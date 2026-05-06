"""Life pre-flight PDF validation.

Reject obvious non-life-policy PDFs early (resume/bank statement/invoice)
before extraction/LLM costs are incurred.

# TODO(preflight-converge): When both health and life preflight are
# stable post-dogfood, evaluate Option C — extract shared core into
# services/preflight_core.py with health and life as thin tuning
# wrappers. See architecture decision in PR description for context.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Final, Optional

try:
    import pymupdf

    _PYMUPDF_AVAILABLE = True
    _PYMUPDF_IMPORT_ERROR: str | None = None
except Exception as _e:  # noqa: BLE001
    pymupdf = None
    _PYMUPDF_AVAILABLE = False
    _PYMUPDF_IMPORT_ERROR = str(_e)

from services.parser.preflight import PreflightResult

logger = logging.getLogger("kavach.life.preflight")

if not _PYMUPDF_AVAILABLE:
    logger.warning(
        "life.preflight: pymupdf unavailable (%s); uploads will skip life preflight",
        _PYMUPDF_IMPORT_ERROR,
    )


# ==========================================================================
# Tunable constants (life-specific)
# ==========================================================================

# --- Stage 1: structural ---
PDF_MAGIC: Final[bytes] = b"%PDF-"
# 10KB floor catches empty/corrupt stubs early.
MIN_FILE_BYTES: Final[int] = 10 * 1024
# Defensive upper bound; router has its own cap too.
MAX_FILE_BYTES: Final[int] = 25 * 1024 * 1024
MIN_PAGES: Final[int] = 1
# Life CIS/bonds are usually small-medium; very large files are suspicious.
MAX_PAGES: Final[int] = 150

# --- Stage 2: text extraction ---
# Scan only first few pages for fast preflight decisions.
MAX_PAGES_TO_SCAN: Final[int] = 5
MAX_TEXT_CHARS: Final[int] = 8000
# If text is too short, likely scanned/image-only; defer instead of rejecting.
MIN_TEXT_FOR_SCORING: Final[int] = 100
# Negative indicators run on early head text for speed.
NEGATIVE_SCAN_CHARS: Final[int] = 500

# --- Stage 4: decision thresholds ---
# Life CIS docs are often more standardized than health wordings.
SCORE_ACCEPT_LIFE: Final[int] = 55
# Same humility band as health: borderline proceeds to extraction.
SCORE_BORDERLINE_LIFE: Final[int] = 30

# --- Per-signal caps ---
# Strong life keywords should carry most positive weight.
VOCAB_STRONG_PT: Final[int] = 5
VOCAB_STRONG_CAP: Final[int] = 25
# Broad vocabulary still useful, but lower confidence.
VOCAB_STANDARD_PT: Final[int] = 2
VOCAB_STANDARD_CAP: Final[int] = 10
VOCAB_TOTAL_CAP: Final[int] = 30

# Regulatory/tax/Indian context confidence bucket.
REGULATORY_CAP: Final[int] = 20
# Document-structure signals from regexes.
STRUCTURE_CAP: Final[int] = 20
# Insurer brand presence is useful but not sufficient alone.
BRAND_CAP: Final[int] = 15

# --- Outcome strings (parity with health) ---
OUTCOME_ACCEPT: Final[str] = "accept"
OUTCOME_BORDERLINE: Final[str] = "borderline"
OUTCOME_REJECT: Final[str] = "reject"
OUTCOME_SKIPPED: Final[str] = "skipped_no_text"
OUTCOME_STRUCTURAL: Final[str] = "structural_reject"


# ==========================================================================
# Life vocabulary and indicators
# ==========================================================================

# Strong indicators: each tuple is a synonym group counted once.
VOCAB_STRONG: Final[tuple[tuple[str, ...], ...]] = (
    ("sum assured", "sum insured"),
    ("policy term",),
    ("premium payment term",),
    ("nominee", "appointee"),
    ("free look period", "free-look period"),
    ("rider",),
    ("customer information sheet", " cis "),
    ("policy bond",),
    ("death benefit",),
    ("maturity benefit",),
)

VOCAB_STANDARD: Final[tuple[str, ...]] = (
    "policy",
    "insurance",
    "premium",
    "policyholder",
    "insured",
    "premium frequency",
    "premium mode",
    "life assured",
    "survival benefit",
    "surrender value",
)

INDIAN_CONTEXT_TERMS: Final[tuple[str, ...]] = (
    "irdai",
    "uin",
    "₹",
    "rs.",
    "inr",
    "lakh",
    "crore",
    "section 80c",
    "section 10(10d)",
)

LIFE_INSURER_NAMES: Final[tuple[str, ...]] = (
    "lic",
    "life insurance corporation",
    "hdfc life",
    "icici prudential life",
    "icici pru life",
    "sbi life",
    "max life",
    "tata aia life",
    "bajaj allianz life",
    "aditya birla sun life",
    "absli",
    "kotak mahindra life",
    "kotak life",
    "canara hsbc life",
    "pnb metlife",
    "reliance nippon life",
    "bharti axa life",
    "future generali life",
    "indiafirst life",
    "star union dai-ichi",
    "edelweiss tokio life",
    "pramerica life",
    "aegon life",
    "exide life",
    "shriram life",
)

NEGATIVE_INDICATORS: Final[tuple[tuple[tuple[str, ...], str, int], ...]] = (
    (("résumé", "resume", "curriculum vitae", " cv "), "resume", 40),
    (("bank statement", "account statement", "transaction history"), "bank_statement", 40),
    (("salary slip", "pay slip", "payslip", "salary certificate"), "salary_slip", 40),
    (("loan agreement", "loan sanction"), "loan_agreement", 30),
    (("form 16", " itr ", "income tax return"), "tax_document", 30),
    (("lease agreement", "rental agreement"), "lease", 30),
)

INVOICE_PENALTY: Final[int] = 30
GST_INVOICE_PENALTY: Final[int] = 20
INVOICE_GUARDS: Final[tuple[str, ...]] = ("policy", "insurance", "premium")


# ==========================================================================
# Regex patterns
# ==========================================================================

UIN_RE: Final[re.Pattern[str]] = re.compile(
    r"\bUIN[:\s]*[A-Z0-9/]{8,}",
    re.IGNORECASE,
)
POLICY_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(policy|certificate)[\s_-]*(no|number|#)[:.\s]*[A-Z0-9][A-Z0-9./\-]{5,}\b",
    re.IGNORECASE,
)
SUM_ASSURED_RE: Final[re.Pattern[str]] = re.compile(
    r"(sum\s+(assured|insured)|death\s+benefit|maturity\s+benefit)"
    r"[\s:.]*₹?\s*[\d,]+(\.\d+)?(\s*(lakh|cr|crore))?",
    re.IGNORECASE,
)
TERM_RE: Final[re.Pattern[str]] = re.compile(
    r"(policy\s+term|premium\s+payment\s+term|ppt|pt)[:.\s]*\d{1,3}",
    re.IGNORECASE,
)
PREMIUM_RE: Final[re.Pattern[str]] = re.compile(
    r"(premium(\s+frequency|\s+mode)?|annual\s+premium|modal\s+premium)"
    r"[:.\s]*₹?\s*[\d,]+",
    re.IGNORECASE,
)
WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


def preflight_check_life(pdf_bytes: bytes) -> PreflightResult:
    """Run life preflight checks. Always returns PreflightResult; never raises."""
    started = time.perf_counter()

    struct_err = _structural_check_bytes(pdf_bytes)
    if struct_err is not None:
        err, msg = struct_err
        return PreflightResult(
            outcome=OUTCOME_STRUCTURAL,
            score=None,
            error=err,
            error_message=msg,
            elapsed_ms=_elapsed_ms(started),
        )

    if not _PYMUPDF_AVAILABLE:
        return PreflightResult(
            outcome=OUTCOME_SKIPPED,
            score=None,
            has_text_layer=False,
            elapsed_ms=_elapsed_ms(started),
        )

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        logger.warning("life.preflight.pymupdf_open_failed: %s", e)
        return PreflightResult(
            outcome=OUTCOME_STRUCTURAL,
            score=None,
            error="invalid_pdf",
            error_message="This file isn't a valid PDF.",
            elapsed_ms=_elapsed_ms(started),
        )

    try:
        if doc.needs_pass:
            return PreflightResult(
                outcome=OUTCOME_STRUCTURAL,
                score=None,
                page_count=doc.page_count,
                error="encrypted_pdf",
                error_message="This PDF is password-protected.",
                elapsed_ms=_elapsed_ms(started),
            )

        page_count = doc.page_count
        if page_count < MIN_PAGES:
            return PreflightResult(
                outcome=OUTCOME_STRUCTURAL,
                score=None,
                page_count=page_count,
                error="pdf_too_few_pages",
                error_message=f"This PDF has {page_count} pages.",
                elapsed_ms=_elapsed_ms(started),
            )
        if page_count > MAX_PAGES:
            return PreflightResult(
                outcome=OUTCOME_STRUCTURAL,
                score=None,
                page_count=page_count,
                error="pdf_too_many_pages",
                error_message=(
                    f"This PDF has {page_count} pages. Insurance documents are "
                    f"usually 1-{MAX_PAGES} pages."
                ),
                elapsed_ms=_elapsed_ms(started),
            )

        try:
            raw_text = _extract_text(doc)
        except Exception as e:  # noqa: BLE001
            logger.warning("life.preflight.text_extract_failed: %s", e)
            return PreflightResult(
                outcome=OUTCOME_SKIPPED,
                score=None,
                page_count=page_count,
                has_text_layer=False,
                elapsed_ms=_elapsed_ms(started),
            )

        normalized = WHITESPACE_RE.sub(" ", raw_text.lower()).strip()
        if len(normalized) < MIN_TEXT_FOR_SCORING:
            return PreflightResult(
                outcome=OUTCOME_SKIPPED,
                score=None,
                page_count=page_count,
                has_text_layer=False,
                elapsed_ms=_elapsed_ms(started),
            )

        signals = _score_signals(normalized)
        score = max(0, min(100, sum(signals.values())))

        if score < SCORE_BORDERLINE_LIFE:
            outcome = OUTCOME_REJECT
        elif score < SCORE_ACCEPT_LIFE:
            outcome = OUTCOME_BORDERLINE
        else:
            outcome = OUTCOME_ACCEPT

        hint = _detect_type_hint(normalized) if outcome == OUTCOME_REJECT else None
        return PreflightResult(
            outcome=outcome,
            score=score,
            signals=signals,
            page_count=page_count,
            has_text_layer=True,
            detected_type_hint=hint,
            elapsed_ms=_elapsed_ms(started),
        )
    finally:
        doc.close()


def _structural_check_bytes(pdf_bytes: bytes) -> Optional[tuple[str, str]]:
    if not pdf_bytes.startswith(PDF_MAGIC):
        return ("invalid_pdf", "This file isn't a valid PDF (no PDF header).")
    if len(pdf_bytes) < MIN_FILE_BYTES:
        return (
            "pdf_too_small",
            f"File is {len(pdf_bytes)} bytes; expected at least {MIN_FILE_BYTES} bytes.",
        )
    if len(pdf_bytes) > MAX_FILE_BYTES:
        return (
            "pdf_too_large",
            f"File is {len(pdf_bytes)} bytes; max {MAX_FILE_BYTES} bytes.",
        )
    return None


def _extract_text(doc: "pymupdf.Document") -> str:
    parts: list[str] = []
    total = 0
    pages_to_scan = min(MAX_PAGES_TO_SCAN, doc.page_count)
    for i in range(pages_to_scan):
        try:
            page_text = doc[i].get_text()
        except Exception:  # noqa: BLE001
            continue
        parts.append(page_text)
        total += len(page_text)
        if total >= MAX_TEXT_CHARS:
            break
    return "".join(parts)[:MAX_TEXT_CHARS]


def _score_signals(text: str) -> dict[str, int]:
    return {
        "vocab": _signal_vocab(text),
        "regulatory": _signal_regulatory(text),
        "structure": _signal_structure(text),
        "brand": _signal_brand(text),
        "negative": _signal_negative(text),
    }


def _signal_vocab(text: str) -> int:
    strong_hits = 0
    for synonyms in VOCAB_STRONG:
        if any(term in text for term in synonyms):
            strong_hits += 1
    strong = min(VOCAB_STRONG_CAP, strong_hits * VOCAB_STRONG_PT)

    standard_hits = sum(1 for term in VOCAB_STANDARD if term in text)
    standard = min(VOCAB_STANDARD_CAP, standard_hits * VOCAB_STANDARD_PT)
    return min(VOCAB_TOTAL_CAP, strong + standard)


def _signal_regulatory(text: str) -> int:
    score = 0
    if "irdai" in text:
        score += 8
    if UIN_RE.search(text):
        score += 6
    if "₹" in text:
        score += 3
    if "rs." in text or "inr" in text:
        score += 2
    if "lakh" in text or "crore" in text:
        score += 3
    if "section 80c" in text or "section 10(10d)" in text:
        score += 6
    if any(term in text for term in INDIAN_CONTEXT_TERMS):
        score += 2
    return min(REGULATORY_CAP, score)


def _signal_structure(text: str) -> int:
    score = 0
    if POLICY_NUMBER_RE.search(text):
        score += 5
    if SUM_ASSURED_RE.search(text):
        score += 5
    if TERM_RE.search(text):
        score += 5
    if PREMIUM_RE.search(text):
        score += 5
    return min(STRUCTURE_CAP, score)


def _signal_brand(text: str) -> int:
    insurer_hits = sum(1 for insurer in LIFE_INSURER_NAMES if insurer in text)
    if insurer_hits == 0:
        return 0
    return min(BRAND_CAP, 5 + insurer_hits * 2)


def _signal_negative(text: str) -> int:
    head = text[:NEGATIVE_SCAN_CHARS]
    penalty = 0

    for terms, _hint, points in NEGATIVE_INDICATORS:
        if any(term in head for term in terms):
            penalty -= points

    if "invoice" in head and not any(guard in head for guard in INVOICE_GUARDS):
        if "gst invoice" in head:
            penalty -= GST_INVOICE_PENALTY
        else:
            penalty -= INVOICE_PENALTY
    return penalty


def _detect_type_hint(text: str) -> str:
    head = text[:NEGATIVE_SCAN_CHARS]
    for terms, hint, _points in NEGATIVE_INDICATORS:
        if any(term in head for term in terms):
            return hint
    if "invoice" in head and not any(guard in head for guard in INVOICE_GUARDS):
        return "invoice"
    return "unknown"


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)

