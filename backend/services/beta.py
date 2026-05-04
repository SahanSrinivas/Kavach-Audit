"""Per-user beta-feature gating.

Controls which users get to dogfood real (vs mock) services before a
global cutover. The gate is checked at request time on routes that
actually invoke an engine (POST /audit/generate, POST /policies/upload).

Read path:
    is_beta_user(db, user_id, feature)   # → bool
    resolve_engine_mode(...)             # → ("real" | "mock", beta_invocation: bool)

Write path:
    add_beta_user(db, user_id, feature, added_by, notes)
    remove_beta_user(db, user_id, feature)
    list_beta_users(db, feature)

Caching:
    60-second TTL in-memory cache keyed by (user_id, feature). Adding or
    removing a user takes effect within 60s; admin write paths also
    invalidate the cache for the affected key as a courtesy.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("kavach.beta")


# Valid feature identifiers. Adding a new beta feature: extend this set
# and the corresponding query-param parsing in the router.
VALID_FEATURES: frozenset[str] = frozenset({
    "audit-real",         # POST /audit/generate runs real services.audit.engine
    "parser-real",        # POST /policies/upload calls real Claude PDF parser
    "claims-advocate",    # forward-compat: claims handholding (not implemented)
})


# ---------- TTL cache ----------

_TTL_SECONDS: float = 60.0
_cache: dict[tuple[str, str], tuple[bool, float]] = {}
_cache_lock = threading.Lock()


def _cache_get(user_id: str, feature: str) -> bool | None:
    """Returns cached value or None if absent/expired. Uses time.monotonic
    so wall-clock changes (NTP skew, daylight saving) don't break TTL math."""
    with _cache_lock:
        entry = _cache.get((user_id, feature))
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del _cache[(user_id, feature)]
            return None
        return value


def _cache_set(user_id: str, feature: str, value: bool) -> None:
    with _cache_lock:
        _cache[(user_id, feature)] = (value, time.monotonic() + _TTL_SECONDS)


def _cache_invalidate(user_id: str, feature: str) -> None:
    with _cache_lock:
        _cache.pop((user_id, feature), None)


def _cache_clear() -> None:
    """Test helper — clears all entries. Production code should not call."""
    with _cache_lock:
        _cache.clear()


# ---------- Public API ----------

async def is_beta_user(db: Any, user_id: str, feature: str) -> bool:
    """Returns True if (user_id, feature) is in the beta_allowlist.

    Default-safe: if `feature` is not in VALID_FEATURES, returns False
    without hitting the DB — never serve real engine output to a
    non-allowlisted user even if the caller passes a typo'd feature name.
    """
    if not user_id or feature not in VALID_FEATURES:
        return False
    cached = _cache_get(user_id, feature)
    if cached is not None:
        return cached
    doc = await db.beta_allowlist.find_one(
        {"user_id": user_id, "feature": feature},
        {"_id": 1},
    )
    value = doc is not None
    _cache_set(user_id, feature, value)
    return value


async def resolve_engine_mode(
    db: Any,
    user_id: str,
    beta_param: str | None,
    feature: str,
    use_mocks_global: bool,
) -> tuple[str, bool]:
    """Decides whether this request runs the real engine or the mock.

    Returns (mode, beta_invocation):
      mode             — "real" | "mock", drives the router branch
      beta_invocation  — True iff the real path was taken via beta opt-in
                         (i.e., USE_MOCKS=true globally but the user is
                         allowlisted and passed ?beta=<feature>)

    Truth table:
      use_mocks_global=False                              → ("real",  False)
      use_mocks_global=True, beta_param != feature        → ("mock",  False)
      use_mocks_global=True, beta_param == feature, in    → ("real",  True)
      use_mocks_global=True, beta_param == feature, out   → ("mock",  False)
    """
    if not use_mocks_global:
        return ("real", False)
    if beta_param != feature:
        return ("mock", False)
    if await is_beta_user(db, user_id, feature):
        logger.info("beta.invoke user_id=%s feature=%s", user_id, feature)
        return ("real", True)
    return ("mock", False)


# ---------- Admin write helpers ----------

async def add_beta_user(
    db: Any,
    user_id: str,
    feature: str,
    added_by: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Insert a row into beta_allowlist. Idempotent on the unique
    (user_id, feature) compound index — duplicate inserts raise
    pymongo.errors.DuplicateKeyError which the admin endpoint catches.
    """
    if feature not in VALID_FEATURES:
        raise ValueError(f"unknown feature: {feature}")
    doc = {
        "user_id": user_id,
        "feature": feature,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "added_by": added_by,
        "notes": notes,
    }
    await db.beta_allowlist.insert_one(dict(doc))
    _cache_invalidate(user_id, feature)
    logger.info("beta.add user_id=%s feature=%s added_by=%s", user_id, feature, added_by)
    return doc


async def remove_beta_user(db: Any, user_id: str, feature: str) -> bool:
    """Delete a row. Returns True if a row was removed, False if no match."""
    if feature not in VALID_FEATURES:
        raise ValueError(f"unknown feature: {feature}")
    res = await db.beta_allowlist.delete_one(
        {"user_id": user_id, "feature": feature},
    )
    deleted = bool(getattr(res, "deleted_count", 0))
    _cache_invalidate(user_id, feature)
    logger.info("beta.remove user_id=%s feature=%s deleted=%s", user_id, feature, deleted)
    return deleted


async def list_beta_users(db: Any, feature: str | None = None) -> list[dict[str, Any]]:
    """List allowlist rows, optionally filtered by feature."""
    query = {"feature": feature} if feature else {}
    rows = await db.beta_allowlist.find(query, {"_id": 0}).to_list(500)
    return list(rows)
