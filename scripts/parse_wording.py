#!/usr/bin/env python3
"""Admin CLI: parse a wording PDF and store it in the wordings DB.

Two modes:

1. Default — POST the PDF to the running backend's admin endpoint
   (POST /api/admin/wordings/parse). Endpoint reads the PDF from disk,
   calls Claude, stores result with qa_status="auto_parsed". Requires
   the backend to be running and reachable.

2. --dry-run — Parse the PDF locally + show what WOULD be stored,
   without hitting the backend or writing anything to Mongo. Requires
   ANTHROPIC_API_KEY in env, no running backend needed. Useful for
   eyeballing the wording shape before committing to the schema or
   for offline schema review.

Usage:

  # Normal parse-and-store (backend must be running)
  python scripts/parse_wording.py \\
    --pdf path/to/optima-restore.pdf \\
    --insurer "HDFC ERGO General" \\
    --plan "Optima Restore" \\
    --source-url "https://www.hdfcergo.com/docs/wording.pdf" \\
    --uin "HDFHLIP26055V102526"

  # Dry-run: see what would be stored, no backend, no DB write
  python scripts/parse_wording.py --dry-run \\
    --pdf optima-restore-revision.pdf \\
    --insurer "HDFC ERGO General" \\
    --plan "Optima Restore"

Auth: ADMIN_PASSWORD env var (or --admin-password override).
Cost: ~₹15-30 (~$0.20-0.40) per parse on Sonnet 4. Same as the parser
smoke test. Don't re-run on the same PDF unless you mean to — admin
upsert is idempotent so it WILL replace the previous parse.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Parse a wording PDF + store in the wordings DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--pdf", required=True, help="Path to the wording PDF")
    p.add_argument("--insurer", required=True,
                   help="Canonical insurer name (e.g., 'HDFC ERGO General')")
    p.add_argument("--plan", required=True,
                   help="Canonical short plan name (e.g., 'Optima Restore')")
    p.add_argument("--source-url", default=None,
                   help="URL the PDF was downloaded from (traceability)")
    p.add_argument("--uin", default=None, help="IRDAI UIN, e.g. HDFHLIP26055V102526")
    p.add_argument("--version", default=None, help="Wording version label")
    p.add_argument("--host", default="http://localhost:8000",
                   help="Backend host (default: http://localhost:8000)")
    p.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD"),
                   help="Admin bearer token (default: $ADMIN_PASSWORD)")
    p.add_argument("--dry-run", action="store_true",
                   help="Parse locally, print what would be stored, do NOT POST. "
                        "Requires ANTHROPIC_API_KEY; no backend needed.")
    return p


def _print_doc(label: str, doc: dict) -> None:
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    print(json.dumps(doc, indent=2, default=str, ensure_ascii=False))


async def _dry_run(args: argparse.Namespace) -> int:
    """Parse locally + show what would be stored. No backend, no DB write."""
    from services.parser import ParseFailureError, parse_policy_pdf
    from services.parser.canonical_vocabulary import CANONICAL_INSURER_NAMES
    from services.wordings import compose_wording_doc

    if args.insurer not in CANONICAL_INSURER_NAMES:
        print(f"ERROR: insurer {args.insurer!r} not in CANONICAL_INSURER_NAMES",
              file=sys.stderr)
        return 2

    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set in env", file=sys.stderr)
        return 2

    pdf_bytes = pdf_path.read_bytes()
    print(f"--- DRY RUN ---")
    print(f"PDF:        {pdf_path}")
    print(f"Size:       {len(pdf_bytes):,} bytes ({len(pdf_bytes)//1024} KB)")
    print(f"Insurer:    {args.insurer}")
    print(f"Plan:       {args.plan}")
    print(f"Calling Claude (this takes 5-15s + costs ~₹15-30) ...")

    try:
        parsed = await parse_policy_pdf(pdf_bytes, pdf_path.name)
    except ParseFailureError as e:
        print(f"\nERROR: parse failed: {e.error_type} — {e}", file=sys.stderr)
        return 1

    doc = compose_wording_doc(
        parsed,
        insurer_canonical=args.insurer,
        plan_name=args.plan,
        source_filename=pdf_path.name,
        source_url=args.source_url,
        wording_uin=args.uin,
        wording_version=args.version,
    )

    _print_doc("DRY-RUN OUTPUT — what WOULD be stored (not stored):", doc)
    print("\n" + "="*70)
    print("To actually store, re-run WITHOUT --dry-run (requires running backend).")
    print("To verify after storing, run scripts/verify_wording.py --id <wording_id>")
    return 0


def _real_parse(args: argparse.Namespace) -> int:
    """POST to /api/admin/wordings/parse via the running backend."""
    import urllib.error
    import urllib.request

    if not args.admin_password:
        print("ERROR: --admin-password not provided and ADMIN_PASSWORD env var unset",
              file=sys.stderr)
        return 2

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found", file=sys.stderr)
        return 2

    # The endpoint reads the PDF from disk by absolute path on the server.
    # If running locally that's fine. For remote backends, the PDF must
    # already exist at this path on the server filesystem.
    body = json.dumps({
        "pdf_path": str(pdf_path),
        "insurer_canonical": args.insurer,
        "plan_name": args.plan,
        "source_url": args.source_url,
        "wording_uin": args.uin,
        "wording_version": args.version,
    }).encode("utf-8")

    url = f"{args.host.rstrip('/')}/api/admin/wordings/parse"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {args.admin_password}")

    print(f"--- POST {url} ---")
    print(f"PDF: {pdf_path}")
    print(f"Insurer: {args.insurer}  |  Plan: {args.plan}")
    print(f"Calling backend (5-15s while Claude parses) ...")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_body = resp.read().decode("utf-8")
            payload = json.loads(response_body)
    except urllib.error.HTTPError as e:
        print(f"\nHTTP {e.code}: {e.reason}", file=sys.stderr)
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            print(json.dumps(err_body, indent=2), file=sys.stderr)
        except Exception:
            pass
        return 1
    except urllib.error.URLError as e:
        print(f"\nERROR: cannot reach backend at {args.host}: {e}", file=sys.stderr)
        print("Is uvicorn running?", file=sys.stderr)
        return 1

    if not payload.get("success"):
        print(f"\nERROR: backend returned success=false: {payload}", file=sys.stderr)
        return 1

    data = payload["data"]
    wording_id = data.get("wording_id")
    print(f"\n✓ Stored wording id={wording_id} (qa_status=auto_parsed)")
    _print_doc("STORED WORDING DOC:", data["wording"])
    print(f"\nNext: review the rules block above. When satisfied, run:")
    print(f"  python scripts/verify_wording.py --id {wording_id} \\")
    print(f"      --notes 'QA passed' --host {args.host}")
    return 0


def main() -> int:
    args = _build_arg_parser().parse_args()
    if args.dry_run:
        return asyncio.run(_dry_run(args))
    return _real_parse(args)


if __name__ == "__main__":
    sys.exit(main())
