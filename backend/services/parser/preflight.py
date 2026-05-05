"""Pre-flight PDF validation — multi-stage filter to reject non-insurance
documents in <2s without burning a Claude API call.

A user uploading a resume / bank statement / random PDF used to wait
~30s and consume ~₹35 in Anthropic credits before Claude returned
"not_an_indian_insurance_policy". This module short-circuits that case
locally.

Algorithm — 5 stages, fail-soft:

  1. Structural — magic bytes, encryption, page count, file size. Hard
     reject with a specific error_type so the frontend can show a
     targeted message.
  2. Text-layer extraction — first 5 pages or 8000 chars via pymupdf.
     If <100 chars total → likely a scanned image-only PDF; defer to
     Claude (which has its own validation) rather than risk false reject.
  3. Multi-signal scoring — vocab + regulatory + structure + brand +
     negative indicators. Each signal is bounded; final score [0, 100].
  4. Decision matrix — accept ≥50, borderline 30-49 (defer to Claude),
     reject <30.
  5. Reject envelope — structured 400 with `detected_type_hint` so the
     frontend can say "Looks like a resume — try your policy schedule".

Design principle: when in doubt, defer to Claude. Cost of false reject
on a real policy (user gives up on the product) >> cost of one wasted
Claude call (~₹35). Hence the 30-50 humility band.

Never raises — pymupdf failures fall through to OUTCOME_SKIPPED.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Final, Optional

# pymupdf is the only third-party dep here. Wrap the import so a missing
# or broken install degrades gracefully — preflight_check returns
# OUTCOME_SKIPPED per request rather than crashing the FastAPI app at
# startup. Claude (with its own validation) becomes the safety net.
try:
    import pymupdf
    _PYMUPDF_AVAILABLE = True
    _PYMUPDF_IMPORT_ERROR: str | None = None
except Exception as _e:                             # noqa: BLE001
    pymupdf = None                                  # type: ignore[assignment]
    _PYMUPDF_AVAILABLE = False
    _PYMUPDF_IMPORT_ERROR = str(_e)

from services.parser.canonical_vocabulary import (
    CANONICAL_INSURER_NAMES,
    INSURER_ALIASES,
)

logger = logging.getLogger("kavach.preflight")

if not _PYMUPDF_AVAILABLE:
    # One-time warning at import — operators can grep for it. Per-request
    # logging would be too noisy if the install is broken in production.
    logger.warning(
        "preflight: pymupdf unavailable (%s); all uploads will skip "
        "preflight and defer to Claude",
        _PYMUPDF_IMPORT_ERROR,
    )


# ==========================================================================
# Tunable constants — surfaced at module top so production score
# distributions can drive adjustments without code archaeology.
# ==========================================================================

# --- Stage 1: structural ---
PDF_MAGIC: Final[bytes] = b"%PDF-"
MIN_FILE_BYTES: Final[int] = 10 * 1024              # 10 KB — below = empty/corrupt
MAX_FILE_BYTES: Final[int] = 25 * 1024 * 1024       # 25 MB — defensive (router caps at 15)
MIN_PAGES: Final[int] = 1
MAX_PAGES: Final[int] = 150                         # real wordings: 30-80; >150 is weird

# --- Stage 2: text extraction ---
MAX_PAGES_TO_SCAN: Final[int] = 5
MAX_TEXT_CHARS: Final[int] = 8000
MIN_TEXT_FOR_SCORING: Final[int] = 100              # below = no text layer
NEGATIVE_SCAN_CHARS: Final[int] = 500               # negatives only check head

# --- Stage 4: decision thresholds ---
SCORE_ACCEPT: Final[int] = 50                       # ≥ this → accept
SCORE_BORDERLINE: Final[int] = 30                   # below this → reject

# --- Per-signal caps ---
VOCAB_STRONG_PT: Final[int] = 5
VOCAB_STRONG_CAP: Final[int] = 20
VOCAB_STANDARD_PT: Final[int] = 2
VOCAB_STANDARD_CAP: Final[int] = 10
VOCAB_TOTAL_CAP: Final[int] = 25

REGULATORY_CAP: Final[int] = 20
STRUCTURE_CAP: Final[int] = 20
BRAND_CAP: Final[int] = 15

# --- Outcome strings (exported for callers) ---
OUTCOME_ACCEPT: Final[str] = "accept"
OUTCOME_BORDERLINE: Final[str] = "borderline"
OUTCOME_REJECT: Final[str] = "reject"
OUTCOME_SKIPPED: Final[str] = "skipped_no_text"
OUTCOME_STRUCTURAL: Final[str] = "structural_reject"

# Outcomes that should NOT call Claude (and should NOT consume rate-limit).
OUTCOMES_NO_CLAUDE: Final[frozenset[str]] = frozenset(
    {OUTCOME_REJECT, OUTCOME_STRUCTURAL}
)

# Outcomes that proceed to Claude — rate-limit query filters by these.
OUTCOMES_PROCEED: Final[frozenset[str]] = frozenset(
    {OUTCOME_ACCEPT, OUTCOME_BORDERLINE, OUTCOME_SKIPPED}
)


# ==========================================================================
# Stage 3 vocabulary — kept here so all tunable knobs are co-located.
# ==========================================================================

# Strong indicators: each tuple is a synonym group counted as ONE hit.
# We score by hit-count (×VOCAB_STRONG_PT, capped at VOCAB_STRONG_CAP).
VOCAB_STRONG: Final[tuple[tuple[str, ...], ...]] = (
    ("sum insured", "sum assured"),
    ("policy schedule", "policy wording", "policy document"),
    ("insurer", "insured person", "policyholder"),
    # premium handled separately below — co-occurrence rather than exact phrase
    ("claim settlement", "claim ratio", "claim process"),
)
# Spec: "premium combined with one of: annual, yearly, payable, due".
# We use document-level co-occurrence rather than exact-phrase ("annual
# premium") because real docs use varied phrasings — eBID's "Mode of
# Premium of Payment Yearly" wouldn't match "yearly premium" but it
# clearly is a premium reference.
PREMIUM_MODIFIERS: Final[tuple[str, ...]] = (
    "annual", "yearly", "payable", "due", "monthly", "half-yearly",
)

VOCAB_STANDARD: Final[tuple[str, ...]] = (
    "policy", "insurance", "coverage", "benefits", "exclusions",
    "waiting period", "deductible", "co-payment", "copay",
    "renewal", "endorsement", "nominee",
    "hospitalization", "in-patient", "out-patient", "opd",
)

# Pre-lowercased canonical names + alias keys (aliases are already lc).
CANONICAL_LC: Final[tuple[str, ...]] = tuple(
    n.lower() for n in CANONICAL_INSURER_NAMES
)
ALIAS_KEYS: Final[tuple[str, ...]] = tuple(INSURER_ALIASES.keys())


# Negative indicators — (terms, hint, penalty). Only checked in
# NEGATIVE_SCAN_CHARS head. Includes a leading/trailing space on tokens
# that are otherwise too generic ("cv" → " cv ", "itr" → " itr ") to
# avoid false matches inside longer English words.
NEGATIVE_INDICATORS: Final[tuple[tuple[tuple[str, ...], str, int], ...]] = (
    (("résumé", "resume", "curriculum vitae", " cv "), "resume", 40),
    (("bank statement", "account statement", "transaction history"),
     "bank_statement", 40),
    (("salary slip", "pay slip", "payslip", "salary certificate"),
     "salary_slip", 40),
    (("loan agreement", "loan sanction"), "loan_agreement", 30),
    (("form 16", " itr ", "income tax return"), "tax_document", 30),
    (("lease agreement", "rental agreement"), "lease", 30),
)
# "invoice" handled separately — penalty depends on absence of
# policy/insurance/premium in the same head (a policy invoice is fine).
INVOICE_PENALTY: Final[int] = 30
GST_INVOICE_PENALTY: Final[int] = 20
INVOICE_GUARDS: Final[tuple[str, ...]] = ("policy", "insurance", "premium")


# ==========================================================================
# Regex patterns
# ==========================================================================
# Note on POLICY_NUMBER_RE: spec gave [A-Z0-9]{6,} but real policy
# numbers contain hyphens, slashes, dots ("HE-OR-23-9087421",
# "P/123/456/789"). We allow those characters after a leading
# alphanumeric so the regex still anchors on a meaningful token.

POLICY_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(policy|certificate)[\s_-]*(no|number|#)[:.\s]*"
    r"[A-Z0-9][A-Z0-9./\-]{5,}\b",
    re.IGNORECASE,
)
SUM_INSURED_RE: Final[re.Pattern[str]] = re.compile(
    r"(sum\s+(insured|assured)|coverage)[\s:.]*₹?\s*[\d,]+(\.\d+)?"
    r"(\s*(lakh|cr|crore))?",
    re.IGNORECASE,
)
POLICY_PERIOD_RE: Final[re.Pattern[str]] = re.compile(
    r"(period\s+of\s+insurance|policy\s+period)[:.\s]+"
    r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}",
    re.IGNORECASE,
)
PREMIUM_AMOUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"(annual\s+premium|premium\s+payable|installment\s+premium)"
    r"[:.\s]*₹?\s*[\d,]+",
    re.IGNORECASE,
)
UIN_RE: Final[re.Pattern[str]] = re.compile(
    r"\bUIN[:\s]*[A-Z0-9/]{8,}",
    re.IGNORECASE,
)
IRDAI_REG_RE: Final[re.Pattern[str]] = re.compile(
    r"(irdai[\s_\-]*reg|reg\.?\s*no\.?)[:\s.]*\d+",
    re.IGNORECASE,
)
WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


# ==========================================================================
# Result type
# ==========================================================================

@dataclass(frozen=True, slots=True)
class PreflightResult:
    """Output of preflight_check. Never raises — error info is in fields.

    `outcome` is the canonical state. Callers should branch on it, not
    on score (which is None for structural rejects and skipped).

    `signals` is the per-category breakdown for observability/tuning;
    keys: vocab, regulatory, structure, brand, negative. The negative
    value is non-positive (it's a penalty subtracted from the sum).

    `error` + `error_message` are populated only for OUTCOME_STRUCTURAL
    so the router can emit a precise frontend-facing error type.
    """
    outcome: str
    score: Optional[int]
    signals: dict[str, int] = field(default_factory=dict)
    page_count: int = 0
    has_text_layer: bool = False
    detected_type_hint: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None
    elapsed_ms: int = 0


# ==========================================================================
# Public API
# ==========================================================================

def preflight_check(pdf_bytes: bytes) -> PreflightResult:
    """Run all 5 stages. Always returns a PreflightResult; never raises.

    Any unexpected pymupdf error falls through to OUTCOME_SKIPPED so
    Claude (with its own validation) becomes the safety net rather
    than risk false-rejecting a real policy due to local-parse weirdness.
    """
    started = time.perf_counter()

    # --- Stage 1a: byte-level structural checks (no PDF parsing needed) ---
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

    # --- pymupdf availability gate ---
    # If the library is missing/broken, skip past stage 1b/2/3 and let
    # Claude validate. Stage 1a still ran (cheap byte checks), so truly
    # malformed files are still caught even without pymupdf.
    if not _PYMUPDF_AVAILABLE:
        return PreflightResult(
            outcome=OUTCOME_SKIPPED,
            score=None,
            has_text_layer=False,
            elapsed_ms=_elapsed_ms(started),
        )

    # --- Stage 1b: open with pymupdf for page/encryption checks ---
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as e:                          # noqa: BLE001
        # Malformed PDF — header was right but body is corrupt.
        logger.warning("preflight.pymupdf_open_failed: %s", e)
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
                    f"This PDF has {page_count} pages. Insurance documents "
                    f"are usually 1-{MAX_PAGES} pages."
                ),
                elapsed_ms=_elapsed_ms(started),
            )

        # --- Stage 2: text extraction ---
        try:
            raw_text = _extract_text(doc)
        except Exception as e:                      # noqa: BLE001
            logger.warning("preflight.text_extract_failed: %s", e)
            # Defer to Claude — don't reject on local extraction issues.
            return PreflightResult(
                outcome=OUTCOME_SKIPPED,
                score=None,
                page_count=page_count,
                has_text_layer=False,
                elapsed_ms=_elapsed_ms(started),
            )

        normalized = WHITESPACE_RE.sub(" ", raw_text.lower()).strip()

        if len(normalized) < MIN_TEXT_FOR_SCORING:
            # Likely a scanned image-only PDF. Claude handles those fine.
            return PreflightResult(
                outcome=OUTCOME_SKIPPED,
                score=None,
                page_count=page_count,
                has_text_layer=False,
                elapsed_ms=_elapsed_ms(started),
            )

        # --- Stage 3: multi-signal scoring ---
        signals = _score_signals(normalized)

        # --- Stage 4: decision ---
        raw_total = sum(signals.values())
        score = max(0, min(100, raw_total))

        if score < SCORE_BORDERLINE:
            outcome = OUTCOME_REJECT
        elif score < SCORE_ACCEPT:
            outcome = OUTCOME_BORDERLINE
        else:
            outcome = OUTCOME_ACCEPT

        # Type hint only meaningful when we're rejecting — gives the
        # frontend a more targeted error message.
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
        doc.close()  # type: ignore[no-untyped-call]


# ==========================================================================
# Stage 1 helpers
# ==========================================================================

def _structural_check_bytes(pdf_bytes: bytes) -> Optional[tuple[str, str]]:
    """Cheap byte-level checks. Returns (error_type, message) or None."""
    if not pdf_bytes.startswith(PDF_MAGIC):
        return ("invalid_pdf", "This file isn't a valid PDF (no PDF header).")
    if len(pdf_bytes) < MIN_FILE_BYTES:
        return (
            "pdf_too_small",
            f"File is {len(pdf_bytes)} bytes; expected at least "
            f"{MIN_FILE_BYTES} bytes.",
        )
    if len(pdf_bytes) > MAX_FILE_BYTES:
        return (
            "pdf_too_large",
            f"File is {len(pdf_bytes)} bytes; max {MAX_FILE_BYTES} bytes.",
        )
    return None


# ==========================================================================
# Stage 2 helpers
# ==========================================================================

def _extract_text(doc: pymupdf.Document) -> str:
    """Concatenate text from first MAX_PAGES_TO_SCAN pages, capped at
    MAX_TEXT_CHARS chars. Per-page failures are skipped silently — a
    single bad page shouldn't disqualify the document."""
    parts: list[str] = []
    total = 0
    pages_to_scan = min(MAX_PAGES_TO_SCAN, doc.page_count)
    for i in range(pages_to_scan):
        try:
            page_text = doc[i].get_text()  # type: ignore[no-untyped-call]
        except Exception:                           # noqa: BLE001
            continue
        parts.append(page_text)
        total += len(page_text)
        if total >= MAX_TEXT_CHARS:
            break
    return "".join(parts)[:MAX_TEXT_CHARS]


# ==========================================================================
# Stage 3 — signal scoring
# ==========================================================================

def _score_signals(normalized: str) -> dict[str, int]:
    """Compute all 5 signals on the normalized (lowercased) text."""
    return {
        "vocab": _signal_vocab(normalized),
        "regulatory": _signal_regulatory(normalized),
        "structure": _signal_structure(normalized),
        "brand": _signal_brand(normalized),
        "negative": _signal_negative(normalized),
    }


def _signal_vocab(text: str) -> int:
    """Insurance vocabulary — strong + standard buckets, capped at 25."""
    strong_hits = 0
    for synonyms in VOCAB_STRONG:
        if any(s in text for s in synonyms):
            strong_hits += 1
    # Premium-modifier co-occurrence (one extra strong hit).
    if "premium" in text and any(m in text for m in PREMIUM_MODIFIERS):
        strong_hits += 1

    strong = min(VOCAB_STRONG_CAP, strong_hits * VOCAB_STRONG_PT)

    standard_hits = sum(1 for term in VOCAB_STANDARD if term in text)
    standard = min(VOCAB_STANDARD_CAP, standard_hits * VOCAB_STANDARD_PT)

    return min(VOCAB_TOTAL_CAP, strong + standard)


def _signal_regulatory(text: str) -> int:
    """Regulatory + Indian context indicators, capped at 20."""
    score = 0
    if "irdai" in text or "insurance regulatory" in text:
        score += 10
    if UIN_RE.search(text):
        score += 5
    if "gst" in text or "gstin" in text:
        score += 2
    if "₹" in text:
        score += 3
    if "rs." in text or "inr" in text:
        score += 2
    if any(t in text for t in ("lakh", "lakhs", "crore", "crores")):
        score += 3

    # Insurer-name presence (canonical names) — +5 per, capped +10.
    insurer_hits = sum(1 for n in CANONICAL_LC if n in text)
    score += min(10, insurer_hits * 5)

    return min(REGULATORY_CAP, score)


def _signal_structure(text: str) -> int:
    """Document-structure regex matches — each fires +5, cap 20."""
    score = 0
    if POLICY_NUMBER_RE.search(text):
        score += 5
    if SUM_INSURED_RE.search(text):
        score += 5
    if POLICY_PERIOD_RE.search(text):
        score += 5
    if PREMIUM_AMOUNT_RE.search(text):
        score += 5
    return min(STRUCTURE_CAP, score)


def _signal_brand(text: str) -> int:
    """Insurer brand presence — canonical (+10) OR alias (+5), plus
    optional +5 for IRDAI registration. Cap 15.

    Either-or for canonical/alias prevents double-counting (most aliases
    are substrings of their canonical names — "hdfc ergo" is a
    substring of "hdfc ergo general")."""
    score = 0
    if any(n in text for n in CANONICAL_LC):
        score += 10
    elif any(a in text for a in ALIAS_KEYS):
        score += 5
    if IRDAI_REG_RE.search(text):
        score += 5
    return min(BRAND_CAP, score)


def _signal_negative(text: str) -> int:
    """Hard rejection terms in document head. Returns a non-positive int.

    "invoice" alone (without policy/insurance/premium nearby) is
    penalty-worthy because policy invoices always co-mention what they're
    invoicing for. A bare "GST invoice" is most often a vendor invoice."""
    head = text[:NEGATIVE_SCAN_CHARS]
    penalty = 0

    for terms, _hint, pts in NEGATIVE_INDICATORS:
        if any(t in head for t in terms):
            penalty -= pts

    if "invoice" in head and not any(g in head for g in INVOICE_GUARDS):
        if "gst invoice" in head:
            penalty -= GST_INVOICE_PENALTY
        else:
            penalty -= INVOICE_PENALTY

    return penalty


def _detect_type_hint(text: str) -> str:
    """Best-guess document type for friendlier reject messages.

    Returns the first hint whose terms fire in the head, else "unknown".
    Order of NEGATIVE_INDICATORS is the priority order — strongest /
    most specific first."""
    head = text[:NEGATIVE_SCAN_CHARS]
    for terms, hint, _pts in NEGATIVE_INDICATORS:
        if any(t in head for t in terms):
            return hint
    if "invoice" in head and not any(g in head for g in INVOICE_GUARDS):
        return "invoice"
    return "unknown"


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
