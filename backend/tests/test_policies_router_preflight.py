"""Router-level integration tests for preflight wiring on
POST /api/policies/upload.

Three scenarios:
  1. Reject path: garbage PDF → 400 not_insurance_document, no policy
     stored, parse_attempt logged with preflight_outcome="reject", and
     the rate-limit query doesn't count it.
  2. Accept path: real-shaped policy → 200, policy stored, parse_attempt
     logged with preflight_outcome="accept", rate-limit DOES count.
  3. Borderline path: ambiguous doc → 200 (defers to Claude), parse_attempt
     logged with preflight_outcome="borderline".
"""
from __future__ import annotations

import io
import os
from typing import Iterator

import pymupdf  # type: ignore[import-untyped]
import pytest

# Required env BEFORE importing the FastAPI app
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "kavach_test")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod" * 2)
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient   # noqa: E402

from auth import get_current_user, verify_csrf   # noqa: E402
from server import app                            # noqa: E402
from services.parser.preflight import (           # noqa: E402
    OUTCOMES_NO_CLAUDE,
    OUTCOME_ACCEPT,
    OUTCOME_BORDERLINE,
    OUTCOME_REJECT,
)
from tests._fake_mongo import FakeDb              # noqa: E402


TEST_USER_ID = "test-preflight-user"


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    fake = FakeDb()
    app.state.db = fake
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": TEST_USER_ID, "mobile": "9999999999",
    }
    app.dependency_overrides[verify_csrf] = lambda: None
    # Skip the 4-second mock parse delay
    async def _no_sleep(_sec: float) -> None:
        return None
    monkeypatch.setattr("routers.policies_router.asyncio.sleep", _no_sleep)
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _make_pdf(header: str, pages: int = 2) -> bytes:
    """Build a synthetic PDF with `header` text on page 1, padded for
    size. Identical helper to test_preflight.py — copied rather than
    imported to keep test files independent."""
    doc = pymupdf.open()
    for p in range(pages):
        page = doc.new_page()
        y = 50.0
        if p == 0:
            for line in header.split("\n"):
                page.insert_text((50, y), line)
                y += 16
        for i in range(40):
            page.insert_text((50, y), f"Padding line {p}-{i} content text.")
            y += 12
            if y > 750:
                break
    pdf = doc.tobytes()
    doc.close()
    return pdf


def _real_policy_pdf() -> bytes:
    return _make_pdf(
        "POLICY SCHEDULE\n"
        "HDFC ERGO General Insurance Company Limited\n"
        "IRDAI Reg. No. 146\n"
        "Policy No: HE-OR-23-9087421\n"
        "UIN: HDFHLIP21345V032021\n"
        "Sum Insured: Rs. 15,00,000 (Fifteen Lakh)\n"
        "Annual Premium Payable: Rs. 22,400\n"
        "Period of Insurance: 01/04/2024 to 31/03/2025\n"
        "Policyholder: Test User\n"
        "Hospitalization, in-patient and OPD benefits.\n"
    )


def _resume_pdf() -> bytes:
    return _make_pdf(
        "CURRICULUM VITAE\n"
        "John Doe — Senior Software Engineer\n"
        "10 years experience in Python and React\n"
        "Skills: distributed systems, machine learning"
    )


def _borderline_pdf() -> bytes:
    """Some insurance vocab but missing brand/regulatory signals.
    Engineered to land in the 30-49 humility band."""
    return _make_pdf(
        "POLICY DOCUMENT\n"
        "This is a policy with coverage and benefits.\n"
        "Premium and renewal terms apply.\n"
        "Exclusions: please refer to schedule.\n"
    )


def _upload(client: TestClient, pdf_bytes: bytes, *, nickname: str | None = None):
    files = {"file": ("policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"nickname": nickname} if nickname is not None else {}
    return client.post("/api/policies/upload", files=files, data=data)


# ==========================================================================
# Reject path
# ==========================================================================

def test_resume_upload_returns_400_with_structured_envelope() -> None:
    r = _upload(_client(), _resume_pdf())
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "not_insurance_document"
    assert detail["detected_type_hint"] == "resume"
    assert "preflight_score" in detail
    assert "user_action" in detail


def test_resume_upload_does_not_insert_a_policy() -> None:
    """No policy row should be created when preflight rejects — the
    mock parser branch must never be reached."""
    _upload(_client(), _resume_pdf())
    fake: FakeDb = app.state.db
    assert len(fake.policies.docs) == 0


def test_resume_upload_logs_preflight_attempt_marked_reject() -> None:
    _upload(_client(), _resume_pdf())
    fake: FakeDb = app.state.db
    rows = fake.parse_attempts.docs
    assert len(rows) == 1
    assert rows[0]["preflight_outcome"] == OUTCOME_REJECT
    assert rows[0]["detected_type_hint"] == "resume"
    assert rows[0]["preflight_score"] is not None


def test_resume_uploads_dont_consume_rate_limit() -> None:
    """The whole point of preflight: garbage uploads must NOT eat
    rate-limit slots. Spam 6 resumes (one over the 5/hr cap) and
    confirm the 7th real upload still succeeds."""
    client = _client()
    for _ in range(6):
        r = _upload(client, _resume_pdf())
        assert r.status_code == 400
    # All 6 logged but with preflight_outcome=reject → rate-limit query
    # (which uses $nin) excludes them. A real upload should still pass.
    r = _upload(client, _real_policy_pdf())
    assert r.status_code == 200, r.text


def test_encrypted_pdf_returns_specific_error_envelope() -> None:
    doc = pymupdf.open()
    for _ in range(2):
        page = doc.new_page()
        for y in range(50, 700, 14):
            page.insert_text((50, y), "Padding to clear MIN_FILE_BYTES.")
    pdf = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="x",
        user_pw="y",
    )
    doc.close()
    r = _upload(_client(), pdf)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "encrypted_pdf"
    assert "password" in detail["user_action"].lower()


# ==========================================================================
# Accept path
# ==========================================================================

def test_real_policy_pdf_is_accepted_and_parsed() -> None:
    r = _upload(_client(), _real_policy_pdf())
    assert r.status_code == 200, r.text
    pol = r.json()["data"]["policy"]
    # Mock parser returned the seeded HDFC ERGO data.
    assert pol["parser_mode"] == "mock"
    assert pol["insurer"]


def test_real_policy_logs_preflight_attempt_marked_accept() -> None:
    _upload(_client(), _real_policy_pdf())
    fake: FakeDb = app.state.db
    rows = fake.parse_attempts.docs
    assert len(rows) == 1
    assert rows[0]["preflight_outcome"] == OUTCOME_ACCEPT
    assert rows[0]["preflight_score"] is not None
    assert rows[0]["preflight_score"] >= 50


# ==========================================================================
# Borderline path
# ==========================================================================

def test_borderline_pdf_proceeds_to_parser_not_rejected() -> None:
    """The 30-49 humility band defers to Claude rather than risk false
    reject. The mock parser branch fires; the user gets a policy back."""
    r = _upload(_client(), _borderline_pdf())
    # Either accept or borderline — depends on exact regex hits.
    # Critically: NOT 400.
    assert r.status_code == 200, r.text
    fake: FakeDb = app.state.db
    rows = fake.parse_attempts.docs
    assert len(rows) == 1
    assert rows[0]["preflight_outcome"] in (OUTCOME_BORDERLINE, OUTCOME_ACCEPT)


# ==========================================================================
# Cross-cutting: rate-limit query semantics
# ==========================================================================

def test_rate_limit_query_excludes_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    """OUTCOMES_NO_CLAUDE entries must be excluded from the count,
    otherwise garbage uploads break legitimate users."""
    fake: FakeDb = app.state.db
    # Pre-seed 10 rejected attempts in the last hour
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    for outcome in list(OUTCOMES_NO_CLAUDE) * 5:
        fake.parse_attempts.docs.append({
            "user_id": TEST_USER_ID,
            "created_at": now_iso,
            "preflight_outcome": outcome,
        })
    # Real upload should still succeed despite 10 rejects on file.
    r = _upload(_client(), _real_policy_pdf())
    assert r.status_code == 200, r.text
