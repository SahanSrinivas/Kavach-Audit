"""Tests for services.parser.preflight.

Three groups:
  - Structural rejects (Stage 1): non-PDF, encrypted, page count, size
  - Positive cases: real-policy PDFs (gated on fixture presence) +
    synthetic policy schedules
  - Negative cases: resume / bank statement / invoice / generic doc
  - Edge cases: scanned PDF, borderline band, mid-doc negatives, perf

Synthetic PDFs are generated in-test with pymupdf so the suite is
self-contained. Real-PDF tests use the dev-only files at the repo root
(skipped automatically if absent).
"""
from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Optional

import pymupdf
import pytest

from services.parser.preflight import (
    MAX_PAGES,
    MIN_FILE_BYTES,
    OUTCOME_ACCEPT,
    OUTCOME_BORDERLINE,
    OUTCOME_REJECT,
    OUTCOME_SKIPPED,
    OUTCOME_STRUCTURAL,
    SCORE_ACCEPT,
    SCORE_BORDERLINE,
    PreflightResult,
    preflight_check,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPTIMA_PDF = REPO_ROOT / "optima-restore-revision.pdf"
EBID_PDF = REPO_ROOT / "eBID_SA609099_BI_12042021090251.pdf"


# ==========================================================================
# Synthetic PDF helpers — kept inline so tests are self-contained.
# Each fixture pads bulk text so the result clears MIN_FILE_BYTES (10 KB).
# ==========================================================================

def _make_pdf(
    header: str,
    body_lines: Optional[list[str]] = None,
    pages: int = 3,
    encrypted: bool = False,
    extra_pages_padding: bool = True,
) -> bytes:
    """Build a synthetic PDF. `header` lands on page 1; `body_lines`
    appears on every page. Padded with neutral text to clear 10 KB."""
    doc = pymupdf.open()
    body_lines = body_lines or []
    for p in range(pages):
        page = doc.new_page()
        y = 50.0
        if p == 0:
            for line in header.split("\n"):
                page.insert_text((50, y), line)
                y += 16
            y += 10
        for line in body_lines:
            page.insert_text((50, y), line)
            y += 14
        if extra_pages_padding:
            # Neutral filler so file size > MIN_FILE_BYTES. Different on
            # each page so PDF compression doesn't shrink it too much.
            for i in range(40):
                page.insert_text(
                    (50, y),
                    f"Page {p + 1} line {i}: neutral filler content xyz "
                    f"abcdefghij {p * 100 + i}.",
                )
                y += 12
                if y > 750:
                    break

    if encrypted:
        # PDF 2.0 AES-256. Owner password protects against re-saving;
        # user password is what makes pymupdf report needs_pass=True.
        return doc.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner_secret",
            user_pw="user_secret",
        )
    return doc.tobytes()


def _real_policy_text() -> str:
    """Header text dense with insurance signals — used as the positive-
    case synthetic fixture. Mirrors a realistic schedule cover page."""
    return (
        "POLICY SCHEDULE\n"
        "HDFC ERGO General Insurance Company Limited\n"
        "IRDAI Reg. No. 146\n"
        "Optima Restore — Family Floater Health Insurance Policy\n"
        "Policy No: HE-OR-23-9087421\n"
        "UIN: HDFHLIP21345V032021\n"
        "Period of Insurance: 01/04/2024 to 31/03/2025\n"
        "Sum Insured: ₹15,00,000 (Fifteen Lakh only)\n"
        "Annual Premium Payable: ₹22,400\n"
        "Insured Person: Mr Test User, Age 32\n"
        "Policyholder: Mr Test User\n"
        "Claim Settlement Ratio FY 2023-24: 95.6%\n"
        "Hospitalization benefits, in-patient and out-patient (OPD).\n"
        "Waiting period for pre-existing diseases: 3 years.\n"
        "Co-payment: 10% on metro cities. Renewal: lifetime.\n"
    )


# ==========================================================================
# Group 1 — Structural rejects (Stage 1)
# ==========================================================================

def test_non_pdf_bytes_rejects_with_invalid_pdf() -> None:
    r = preflight_check(b"This is not a PDF, just plain text. " * 500)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "invalid_pdf"
    assert r.score is None


def test_too_small_file_rejects() -> None:
    # PDF magic but truncated body
    r = preflight_check(b"%PDF-1.4\nshort\n")
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "pdf_too_small"


def test_encrypted_pdf_rejects_with_specific_error() -> None:
    pdf = _make_pdf("Sample header", pages=2, encrypted=True)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "encrypted_pdf"
    assert r.page_count >= 1


def test_too_many_pages_rejects() -> None:
    # Build a slim PDF with > MAX_PAGES pages — minimal content per page
    # to keep test runtime small.
    doc = pymupdf.open()
    for _ in range(MAX_PAGES + 5):
        page = doc.new_page()
        page.insert_text((50, 50), "x")
    pdf = doc.tobytes()
    doc.close()
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "pdf_too_many_pages"
    assert r.page_count == MAX_PAGES + 5


def test_zero_pages_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    """0-page PDFs are rare in the wild (pymupdf refuses to write them
    so we can't cleanly synthesize one), but the MIN_PAGES branch
    still needs coverage. Stub pymupdf.open to return a valid-shaped
    doc with page_count=0."""
    # Pad input bytes past MIN_FILE_BYTES (10 KB) so the size check
    # doesn't fire before page check.
    real_pdf = _make_pdf("dummy", pages=2, extra_pages_padding=True)
    assert len(real_pdf) > MIN_FILE_BYTES

    class _FakeDoc:
        page_count = 0
        needs_pass = False
        def close(self) -> None: pass

    from services.parser import preflight as pf
    monkeypatch.setattr(pf.pymupdf, "open", lambda **kw: _FakeDoc())

    r = preflight_check(real_pdf)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "pdf_too_few_pages"
    assert r.page_count == 0


# ==========================================================================
# Group 2 — Positive cases (should accept)
# ==========================================================================

def test_synthetic_policy_schedule_accepts_with_high_score() -> None:
    pdf = _make_pdf(_real_policy_text(), pages=2)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_ACCEPT, f"score={r.score} signals={r.signals}"
    assert r.score is not None and r.score >= 70


def test_synthetic_star_health_schedule_accepts() -> None:
    text = (
        "Star Health and Allied Insurance Co Ltd\n"
        "IRDAI Reg. No. 129\n"
        "Family Health Optima Insurance Plan\n"
        "Policy No: P/171210/01/2024/000123\n"
        "UIN: SHAHLIP19012V031819\n"
        "Sum Insured: ₹10,00,000\n"
        "Annual Premium: ₹18,500\n"
        "Period of Insurance: 15/06/2024 - 14/06/2025\n"
        "Insured: Test Family\n"
        "Hospitalization, OPD, ambulance benefits included.\n"
        "Co-payment: 20% for senior citizens.\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_ACCEPT, f"score={r.score} signals={r.signals}"


def test_synthetic_lic_term_policy_accepts() -> None:
    text = (
        "Life Insurance Corporation of India\n"
        "IRDAI Reg. No. 512\n"
        "LIC Tech Term Plan — Pure Term Insurance\n"
        "Policy No: 123456789\n"
        "UIN: 512N333V01\n"
        "Sum Assured: ₹1,00,00,000 (One Crore)\n"
        "Annual Premium Payable: ₹14,200\n"
        "Policy Period: 10/01/2024 to 10/01/2059\n"
        "Policyholder: Test User, Age 32, Non-smoker\n"
        "Nominee: Spouse\n"
        "Claim settlement ratio FY 2023-24: 98.4%\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_ACCEPT, f"score={r.score} signals={r.signals}"


def test_synthetic_bilingual_policy_accepts() -> None:
    """Hindi/English bilingual policy — Indian context dominates and
    English insurance vocab is enough to score well."""
    text = (
        "बीमा पॉलिसी / Insurance Policy\n"
        "ICICI Lombard General Insurance Co Ltd\n"
        "IRDAI Reg No 115\n"
        "Complete Health Insurance Policy\n"
        "Policy No: 4034i/HLT/12345/00\n"
        "UIN: ICIHLIP22013V032122\n"
        "Sum Insured: ₹5,00,000 (Pancha Lakh)\n"
        "Annual Premium: ₹16,000\n"
        "Period of Insurance: 01/05/2024 - 30/04/2025\n"
        "Insured Person / बीमित व्यक्ति: Test User\n"
        "Hospitalization, in-patient benefits.\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_ACCEPT, f"score={r.score} signals={r.signals}"


@pytest.mark.skipif(
    not OPTIMA_PDF.exists(),
    reason="Optima Restore PDF only present in dev environment",
)
def test_real_optima_restore_wording_accepts() -> None:
    """Dev-environment regression: the canonical reference PDF for
    parser dogfood. If this ever scores below 50, the algorithm
    regressed against real policy wordings."""
    r = preflight_check(OPTIMA_PDF.read_bytes())
    assert r.outcome == OUTCOME_ACCEPT, f"score={r.score} signals={r.signals}"
    # Wording-only doc has no schedule fields → structure signal often
    # 0; total still >= 60 from vocab + regulatory + brand.
    assert r.score is not None and r.score >= 60


@pytest.mark.skipif(
    not EBID_PDF.exists(),
    reason="eBID life-insurance PDF only present in dev environment",
)
def test_real_ebid_life_illustration_accepts() -> None:
    """Real benefit-illustration PDF. Lighter on vocab than a wording
    but still scores >= ACCEPT threshold thanks to the life-insurer
    canonical name + IRDAI + structure regexes."""
    r = preflight_check(EBID_PDF.read_bytes())
    assert r.outcome == OUTCOME_ACCEPT, f"score={r.score} signals={r.signals}"
    assert r.score is not None and r.score >= SCORE_ACCEPT


# ==========================================================================
# Group 3 — Negative cases (should reject with detected_type_hint)
# ==========================================================================

def test_resume_pdf_rejects_with_hint() -> None:
    text = (
        "CURRICULUM VITAE\n"
        "John Doe — Senior Software Engineer\n"
        "10 years of experience in Python, Django, React\n"
        "Education: B.Tech Computer Science\n"
        "Work Experience: Google, Microsoft\n"
        "Skills: distributed systems, machine learning\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "resume"


def test_bank_statement_pdf_rejects_with_hint() -> None:
    text = (
        "BANK STATEMENT — HDFC Bank\n"
        "Account Statement for Account No 12345678\n"
        "Statement Period: 01/06/2024 to 30/06/2024\n"
        "Transaction History\n"
        "Opening Balance: 50000\n"
        "Closing Balance: 75000\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "bank_statement"


def test_random_doc_with_no_insurance_signals_rejects() -> None:
    text = (
        "A Brief History of Time\n"
        "by Stephen Hawking\n"
        "Chapter One: Our Picture of the Universe\n"
        "The nature of stars, the formation of galaxies\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_REJECT
    # No specific negative term fired — hint defaults to "unknown".
    assert r.detected_type_hint == "unknown"
    assert r.score is not None and r.score < SCORE_BORDERLINE


def test_gst_invoice_without_insurance_terms_rejects() -> None:
    text = (
        "GST INVOICE\n"
        "Invoice No: INV-2024-12345\n"
        "Vendor: ABC Corp Ltd\n"
        "GSTIN: 27ABCDE1234F1Z5\n"
        "Amount: ₹50,000 plus 18% GST\n"
        "Total Payable: ₹59,000\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "invoice"


def test_loan_agreement_rejects_with_hint() -> None:
    text = (
        "LOAN AGREEMENT\n"
        "Loan Sanction Letter\n"
        "Borrower: Test User\n"
        "Lender: Test Bank Ltd\n"
        "Principal Amount: ₹10,00,000\n"
        "Tenure: 60 months\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "loan_agreement"


# ==========================================================================
# Group 4 — Edge cases
# ==========================================================================

def test_image_only_pdf_skips_to_claude() -> None:
    """PDF with no text layer (e.g., scanned image). pymupdf returns
    minimal/no text — preflight defers rather than risking false reject."""
    doc = pymupdf.open()
    page = doc.new_page()
    # Insert an actual image rectangle (no text). Padding bytes for size.
    page.draw_rect(pymupdf.Rect(50, 50, 500, 700), fill=(0.9, 0.9, 0.9))
    pdf = doc.tobytes() + b"\n%padding " * 5000
    doc.close()
    # Re-validate with pymupdf to confirm low text content
    check = pymupdf.open(stream=pdf, filetype="pdf")
    text_len = sum(len(check[i].get_text()) for i in range(check.page_count))
    check.close()
    assert text_len < 100, f"fixture has too much text ({text_len}) for this test"

    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_SKIPPED
    assert r.has_text_layer is False
    assert r.score is None


def test_borderline_band_marked_borderline_not_rejected() -> None:
    """A doc with some insurance vocab but missing brand/regulatory
    signals lands in 30-49 — preflight defers rather than reject."""
    text = (
        "POLICY DOCUMENT\n"
        "This is a policy with coverage and benefits and exclusions.\n"
        "Premium and renewal terms apply.\n"
    )
    pdf = _make_pdf(text)
    r = preflight_check(pdf)
    # Could be accept or borderline depending on regex hits — we don't
    # assert exact band, but assert it doesn't reject (the humility band
    # philosophy: when in doubt, defer).
    assert r.outcome in (OUTCOME_ACCEPT, OUTCOME_BORDERLINE), (
        f"expected accept or borderline; got {r.outcome} score={r.score} "
        f"signals={r.signals}"
    )


def test_resume_word_in_body_doesnt_trigger_negative() -> None:
    """Negative indicators only check first 500 chars. A real policy
    that mentions 'resume coverage' deep in body shouldn't be flagged."""
    head = _real_policy_text()
    # Pad header to push 'resume' word past 500-char window.
    body = ["Coverage will resume after waiting period elapses."] * 20
    pdf = _make_pdf(head, body_lines=body)
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_ACCEPT
    assert r.detected_type_hint is None
    # Negative signal must be 0 — head doesn't contain "resume"
    assert r.signals.get("negative", 0) == 0


def test_empty_pdf_skips_to_claude() -> None:
    """Valid PDF structure, zero text content → defer (don't reject)."""
    doc = pymupdf.open()
    for _ in range(2):
        doc.new_page()  # blank page
    pdf = doc.tobytes() + b"\n%pad " * 5000
    doc.close()
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_SKIPPED
    assert r.has_text_layer is False


def test_performance_under_1s_on_large_pdf() -> None:
    """80-page wording-style document must complete preflight in <1s."""
    text = _real_policy_text()
    body = ["Coverage details, exclusions, definitions section." for _ in range(20)]
    pdf = _make_pdf(text, body_lines=body, pages=80)
    started = time.perf_counter()
    r = preflight_check(pdf)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert elapsed_ms < 1000, f"preflight took {elapsed_ms:.0f}ms; budget 1000ms"
    assert r.elapsed_ms < 1000


def test_random_non_insurance_never_exceeds_borderline() -> None:
    """Sanity: a few unrelated documents should never accidentally
    pass the SCORE_BORDERLINE threshold without insurance terms."""
    samples = [
        "Recipe for chocolate cake. Ingredients: flour, sugar, butter.",
        "User Manual — Toaster Model 4500. Operating instructions.",
        "Meeting minutes from board meeting on quarterly review.",
        "Syllabus — Introduction to Computer Science. Course outline.",
    ]
    for text in samples:
        pdf = _make_pdf(text)
        r = preflight_check(pdf)
        if r.outcome == OUTCOME_SKIPPED:
            continue  # too little text to score
        assert r.score is not None
        assert r.score < SCORE_BORDERLINE, (
            f"unrelated doc unexpectedly scored {r.score}: {text[:40]!r} "
            f"signals={r.signals}"
        )


# ==========================================================================
# PreflightResult dataclass invariants
# ==========================================================================

def test_preflight_result_is_frozen() -> None:
    """The dataclass is frozen so callers can't accidentally mutate
    cached results (defensive — we don't currently cache, but might)."""
    pdf = _make_pdf(_real_policy_text())
    r = preflight_check(pdf)
    with pytest.raises((AttributeError, Exception)):
        r.score = 999  # type: ignore[misc]


def test_missing_pymupdf_degrades_to_skipped_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If pymupdf is unavailable at runtime (broken install, OS-specific
    wheel issue), preflight must return OUTCOME_SKIPPED for any
    structurally-valid PDF rather than raising — Claude is the safety
    net. Verifies the pymupdf-availability gate added because the
    naked module-top import would otherwise crash the whole FastAPI
    app at startup."""
    from services.parser import preflight as pf
    monkeypatch.setattr(pf, "_PYMUPDF_AVAILABLE", False)
    pdf = _make_pdf(_real_policy_text())
    r = preflight_check(pdf)
    assert r.outcome == OUTCOME_SKIPPED
    assert r.score is None
    assert r.has_text_layer is False


def test_missing_pymupdf_still_catches_byte_level_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 1a (byte-level) checks don't need pymupdf. Even with the
    library unavailable, obviously-not-a-PDF input still gets a
    structural reject — we don't lose ALL validation."""
    from services.parser import preflight as pf
    monkeypatch.setattr(pf, "_PYMUPDF_AVAILABLE", False)
    r = preflight_check(b"not a pdf at all" * 1000)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "invalid_pdf"


def test_outcome_values_are_strings() -> None:
    """outcome must be one of the declared constants — a typo would
    break the rate-limit query that filters on these values."""
    pdf = _make_pdf(_real_policy_text())
    r = preflight_check(pdf)
    assert isinstance(r.outcome, str)
    assert r.outcome in {
        OUTCOME_ACCEPT, OUTCOME_BORDERLINE, OUTCOME_REJECT,
        OUTCOME_SKIPPED, OUTCOME_STRUCTURAL,
    }
