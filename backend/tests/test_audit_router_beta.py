"""Route-level tests for the beta gate on POST /api/audit/generate.

Uses FastAPI TestClient with a FakeDb stand-in for Mongo and a
dependency override to bypass the OTP/JWT cookie auth flow.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterator

import pytest

# Set required env BEFORE importing the FastAPI app so module-level reads
# (USE_MOCKS, JWT_SECRET) pick up sane test values.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "kavach_test")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod" * 2)
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient   # noqa: E402

from auth import get_current_user, verify_csrf  # noqa: E402
from server import app                          # noqa: E402
from services import beta as beta_mod           # noqa: E402
from tests._fake_mongo import FakeDb            # noqa: E402


TEST_USER_ID = "test-user-1"


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Fresh fake-db + cleared beta cache + auth bypass for every test."""
    fake = FakeDb()
    # Seed a user record so the real-engine path doesn't 404 in tests
    # that flip to real mode.
    fake.users.docs.append({
        "id": TEST_USER_ID, "mobile": "9999999999",
        "age": 32, "city": "Mumbai", "tier": "tier-1",
        "income": 1_500_000,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    app.state.db = fake
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": TEST_USER_ID, "mobile": "9999999999",
    }
    app.dependency_overrides[verify_csrf] = lambda: None
    beta_mod._cache_clear()
    yield
    app.dependency_overrides.clear()
    beta_mod._cache_clear()


def _client() -> TestClient:
    return TestClient(app)


# ---------- Truth table ----------

def test_no_param_returns_mock_for_non_beta_user() -> None:
    """USE_MOCKS=true + no beta param + non-beta user → mock engine, beta_invocation=false."""
    client = _client()
    r = client.post("/api/audit/generate")
    assert r.status_code == 200, r.text
    audit = r.json()["data"]["audit"]
    assert audit["engine_mode"] == "mock"
    assert audit["beta_invocation"] is False


def test_no_param_returns_mock_for_beta_user_too() -> None:
    """Default-safe: even beta user gets mock without explicit ?beta opt-in."""
    fake: FakeDb = app.state.db
    fake.beta_allowlist.docs.append({
        "user_id": TEST_USER_ID, "feature": "audit-real",
        "added_by": "admin", "notes": None,
    })
    r = _client().post("/api/audit/generate")
    audit = r.json()["data"]["audit"]
    assert audit["engine_mode"] == "mock"
    assert audit["beta_invocation"] is False


def test_beta_param_for_non_beta_user_still_returns_mock() -> None:
    """Critical safety: ?beta=audit-real on a non-allowlisted user must
    fall through to mock — the engine MUST NOT serve real output to a
    user not in the allowlist, even if they pass the magic param."""
    r = _client().post("/api/audit/generate?beta=audit-real")
    audit = r.json()["data"]["audit"]
    assert audit["engine_mode"] == "mock"
    assert audit["beta_invocation"] is False


def test_beta_param_for_beta_user_returns_real_engine() -> None:
    fake: FakeDb = app.state.db
    fake.beta_allowlist.docs.append({
        "user_id": TEST_USER_ID, "feature": "audit-real",
        "added_by": "admin", "notes": None,
    })
    r = _client().post("/api/audit/generate?beta=audit-real")
    assert r.status_code == 200, r.text
    audit = r.json()["data"]["audit"]
    assert audit["engine_mode"] == "real"
    assert audit["beta_invocation"] is True
    # Real engine produces these fields; mock doesn't:
    assert "data_version" in audit
    assert "engine_ms" in audit


def test_invalid_beta_param_falls_through_to_mock() -> None:
    """?beta=garbage doesn't match any feature → mock."""
    fake: FakeDb = app.state.db
    fake.beta_allowlist.docs.append({
        "user_id": TEST_USER_ID, "feature": "audit-real",
        "added_by": "admin", "notes": None,
    })
    r = _client().post("/api/audit/generate?beta=garbage")
    audit = r.json()["data"]["audit"]
    assert audit["engine_mode"] == "mock"
    assert audit["beta_invocation"] is False


def test_wrong_feature_param_falls_through_to_mock() -> None:
    """?beta=parser-real on the audit endpoint → mock (param doesn't match feature)."""
    fake: FakeDb = app.state.db
    fake.beta_allowlist.docs.append({
        "user_id": TEST_USER_ID, "feature": "parser-real",
        "added_by": "admin", "notes": None,
    })
    r = _client().post("/api/audit/generate?beta=parser-real")
    audit = r.json()["data"]["audit"]
    assert audit["engine_mode"] == "mock"


# ---------- Mongo write verification ----------

def test_audit_row_written_with_observability_fields_for_mock() -> None:
    _client().post("/api/audit/generate")
    fake: FakeDb = app.state.db
    rows = fake.audits.docs
    assert len(rows) == 1
    assert rows[0]["engine_mode"] == "mock"
    assert rows[0]["beta_invocation"] is False
    assert rows[0]["user_id"] == TEST_USER_ID


def test_audit_row_written_with_observability_fields_for_real_via_beta() -> None:
    fake: FakeDb = app.state.db
    fake.beta_allowlist.docs.append({
        "user_id": TEST_USER_ID, "feature": "audit-real",
        "added_by": "admin", "notes": None,
    })
    _client().post("/api/audit/generate?beta=audit-real")
    rows = fake.audits.docs
    assert len(rows) == 1
    assert rows[0]["engine_mode"] == "real"
    assert rows[0]["beta_invocation"] is True


# ---------- Backward-compat: GET /audit/latest still works ----------

def test_get_latest_returns_stored_row_unchanged() -> None:
    """The new engine_mode + beta_invocation fields are extras; the
    existing GET /audit/latest contract still returns the stored shape."""
    _client().post("/api/audit/generate")
    r = _client().get("/api/audit/latest")
    assert r.status_code == 200
    audit = r.json()["data"]["audit"]
    assert audit is not None
    # Original mock-shape fields the frontend reads — none broken
    assert "scores" in audit
    assert "findings" in audit
    assert "portfolio" in audit
    # New extras present (forward-compat for analytics)
    assert audit["engine_mode"] == "mock"
    assert audit["beta_invocation"] is False


def test_get_latest_returns_null_when_no_audits() -> None:
    """No auto-generate (Phase 2B change). GET on a fresh user → null."""
    r = _client().get("/api/audit/latest")
    assert r.status_code == 200
    assert r.json()["data"]["audit"] is None
