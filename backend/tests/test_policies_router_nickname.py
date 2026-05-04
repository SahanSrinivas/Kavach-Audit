"""Route-level tests for the policy_nickname feature on POST /api/policies/upload.

Covers the four contract pieces:
  1. Schema — nickname round-trips through Policy.from_dict / to_dict
  2. Endpoint — accepts nickname multipart field, normalizes whitespace,
     enforces 60-char cap, requires-when-N>=1
  3. Storage — nickname lands in the stored policy doc + response
  4. Mock branch — also stamps policy_nickname (so frontend behavior is
     identical regardless of USE_MOCKS)
"""
from __future__ import annotations

import io
import os
from typing import Iterator

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
from services.audit.types import Policy           # noqa: E402
from tests._fake_mongo import FakeDb              # noqa: E402


TEST_USER_ID = "test-user-nickname"


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    fake = FakeDb()
    app.state.db = fake
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": TEST_USER_ID, "mobile": "9999999999",
    }
    app.dependency_overrides[verify_csrf] = lambda: None
    # Skip the 4-second mock parse delay — keeps tests fast
    async def _no_sleep(_sec: float) -> None:
        return None
    monkeypatch.setattr("routers.policies_router.asyncio.sleep", _no_sleep)
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _upload(
    client: TestClient,
    *,
    filename: str = "policy.pdf",
    nickname: str | None = None,
    pdf_bytes: bytes = b"%PDF-1.4 dummy bytes",
) -> object:
    files = {"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    data = {}
    if nickname is not None:
        data["nickname"] = nickname
    return client.post("/api/policies/upload", files=files, data=data)


# ==========================================================================
# 1. Schema — Policy.from_dict round-trips policy_nickname
# ==========================================================================

def test_policy_from_dict_preserves_nickname() -> None:
    p = Policy.from_dict({
        "id": "p1", "type": "health", "insurer": "HDFC ERGO General",
        "sum_insured": 1_000_000, "premium": 20_000,
        "policy_nickname": "Father's policy",
    })
    assert p.policy_nickname == "Father's policy"


def test_policy_from_dict_defaults_nickname_to_none_when_absent() -> None:
    p = Policy.from_dict({
        "id": "p1", "type": "health", "insurer": "HDFC ERGO General",
        "sum_insured": 1_000_000, "premium": 20_000,
    })
    assert p.policy_nickname is None


# ==========================================================================
# 2. Endpoint — first upload (no existing policies) → nickname OPTIONAL
# ==========================================================================

def test_first_upload_without_nickname_succeeds() -> None:
    """First-ever policy upload doesn't require a nickname.
    Honors 'Required if user has more than one policy already' literally."""
    r = _upload(_client())
    assert r.status_code == 200, r.text
    pol = r.json()["data"]["policy"]
    assert pol["policy_nickname"] is None


def test_first_upload_with_nickname_stores_it() -> None:
    r = _upload(_client(), nickname="Father's policy")
    assert r.status_code == 200, r.text
    pol = r.json()["data"]["policy"]
    assert pol["policy_nickname"] == "Father's policy"


# ==========================================================================
# 2 cont. — N+1 upload (existing policies present) → nickname REQUIRED
# ==========================================================================

def test_second_upload_without_nickname_returns_400() -> None:
    """User has at least one prior policy → nickname required."""
    fake: FakeDb = app.state.db
    fake.policies.docs.append({"id": "old1", "user_id": TEST_USER_ID})
    r = _upload(_client())   # no nickname
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("error") == "nickname_required"


def test_second_upload_with_nickname_succeeds() -> None:
    fake: FakeDb = app.state.db
    fake.policies.docs.append({"id": "old1", "user_id": TEST_USER_ID})
    r = _upload(_client(), nickname="My new HDFC plan")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["policy"]["policy_nickname"] == "My new HDFC plan"


# ==========================================================================
# 2 cont. — normalization
# ==========================================================================

def test_whitespace_only_nickname_treated_as_none_first_upload() -> None:
    """Empty/whitespace nickname → server treats as None (no '' stored)."""
    r = _upload(_client(), nickname="   ")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["policy"]["policy_nickname"] is None


def test_whitespace_only_nickname_fails_when_required() -> None:
    """Whitespace doesn't satisfy the requires-N>=1 check."""
    fake: FakeDb = app.state.db
    fake.policies.docs.append({"id": "old1", "user_id": TEST_USER_ID})
    r = _upload(_client(), nickname="   ")
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "nickname_required"


def test_nickname_with_surrounding_whitespace_is_stripped() -> None:
    r = _upload(_client(), nickname="  Father's policy  ")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["policy"]["policy_nickname"] == "Father's policy"


# ==========================================================================
# 2 cont. — length cap
# ==========================================================================

def test_nickname_exactly_60_chars_accepted() -> None:
    nick = "a" * 60
    r = _upload(_client(), nickname=nick)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["policy"]["policy_nickname"] == nick


def test_nickname_61_chars_rejected_with_clear_error() -> None:
    """Server-side cap enforced at 60 chars (matches frontend maxLength)."""
    nick = "a" * 61
    r = _upload(_client(), nickname=nick)
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("error") == "nickname_too_long"
    # Error message names the exact length so debugging is easy
    assert "60" in detail.get("message", "")
    assert "61" in detail.get("message", "")


# ==========================================================================
# 3. Storage — written to db.policies with the nickname
# ==========================================================================

def test_nickname_persists_to_mongo() -> None:
    _upload(_client(), nickname="Father's policy")
    fake: FakeDb = app.state.db
    rows = fake.policies.docs
    assert len(rows) == 1
    assert rows[0]["policy_nickname"] == "Father's policy"


# ==========================================================================
# 4. Mock branch behavior parity
# ==========================================================================

def test_mock_branch_stamps_policy_nickname_field() -> None:
    """USE_MOCKS=true path also includes policy_nickname so the frontend
    sees a consistent shape regardless of mode."""
    r = _upload(_client(), nickname="Office cover")
    pol = r.json()["data"]["policy"]
    assert "policy_nickname" in pol
    assert pol["policy_nickname"] == "Office cover"
    # parser_mode confirms we exercised the mock branch
    assert pol["parser_mode"] == "mock"


def test_mock_branch_first_upload_nickname_null_in_response() -> None:
    r = _upload(_client())
    pol = r.json()["data"]["policy"]
    assert pol["policy_nickname"] is None
    assert pol["parser_mode"] == "mock"


# ==========================================================================
# Edge: validation runs BEFORE expensive parse work
# ==========================================================================

def test_nickname_validation_runs_before_rate_limit_or_parse() -> None:
    """Nickname check is on the hot path before the parse call. Even if
    USE_MOCKS=true (which sleeps 4s normally), 400 should return fast."""
    fake: FakeDb = app.state.db
    fake.policies.docs.append({"id": "old1", "user_id": TEST_USER_ID})
    r = _upload(_client(), nickname="x" * 100)  # too long AND nickname-required
    assert r.status_code == 400
    # Length check fires first (it's earlier in the function)
    assert r.json()["detail"]["error"] == "nickname_too_long"
    # The parse_attempts collection was NOT touched (validation short-circuited)
    assert len(fake.parse_attempts.docs) == 0
    # No new policies stored
    assert len(fake.policies.docs) == 1   # only the seed
