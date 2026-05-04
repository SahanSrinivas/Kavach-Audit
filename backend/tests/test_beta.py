"""Unit tests for backend/services/beta.py.

Covers:
  - is_beta_user truth table
  - VALID_FEATURES gate
  - resolve_engine_mode truth table
  - TTL cache hit, miss, expiry (via time.monotonic monkey-patch)
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from services import beta as beta_mod


# ---------- Helpers ----------

class _FakeAllowlist:
    """Async stub for db.beta_allowlist.find_one."""
    def __init__(self, hits: set[tuple[str, str]]) -> None:
        self.hits = hits
        self.calls: list[dict[str, str]] = []

    async def find_one(self, query: dict[str, str], _projection: dict | None = None) -> dict | None:
        self.calls.append(query)
        key = (query.get("user_id", ""), query.get("feature", ""))
        return {"_id": "x"} if key in self.hits else None


class _FakeDb:
    def __init__(self, hits: set[tuple[str, str]]) -> None:
        self.beta_allowlist = _FakeAllowlist(hits)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Cache state leaks across tests; clear before every test."""
    beta_mod._cache_clear()
    yield
    beta_mod._cache_clear()


# ---------- is_beta_user ----------

@pytest.mark.asyncio
async def test_is_beta_user_returns_true_for_allowlisted() -> None:
    db = _FakeDb({("u1", "audit-real")})
    assert await beta_mod.is_beta_user(db, "u1", "audit-real") is True


@pytest.mark.asyncio
async def test_is_beta_user_returns_false_for_non_allowlisted() -> None:
    db = _FakeDb(set())
    assert await beta_mod.is_beta_user(db, "u1", "audit-real") is False


@pytest.mark.asyncio
async def test_is_beta_user_returns_false_for_wrong_feature() -> None:
    db = _FakeDb({("u1", "audit-real")})
    assert await beta_mod.is_beta_user(db, "u1", "parser-real") is False


@pytest.mark.asyncio
async def test_is_beta_user_returns_false_for_invalid_feature_no_db_call() -> None:
    """Invalid feature names short-circuit before hitting Mongo."""
    db = _FakeDb({("u1", "anything")})
    assert await beta_mod.is_beta_user(db, "u1", "garbage-feature") is False
    assert db.beta_allowlist.calls == []  # never queried


@pytest.mark.asyncio
async def test_is_beta_user_returns_false_for_empty_user_id() -> None:
    db = _FakeDb({("", "audit-real")})
    assert await beta_mod.is_beta_user(db, "", "audit-real") is False
    assert db.beta_allowlist.calls == []


# ---------- TTL cache ----------

@pytest.mark.asyncio
async def test_cache_hit_skips_db() -> None:
    db = _FakeDb({("u1", "audit-real")})
    await beta_mod.is_beta_user(db, "u1", "audit-real")  # warm
    await beta_mod.is_beta_user(db, "u1", "audit-real")  # should hit cache
    await beta_mod.is_beta_user(db, "u1", "audit-real")
    assert len(db.beta_allowlist.calls) == 1


@pytest.mark.asyncio
async def test_cache_expires_after_ttl() -> None:
    """Use time.monotonic monkey-patch to force the TTL boundary deterministically."""
    db = _FakeDb({("u1", "audit-real")})

    fake_now = [0.0]

    def _monotonic() -> float:
        return fake_now[0]

    with patch("services.beta.time.monotonic", _monotonic):
        await beta_mod.is_beta_user(db, "u1", "audit-real")
        assert len(db.beta_allowlist.calls) == 1
        # Within TTL — cached
        fake_now[0] = beta_mod._TTL_SECONDS - 0.001
        await beta_mod.is_beta_user(db, "u1", "audit-real")
        assert len(db.beta_allowlist.calls) == 1
        # Past TTL — re-fetches
        fake_now[0] = beta_mod._TTL_SECONDS + 0.001
        await beta_mod.is_beta_user(db, "u1", "audit-real")
        assert len(db.beta_allowlist.calls) == 2


@pytest.mark.asyncio
async def test_cache_negative_result_also_cached() -> None:
    db = _FakeDb(set())  # no hits
    await beta_mod.is_beta_user(db, "u1", "audit-real")
    await beta_mod.is_beta_user(db, "u1", "audit-real")
    assert len(db.beta_allowlist.calls) == 1  # negative also cached


@pytest.mark.asyncio
async def test_cache_invalidate_forces_refetch() -> None:
    db = _FakeDb({("u1", "audit-real")})
    await beta_mod.is_beta_user(db, "u1", "audit-real")
    beta_mod._cache_invalidate("u1", "audit-real")
    await beta_mod.is_beta_user(db, "u1", "audit-real")
    assert len(db.beta_allowlist.calls) == 2


# ---------- resolve_engine_mode truth table ----------

@pytest.mark.asyncio
async def test_resolve_real_when_use_mocks_false_globally() -> None:
    db = _FakeDb(set())
    mode, beta_inv = await beta_mod.resolve_engine_mode(
        db=db, user_id="u1", beta_param=None, feature="audit-real",
        use_mocks_global=False,
    )
    assert mode == "real"
    assert beta_inv is False  # not a beta invocation, the system is fully real


@pytest.mark.asyncio
async def test_resolve_real_for_beta_user_with_matching_param() -> None:
    db = _FakeDb({("u1", "audit-real")})
    mode, beta_inv = await beta_mod.resolve_engine_mode(
        db=db, user_id="u1", beta_param="audit-real", feature="audit-real",
        use_mocks_global=True,
    )
    assert mode == "real"
    assert beta_inv is True


@pytest.mark.asyncio
async def test_resolve_mock_for_non_beta_user_with_matching_param() -> None:
    db = _FakeDb(set())
    mode, beta_inv = await beta_mod.resolve_engine_mode(
        db=db, user_id="u1", beta_param="audit-real", feature="audit-real",
        use_mocks_global=True,
    )
    assert mode == "mock"
    assert beta_inv is False


@pytest.mark.asyncio
async def test_resolve_mock_when_no_beta_param() -> None:
    """Default-safe: even an allowlisted user gets mock without explicit opt-in."""
    db = _FakeDb({("u1", "audit-real")})
    mode, beta_inv = await beta_mod.resolve_engine_mode(
        db=db, user_id="u1", beta_param=None, feature="audit-real",
        use_mocks_global=True,
    )
    assert mode == "mock"
    assert beta_inv is False


@pytest.mark.asyncio
async def test_resolve_mock_for_param_mismatch() -> None:
    """beta=parser-real when feature=audit-real → mock (param doesn't match)."""
    db = _FakeDb({("u1", "audit-real"), ("u1", "parser-real")})
    mode, beta_inv = await beta_mod.resolve_engine_mode(
        db=db, user_id="u1", beta_param="parser-real", feature="audit-real",
        use_mocks_global=True,
    )
    assert mode == "mock"
    assert beta_inv is False


@pytest.mark.asyncio
async def test_resolve_mock_for_garbage_param() -> None:
    """Default-safe: invalid feature names never serve real."""
    db = _FakeDb({("u1", "audit-real")})
    mode, beta_inv = await beta_mod.resolve_engine_mode(
        db=db, user_id="u1", beta_param="garbage", feature="audit-real",
        use_mocks_global=True,
    )
    assert mode == "mock"
    assert beta_inv is False


# ---------- Admin write helpers ----------

class _FakeWriteableDb:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

        class _Col:
            def __init__(_self) -> None:
                pass

            async def insert_one(_self, doc: dict[str, Any]) -> None:
                self.docs.append(doc)

            async def delete_one(_self, query: dict[str, Any]) -> Any:
                before = len(self.docs)
                self.docs[:] = [d for d in self.docs if not (
                    d.get("user_id") == query.get("user_id")
                    and d.get("feature") == query.get("feature")
                )]
                class _Res:
                    deleted_count = before - len(self.docs)
                return _Res()

            def find(_self, query: dict[str, Any], _projection: dict | None = None) -> Any:
                rows = list(self.docs)
                if "feature" in query:
                    rows = [d for d in rows if d.get("feature") == query["feature"]]

                class _Cursor:
                    async def to_list(_inner, _n: int) -> list[dict[str, Any]]:
                        return rows
                return _Cursor()

        self.beta_allowlist = _Col()


@pytest.mark.asyncio
async def test_add_beta_user_writes_doc() -> None:
    db = _FakeWriteableDb()
    doc = await beta_mod.add_beta_user(db, "u1", "audit-real",
                                       added_by="admin", notes="founder dogfood")
    assert doc["user_id"] == "u1"
    assert doc["feature"] == "audit-real"
    assert doc["notes"] == "founder dogfood"
    assert len(db.docs) == 1


@pytest.mark.asyncio
async def test_add_beta_user_rejects_invalid_feature() -> None:
    db = _FakeWriteableDb()
    with pytest.raises(ValueError):
        await beta_mod.add_beta_user(db, "u1", "garbage", added_by="admin")
    assert db.docs == []


@pytest.mark.asyncio
async def test_remove_beta_user_returns_true_on_match() -> None:
    db = _FakeWriteableDb()
    await beta_mod.add_beta_user(db, "u1", "audit-real", added_by="admin")
    deleted = await beta_mod.remove_beta_user(db, "u1", "audit-real")
    assert deleted is True
    assert db.docs == []


@pytest.mark.asyncio
async def test_remove_beta_user_returns_false_on_no_match() -> None:
    db = _FakeWriteableDb()
    deleted = await beta_mod.remove_beta_user(db, "u1", "audit-real")
    assert deleted is False


@pytest.mark.asyncio
async def test_list_beta_users_filters_by_feature() -> None:
    db = _FakeWriteableDb()
    await beta_mod.add_beta_user(db, "u1", "audit-real", added_by="admin")
    await beta_mod.add_beta_user(db, "u2", "audit-real", added_by="admin")
    await beta_mod.add_beta_user(db, "u3", "parser-real", added_by="admin")
    rows = await beta_mod.list_beta_users(db, feature="audit-real")
    assert len(rows) == 2
    rows_all = await beta_mod.list_beta_users(db)
    assert len(rows_all) == 3
