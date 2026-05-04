"""Route-level tests for /api/admin/beta-allowlist CRUD."""
from __future__ import annotations

import os
from typing import Iterator

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "kavach_test")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod" * 2)
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")
ADMIN_TOKEN = os.environ["ADMIN_PASSWORD"]

from fastapi.testclient import TestClient   # noqa: E402

from server import app                      # noqa: E402
from services import beta as beta_mod       # noqa: E402
from tests._fake_mongo import FakeDb        # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    fake = FakeDb()
    app.state.db = fake
    beta_mod._cache_clear()
    yield
    beta_mod._cache_clear()


def _client() -> TestClient:
    return TestClient(app)


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ---------- Auth ----------

def test_add_without_auth_returns_401() -> None:
    r = _client().post("/api/admin/beta-allowlist",
                       json={"user_id": "u1", "feature": "audit-real"})
    assert r.status_code == 401


def test_add_with_wrong_token_returns_401() -> None:
    r = _client().post(
        "/api/admin/beta-allowlist",
        json={"user_id": "u1", "feature": "audit-real"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_remove_without_auth_returns_401() -> None:
    r = _client().request(
        "DELETE", "/api/admin/beta-allowlist",
        json={"user_id": "u1", "feature": "audit-real"},
    )
    assert r.status_code == 401


def test_list_without_auth_returns_401() -> None:
    r = _client().get("/api/admin/beta-allowlist")
    assert r.status_code == 401


# ---------- Add ----------

def test_admin_can_add_user() -> None:
    r = _client().post(
        "/api/admin/beta-allowlist",
        json={"user_id": "u1", "feature": "audit-real", "notes": "founder"},
        headers=_admin_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["data"]["entry"]["user_id"] == "u1"
    assert body["data"]["entry"]["feature"] == "audit-real"
    assert body["data"]["entry"]["notes"] == "founder"
    assert body["data"]["entry"]["added_by"] == "admin"
    fake: FakeDb = app.state.db
    assert len(fake.beta_allowlist.docs) == 1


def test_admin_add_invalid_feature_returns_400() -> None:
    r = _client().post(
        "/api/admin/beta-allowlist",
        json={"user_id": "u1", "feature": "garbage"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
    assert "invalid_feature" in r.text


def test_admin_add_duplicate_returns_409() -> None:
    c = _client()
    c.post("/api/admin/beta-allowlist",
           json={"user_id": "u1", "feature": "audit-real"},
           headers=_admin_headers())
    r = c.post("/api/admin/beta-allowlist",
               json={"user_id": "u1", "feature": "audit-real"},
               headers=_admin_headers())
    assert r.status_code == 409
    assert "already_allowlisted" in r.text


# ---------- List ----------

def test_admin_can_list_all() -> None:
    c = _client()
    c.post("/api/admin/beta-allowlist",
           json={"user_id": "u1", "feature": "audit-real"},
           headers=_admin_headers())
    c.post("/api/admin/beta-allowlist",
           json={"user_id": "u2", "feature": "parser-real"},
           headers=_admin_headers())
    r = c.get("/api/admin/beta-allowlist", headers=_admin_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["count"] == 2


def test_admin_can_filter_list_by_feature() -> None:
    c = _client()
    c.post("/api/admin/beta-allowlist",
           json={"user_id": "u1", "feature": "audit-real"},
           headers=_admin_headers())
    c.post("/api/admin/beta-allowlist",
           json={"user_id": "u2", "feature": "parser-real"},
           headers=_admin_headers())
    r = c.get("/api/admin/beta-allowlist?feature=audit-real",
              headers=_admin_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["count"] == 1
    assert body["data"]["entries"][0]["user_id"] == "u1"


def test_admin_list_invalid_feature_returns_400() -> None:
    r = _client().get("/api/admin/beta-allowlist?feature=garbage",
                      headers=_admin_headers())
    assert r.status_code == 400


# ---------- Remove ----------

def test_admin_can_remove_user() -> None:
    c = _client()
    c.post("/api/admin/beta-allowlist",
           json={"user_id": "u1", "feature": "audit-real"},
           headers=_admin_headers())
    r = c.request(
        "DELETE", "/api/admin/beta-allowlist",
        json={"user_id": "u1", "feature": "audit-real"},
        headers=_admin_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["removed"] is True
    fake: FakeDb = app.state.db
    assert fake.beta_allowlist.docs == []


def test_admin_remove_nonexistent_returns_404() -> None:
    r = _client().request(
        "DELETE", "/api/admin/beta-allowlist",
        json={"user_id": "ghost", "feature": "audit-real"},
        headers=_admin_headers(),
    )
    assert r.status_code == 404
    assert "not_allowlisted" in r.text


def test_admin_remove_invalid_feature_returns_400() -> None:
    r = _client().request(
        "DELETE", "/api/admin/beta-allowlist",
        json={"user_id": "u1", "feature": "garbage"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
