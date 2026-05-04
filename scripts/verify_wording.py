#!/usr/bin/env python3
"""Admin CLI: update a wording's qa_status.

Promotes a parsed wording to "human_verified" (default) after admin
review. Or flag it as "needs_review" / reset to "auto_parsed".

Usage:

  # Mark as human_verified (default status)
  python scripts/verify_wording.py --id <wording_id> --notes "QA passed"

  # Flag for re-review
  python scripts/verify_wording.py --id <wording_id> \\
    --status needs_review --notes "Sub-limits look wrong, re-parse"

  # Reset to auto_parsed (rare — typically after re-parse)
  python scripts/verify_wording.py --id <wording_id> --status auto_parsed

Auth: ADMIN_PASSWORD env var (or --admin-password override).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

VALID_STATUSES = ("auto_parsed", "human_verified", "needs_review")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Update a wording's qa_status (admin-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--id", required=True, dest="wording_id",
                   help="Wording id (UUID string from parse_wording.py output)")
    p.add_argument("--status", default="human_verified", choices=VALID_STATUSES,
                   help="New qa_status (default: human_verified)")
    p.add_argument("--notes", default=None,
                   help="Optional reviewer note (gets stored on the wording)")
    p.add_argument("--host", default="http://localhost:8000",
                   help="Backend host (default: http://localhost:8000)")
    p.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD"),
                   help="Admin bearer token (default: $ADMIN_PASSWORD)")
    return p


def main() -> int:
    args = _build_arg_parser().parse_args()
    if not args.admin_password:
        print("ERROR: --admin-password not provided and ADMIN_PASSWORD env var unset",
              file=sys.stderr)
        return 2

    body_dict: dict = {"status": args.status}
    if args.notes:
        body_dict["notes"] = args.notes

    url = f"{args.host.rstrip('/')}/api/admin/wordings/{args.wording_id}/qa"
    req = urllib.request.Request(
        url, data=json.dumps(body_dict).encode("utf-8"), method="PATCH",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {args.admin_password}")

    print(f"--- PATCH {url} ---")
    print(f"status: {args.status}" + (f" | notes: {args.notes}" if args.notes else ""))
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
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
        return 1

    if not payload.get("success"):
        print(f"\nERROR: backend returned success=false: {payload}", file=sys.stderr)
        return 1

    w = payload["data"]["wording"]
    print(f"\n✓ Updated wording id={w['id']}")
    print(f"  insurer:        {w.get('insurer_canonical')}")
    print(f"  plan:           {w.get('plan_name')}")
    print(f"  qa_status:      {w.get('qa_status')}")
    print(f"  qa_verified_by: {w.get('qa_verified_by')}")
    print(f"  qa_verified_at: {w.get('qa_verified_at')}")
    if w.get("qa_notes"):
        print(f"  qa_notes:       {w['qa_notes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
