"""Benchmark insurer table (FY 2022–25 style metrics) + wording downloads for gaps.

The user's top-10 list overlaps largely with ``download_wordings_latest.py``.
Already covered there (or in ``download_wordings.py``):

  HDFC ERGO, Bajaj Allianz (as “Bajaj General”), Aditya Birla Health,
  Care Health, Niva Bupa, ICICI Lombard, Tata AIG General.

This module stores the **full benchmark table** as structured data and defines
**additional** policy-wording PDF targets for insurers that were missing from
``download_wordings_latest.py``:

  • SBI General Insurance — **Super Health** master wording (aligns with Ditto’s
    *Super Health Platinum Infinite*; Platinum Infinite brochure-only PDFs are not full wordings)
  • Go Digit General Insurance
  • Future Generali India — mapped from the label **“Generali Central”**
    (no insurer is registered under that exact name on IRDAI; we treat it as
    Future Generali India’s retail **Health Total** line. Adjust the URL row if
    your source meant a different carrier.)

Usage — fetch only the three additions into ``wordings-benchmark/``::

    python scripts/benchmark_insurer_wordings.py

Requires ``requests`` (same as ``download_wordings.py``).
PDFs remain gitignored via ``*.pdf``.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
WORDINGS_BENCHMARK_DIR = REPO_ROOT / "wordings-benchmark"
LOG_PATH = WORDINGS_BENCHMARK_DIR / "_download_log.txt"

# ---------------------------------------------------------------------------
# FY 2022–25 style benchmark table (user-supplied)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InsurerBenchmarkRow:
    """Single row from the 5-point rating / public-metrics snapshot."""

    insurer_label: str
    rating_5pt: float
    claim_settlement_ratio_pct: float  # FY 2022–25
    complaints_per_10k_claims: float  # FY 2022–25
    annual_business_crores: float  # FY 2022–25


# Full list provided by product — used for analytics / UI; not exhaustive vs
# ``CANONICAL_INSURER_NAMES`` in the backend.
BENCHMARK_TABLE_2022_25: tuple[InsurerBenchmarkRow, ...] = (
    InsurerBenchmarkRow("HDFC ERGO", 4.99, 96.71, 9.28, 6118.0),
    InsurerBenchmarkRow("Bajaj General", 4.99, 96.78, 3.07, 6119.0),
    InsurerBenchmarkRow("Aditya Birla", 4.49, 95.81, 18.67, 3290.0),
    InsurerBenchmarkRow("Care Health", 4.23, 93.13, 42.0, 6775.0),
    InsurerBenchmarkRow("Niva Bupa", 4.23, 91.62, 42.85, 5481.0),
    InsurerBenchmarkRow("SBI General", 3.79, 96.14, 20.51, 3329.0),
    InsurerBenchmarkRow("Go Digit", 3.69, 98.66, 16.88, 1388.0),
    InsurerBenchmarkRow("Generali Central", 3.66, 91.78, 11.02, 3989.0),
    InsurerBenchmarkRow("ICICI Lombard", 3.65, 84.50, 10.67, 6794.0),
    InsurerBenchmarkRow("TATA AIG", 3.43, 88.72, 10.65, 3165.0),
)


def benchmark_labels_covered_by_wordings_latest() -> frozenset[str]:
    """Normalized insurer names already present in ``download_wordings_latest``."""
    return frozenset(
        {
            "hdfc ergo general",
            "bajaj allianz general",
            "aditya birla health",
            "care health",
            "niva bupa",
            "icici lombard",
            "tata aig general",
        }
    )


def benchmark_row_download_status(row: InsurerBenchmarkRow) -> str:
    """Human-readable: whether we already have a wording batch entry."""
    key = row.insurer_label.strip().lower()
    covered = benchmark_labels_covered_by_wordings_latest()

    aliases = {
        "hdfc ergo": "hdfc ergo general",
        "bajaj general": "bajaj allianz general",
        "aditya birla": "aditya birla health",
        "tata aig": "tata aig general",
    }
    normalized = aliases.get(key, key)

    # Table-only rows (no exact match in wording scripts — subsidiary naming).
    if key == "generali central":
        return "additional_download (mapped to Future Generali India — see script docstring)"

    if normalized in covered:
        return "in_download_wordings_latest"

    if key in {"sbi general", "go digit"}:
        return "additional_download (this module)"

    return "not_in_batch — extend download_wordings_latest.py if you add a flagship plan"


# ---------------------------------------------------------------------------
# Additional wording targets (missing from existing batches)
# ---------------------------------------------------------------------------

_scripts_dir = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_dw", _scripts_dir / "download_wordings.py")
if _spec is None or _spec.loader is None:
    print("ERROR: could not load download_wordings.py", file=sys.stderr)
    sys.exit(1)
_dw = importlib.util.module_from_spec(_spec)
# Register before exec_module so Python 3.14's dataclass internals can
# resolve cls.__module__ during forward-reference evaluation. Without
# this, AttributeError: 'NoneType' object has no attribute '__dict__'
# at the @dataclass(frozen=True) line in download_wordings.py.
sys.modules["_dw"] = _dw
_spec.loader.exec_module(_dw)

slugify = _dw.slugify
_try_fetch = _dw._try_fetch
load_firecrawl_key = _dw.load_firecrawl_key


@dataclass(frozen=True)
class ExtraTarget:
    insurer: str
    plan: str
    urls: tuple[str, ...]
    domain: str
    referer: Optional[str] = None


# Official PDFs — verify UIN inside each file after download.
ADDITIONAL_BENCHMARK_TARGETS: tuple[ExtraTarget, ...] = (
    ExtraTarget(
        "SBI General Insurance",
        "Super Health Insurance (incl. Platinum Infinite)",
        (
            # Super Health product family wording — same document covers Platinum / Platinum Infinite
            # as listed under “Super Health Insurance” on sbigeneral.in/downloads.
            "https://content.sbigeneral.in/uploads/Super_Health_Insurance_Policy_Wording_New_1512_1a70d6d07a.pdf",
            "https://content.sbigeneral.in/uploads/a03c37a8bc184d5b883c55f535e36bb2.pdf",
        ),
        "sbigeneral.in",
        referer="https://www.sbigeneral.in/health-insurance/super-health-insurance-policy",
    ),
    ExtraTarget(
        "Go Digit General Insurance",
        "Digit Health Insurance Policy",
        (
            "https://www.godigit.com/content/dam/godigit/directportal/en/downloads/health/Policy%20Wordings%20-%20Digit%20Health%20Insurance%20Policy.pdf",
        ),
        "godigit.com",
        referer="https://www.godigit.com/",
    ),
    ExtraTarget(
        "Future Generali India Insurance",
        "Health Total",
        (
            # Retail Health Total — IRDAI mirror (file name contains '+', encoded by fetch)
            "https://irdai.gov.in/documents/37343/931203/FG_+HEALTH+TOTAL_2015-2016.pdf/1eb4f64e-57e8-6ec7-e9b3-43ad81dee8b7?t=1668408586057&version=1.1",
        ),
        "futuregenerali.in",
        referer="https://www.futuregenerali.in/",
    ),
)


def _try_urls(t: ExtraTarget):
    fc_key = load_firecrawl_key()
    errs: list[str] = []
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
            return body, source, err or "", i + 1
        errs.append(f"url{i + 1}: {err}")
    return None, "-", "; ".join(errs), 0


def main() -> int:
    WORDINGS_BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    fc_key = load_firecrawl_key()
    lines: list[str] = [
        f"# benchmark_insurer_wordings — {_dw._now_iso()}",
        f"# firecrawl: {'on' if fc_key else 'off'}",
        "",
    ]
    ok = fail = 0
    import time

    for t in ADDITIONAL_BENCHMARK_TARGETS:
        insurer_slug = slugify(t.insurer)
        plan_slug = slugify(t.plan)
        out_path = WORDINGS_BENCHMARK_DIR / insurer_slug / f"{plan_slug}.pdf"
        t0 = time.perf_counter()
        body, source, err, used_idx = _try_urls(t)
        ms = int((time.perf_counter() - t0) * 1000)
        if body is None:
            fail += 1
            lines.append(f"FAIL {t.insurer} | {t.plan}\n  {err}\n")
            print(f"FAIL  {t.insurer}: {err}")
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)
        ok += 1
        lines.append(
            f"OK {t.insurer} | {t.plan} via {source} (url {used_idx}/{len(t.urls)}) "
            f"{len(body):,}b {ms}ms → {out_path.relative_to(REPO_ROOT)}\n"
        )
        print(f"OK    {t.insurer}: {len(body):,} bytes ({source})")

    lines.append("")
    lines.append(f"# Summary: {ok} ok, {fail} failed")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nLog → {LOG_PATH.relative_to(REPO_ROOT)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
