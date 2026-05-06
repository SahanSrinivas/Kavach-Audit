"""Download the freshest policy-wording PDFs into ``wordings-latest/``.

This complements ``download_wordings.py`` (which fills ``wordings/``) with
URLs chosen to upgrade known-stale IRDAI mirrors — insurer CDN where Akamai
allows it, United India’s official Mar-2024 filing for UIIHLIP24090,
ManipalCigna’s newer IRDAI UIN, Ditto’s mirror for Oriental, etc.

Some targets list **multiple URLs** (tried in order until a valid PDF).

Usage::
    python scripts/download_wordings_latest.py

Requires ``requests``. Optional Firecrawl fallback uses ``FIRE_CRAWL`` in
``backend/.env`` (same as ``download_wordings.py``).

PDFs under ``wordings-latest/`` remain gitignored via ``*.pdf``.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
WORDINGS_LATEST_DIR = REPO_ROOT / "wordings-latest"
LOG_PATH = WORDINGS_LATEST_DIR / "_download_log.txt"

# ---------------------------------------------------------------------------
# Load fetch helpers from download_wordings.py (same validation + HTTP stack)
# ---------------------------------------------------------------------------

_scripts_dir = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_dw", _scripts_dir / "download_wordings.py")
if _spec is None or _spec.loader is None:
    print("ERROR: could not load download_wordings.py", file=sys.stderr)
    sys.exit(1)
_dw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dw)

slugify = _dw.slugify
_try_fetch = _dw._try_fetch
load_firecrawl_key = _dw.load_firecrawl_key
_now_iso = _dw._now_iso


@dataclass(frozen=True)
class LatestBatchTarget:
    insurer: str
    plan: str
    urls: tuple[str, ...]
    domain: str
    referer: Optional[str] = None


# URLs ordered newest-first / best-effort. Comments reference UIN where cited.
LATEST_TARGETS: tuple[LatestBatchTarget, ...] = (
    LatestBatchTarget(
        "Niva Bupa",
        "ReAssure 2.0 Platinum+",
        (
            # NBHHLIP26042V022526 — master Policy Wording on corporate DAM
            "https://www.nivabupa.com/content/dam/nivabupa/PDF/reassure-2-0/ReAssure%202.0%20-%20Policy%20Wording.pdf",
            "https://transactions.nivabupa.com/pages/doc/policy_wording/ReAssure-2.0-Policy-Wording.pdf",
        ),
        "nivabupa.com",
    ),
    LatestBatchTarget(
        "New India Assurance",
        "Floater Mediclaim",
        (
            "https://www.newindia.co.in/assets/docs/know-more/health/floater-mediclaim-policy/Policy Clause New India Floater Mediclaim Policy wef 01 10 2024.pdf",
        ),
        "newindia.co.in",
    ),
    LatestBatchTarget(
        "ICICI Lombard",
        "Elevate",
        (
            "https://www.icicilombard.com/docs/default-source/apps/elevateapp/assets/pdf/elevate-policy-wordings.pdf",
        ),
        "icicilombard.com",
        referer="https://www.icicilombard.com/health-insurance/elevate-health-policy",
    ),
    LatestBatchTarget(
        "Bajaj Allianz General",
        "Health Guard",
        (
            "https://www.bajajallianz.com/download-documents/health-insurance/health-guard/Health-Guard-Policy-Wordings-print.pdf",
        ),
        "bajajallianz.com",
    ),
    LatestBatchTarget(
        "Aditya Birla Health",
        "Activ One MAX",
        (
            "https://www.adityabirlacapital.com/healthinsurance/assets/pdf/active-one/NXT/product-information/policy-document.pdf",
        ),
        "adityabirlacapital.com",
    ),
    LatestBatchTarget(
        "HDFC ERGO General",
        "Optima Secure",
        (
            "https://www.hdfcergo.com/docs/default-source/downloads/policy-wordings/health/optima-secure-revision-pw.pdf",
        ),
        "hdfcergo.com",
    ),
    LatestBatchTarget(
        "Care Health",
        "Supreme",
        (
            "https://cms.careinsurance.com/cms/public/uploads/download_center/care-supreme---policy-terms-and-conditions.pdf",
        ),
        "careinsurance.com",
    ),
    LatestBatchTarget(
        "SBI General Insurance",
        "Super Health Insurance",
        (
            # Same master wording used for Super Health Platinum / Platinum Infinite (sbigeneral.in/downloads).
            "https://content.sbigeneral.in/uploads/Super_Health_Insurance_Policy_Wording_New_1512_1a70d6d07a.pdf",
        ),
        "sbigeneral.in",
        referer="https://www.sbigeneral.in/health-insurance/super-health-insurance-policy",
    ),
    LatestBatchTarget(
        "Star Health",
        "Comprehensive",
        (
            # Star CDN — typically newer than stale IRDAI mirror for SHAHLIP22028…
            "https://d37e9lgzp3sa8.cloudfront.net/sites/default/files/policy-clauses/star-comprehensive-policy-clause-new-1.pdf",
            "https://irdai.gov.in/documents/37343/931203/SHAHLIP22028V072122_HEALTH2050.pdf/70aade12-d528-1155-a8b7-c03d2cfecd15?version=1.1&t=1668769970678&download=true",
        ),
        "starhealth.in",
    ),
    LatestBatchTarget(
        "Star Health",
        "Senior Citizens Red Carpet",
        (
            # Prefer newer IRDAI filing SHAHLIP22040… then legacy SHAHLIP22199…
            "https://irdai.gov.in/documents/37343/931203/SHAHLIP22040V052122_HEALTH2060.pdf/90e8300f-8f3c-8994-2598-cc59a52be20d?download=true&t=1668770691979&version=1.1",
            "https://irdai.gov.in/documents/37343/931203/SHAHLIP22199V062122.pdf/e5830765-7541-0484-9119-330738250254?version=1.1&t=1668853579702&download=true",
        ),
        "starhealth.in",
    ),
    LatestBatchTarget(
        "ManipalCigna",
        "ProHealth Prime",
        (
            # MCIHLIP23022V032223 — newer IRDAI filing than MCIHLIP22224…
            "https://irdai.gov.in/documents/37343/931203/MCIHLIP23022V032223.pdf/95221470-886d-ff52-2a78-b1031aaddee7?download=true&t=1669349551633&version=1.0",
            "https://s3.ap-south-1.amazonaws.com/ditto-partners/Pro_Health_Prime_Protect_Policy_Wording_7e009aa66b.pdf",
            "https://irdai.gov.in/documents/37343/931203/MCIHLIP22224V012122.pdf/6cf0a1af-1bc8-0c09-531a-671e15963135?version=1.1&t=1668851840343&download=true",
        ),
        "manipalcigna.com",
    ),
    LatestBatchTarget(
        "United India Insurance",
        "Family Medicare",
        (
            # UIIHLIP24090V052324 — revised wordings wef Mar 2024 (post-Apr-2024 block)
            "https://uiic.co.in/sites/default/files/uploads/downloadcenter/20240311_Policy_Wordings_FMP.pdf",
            "https://irdai.gov.in/documents/37343/931203/UIIHLIP22070V042122_HEALTH2068.pdf/ade80179-0e46-3c62-a889-652663255c71?version=1.1&t=1668769400360&download=true",
        ),
        "uiic.co.in",
        referer="https://uiic.co.in/en/product/health/Family-Medicare-Policy",
    ),
    LatestBatchTarget(
        "Oriental Insurance",
        "Happy Family Floater",
        (
            # Ditto mirror — full wording; aligns with OICHLIP23134 prospectus line
            "https://ditto-partners.s3.ap-south-1.amazonaws.com/Oriental+Insurance/Happy+Family+Floater+Policy-+Policy+wording.pdf",
            "https://s3.ap-south-1.amazonaws.com/ditto-partners/Oriental+Insurance/Happy+Family+Floater+Policy-+Policy+wording.pdf",
            # Older IRDAI-filed HFF 2021-22 (OICHLIP22010…)
            "https://irdai.gov.in/documents/37343/931203/OICHLIP22010V042223.pdf/b8f4f473-3670-8936-c219-d87881338353?download=true&t=1669353756992&version=1.0",
        ),
        "orientalinsurance.org.in",
    ),
    LatestBatchTarget(
        "Tata AIG General",
        "MediCare Premier",
        (
            "https://www.tataaig.com/s3/Tata_AIG_Medi_Care_Premier_2f02f3813c.pdf",
        ),
        "tataaig.com",
    ),
    LatestBatchTarget(
        "National Insurance",
        "Mediclaim",
        (
            "https://irdai.gov.in/documents/37343/931203/NICHLIP21166V042021_2020-2021.pdf/11efffcc-a037-8819-2d2a-dc210ddac550?version=1.1&t=1668663754897&download=true",
        ),
        "nationalinsurance.nic.co.in",
    ),
)


def _batch_to_try_fetch(t: LatestBatchTarget) -> tuple[Optional[bytes], str, str]:
    """Try each URL until one succeeds (same semantics as download_wordings._try_fetch)."""
    fc_key = load_firecrawl_key()
    combined_err: list[str] = []

    for i, url in enumerate(t.urls):
        stub = _dw.WordingTarget(
            insurer=t.insurer,
            plan=t.plan,
            url=url,
            domain=t.domain,
            referer=t.referer,
        )
        body, source, err = _try_fetch(stub, fc_key)
        if body is not None:
            return body, source, err or ""
        combined_err.append(f"url{i + 1}: {err}")

    return None, "-", "; ".join(combined_err)


def write_log(lines: list[str]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    WORDINGS_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    fc_key = load_firecrawl_key()
    log: list[str] = []
    log.append(f"# Wordings LATEST download log — {_now_iso()}")
    log.append(
        f"# {len(LATEST_TARGETS)} targets, firecrawl fallback: "
        f"{'enabled' if fc_key else 'DISABLED'}"
    )
    log.append("")

    ok = 0
    failed = 0
    import time

    for t in LATEST_TARGETS:
        insurer_slug = slugify(t.insurer)
        plan_slug = slugify(t.plan)
        out_dir = WORDINGS_LATEST_DIR / insurer_slug
        out_path = out_dir / f"{plan_slug}.pdf"

        ts = _now_iso()
        started = time.perf_counter()
        body, source, err = _batch_to_try_fetch(t)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if body is None:
            failed += 1
            log.append(
                f"[{ts}] FAIL  {t.insurer} | {t.plan}\n"
                f"  urls:   {len(t.urls)} tried\n"
                f"  error:  {err}  ({elapsed_ms}ms)"
            )
            print(f"FAIL  {t.insurer} / {t.plan}: {err}")
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)
        size = len(body)
        ok += 1
        log.append(
            f"[{ts}] OK    {t.insurer} | {t.plan}  (via {source})\n"
            f"  tried:  {len(t.urls)} URL(s)\n"
            f"  size:   {size:,} bytes  ({elapsed_ms}ms)\n"
            f"  saved:  {out_path.relative_to(REPO_ROOT)}"
        )
        print(f"OK    {t.insurer} / {t.plan}: {size:,} bytes  (via {source})")

    log.append("")
    log.append(f"# Summary: {ok} ok, {failed} failed (of {len(LATEST_TARGETS)} targets)")
    write_log(log)
    print(f"\n{ok} ok, {failed} failed. Log → {LOG_PATH.relative_to(REPO_ROOT)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
