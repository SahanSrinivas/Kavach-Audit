"""Life preflight scoring and structural guards (services.life.preflight)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest

import services.life.preflight as life_pf
from services.life.preflight import (
    OUTCOME_ACCEPT,
    OUTCOME_BORDERLINE,
    OUTCOME_REJECT,
    OUTCOME_SKIPPED,
    OUTCOME_STRUCTURAL,
    PDF_MAGIC,
    SCORE_ACCEPT_LIFE,
    SCORE_BORDERLINE_LIFE,
    preflight_check_life,
)
from tests.life_preflight_fixtures import (
    accept_shape_life_pdf,
    bank_statement_pdf,
    blank_pages_no_text_pdf,
    borderline_band_life_pdf,
    eighty_page_accept_life_pdf,
    invalid_magic_bytes_payload,
    invoice_pdf_no_guards_head,
    oversized_page_count_pdf,
    resume_pdf,
    strong_vocab_life_pdf,
    structural_too_small_bytes,
)

pytestmark = pytest.mark.skipif(
    not life_pf._PYMUPDF_AVAILABLE,
    reason="pymupdf required for life preflight tests",
)


def test_life_policy_pdf_accepts() -> None:
    raw = accept_shape_life_pdf()
    r = preflight_check_life(raw)
    assert r.outcome == OUTCOME_ACCEPT
    assert r.score is not None and r.score >= SCORE_ACCEPT_LIFE


def test_life_policy_with_strong_vocab_accepts_high_score() -> None:
    raw = strong_vocab_life_pdf()
    r = preflight_check_life(raw)
    assert r.outcome == OUTCOME_ACCEPT
    assert r.score is not None and r.score >= 72
    assert r.signals.get("vocab") == life_pf.VOCAB_TOTAL_CAP
    assert r.signals.get("brand") >= 14
    assert r.signals.get("regulatory") >= 18


def test_life_policy_borderline_proceeds() -> None:
    raw = borderline_band_life_pdf()
    r = preflight_check_life(raw)
    assert r.outcome == OUTCOME_BORDERLINE
    assert r.score is not None
    assert SCORE_BORDERLINE_LIFE <= r.score < SCORE_ACCEPT_LIFE


def test_resume_rejects() -> None:
    r = preflight_check_life(resume_pdf())
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "resume"


def test_bank_statement_rejects() -> None:
    r = preflight_check_life(bank_statement_pdf())
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "bank_statement"


def test_invoice_rejects() -> None:
    r = preflight_check_life(invoice_pdf_no_guards_head())
    assert r.outcome == OUTCOME_REJECT
    assert r.detected_type_hint == "invoice"


def test_scanned_pdf_skipped() -> None:
    r = preflight_check_life(blank_pages_no_text_pdf())
    assert r.outcome == OUTCOME_SKIPPED


def test_pdf_too_small_structural() -> None:
    raw = structural_too_small_bytes()
    assert raw.startswith(PDF_MAGIC)
    assert len(raw) < life_pf.MIN_FILE_BYTES
    r = preflight_check_life(raw)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "pdf_too_small"


def test_pdf_too_many_pages_structural() -> None:
    r = preflight_check_life(oversized_page_count_pdf(pages=200))
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "pdf_too_many_pages"


def test_invalid_magic_bytes_structural() -> None:
    payload = invalid_magic_bytes_payload()
    assert not payload.startswith(PDF_MAGIC)
    r = preflight_check_life(payload)
    assert r.outcome == OUTCOME_STRUCTURAL
    assert r.error == "invalid_pdf"


def test_preflight_completes_under_1s() -> None:
    raw = eighty_page_accept_life_pdf()
    r = preflight_check_life(raw)
    assert r.elapsed_ms < 1000
    assert r.outcome == OUTCOME_ACCEPT
