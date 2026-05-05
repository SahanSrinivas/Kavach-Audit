"""Rate limiting for public endpoints: Redis (distributed) or in-memory fallback."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

from starlette.requests import Request

logger = logging.getLogger("kavach.rate_limit")

_DISABLED = os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes")
_EXTRACT_PER_MIN = int(os.environ.get("LIFE_EXTRACT_RATE_PER_MIN", "12"))
_PERIOD_SECONDS = 60.0

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_METRICS: dict[str, int] = {
    "memory_checks": 0,
    "redis_checks": 0,
    "redis_fallbacks": 0,
    "rate_limited": 0,
}


class SlidingWindowRateLimiter:
    """In-memory sliding window (single process only)."""

    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self.max_calls = max_calls
        self.period = period_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        if _DISABLED:
            return True
        now = time.time()
        cutoff = now - self.period
        bucket = [t for t in self._hits[key] if t > cutoff]
        bucket.append(now)
        self._hits[key] = bucket
        return len(bucket) <= self.max_calls


life_extract_limiter = SlidingWindowRateLimiter(max_calls=_EXTRACT_PER_MIN, period_seconds=_PERIOD_SECONDS)


def client_ip_from_request(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _redis_fixed_window_allow(ip: str) -> bool:
    """INCR per UTC minute key; shared across workers when Redis is available."""
    try:
        import redis
    except ImportError:
        _METRICS["redis_fallbacks"] += 1
        logger.warning("rate_limit.redis_import_failed fallback memory")
        return life_extract_limiter.check(ip)

    minute_bucket = int(time.time() // 60)
    key = f"kavach:life_extract:{ip}:{minute_bucket}"
    try:
        _METRICS["redis_checks"] += 1
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1.5)
        n = int(r.incr(key))
        if n == 1:
            r.expire(key, int(_PERIOD_SECONDS * 2))
        return n <= _EXTRACT_PER_MIN
    except Exception as e:
        _METRICS["redis_fallbacks"] += 1
        logger.warning("rate_limit.redis_error error=%s fallback memory", e)
        return life_extract_limiter.check(ip)


def check_extract_rate_limit(ip: str) -> bool:
    """Prefer Redis when ``REDIS_URL`` is set; else sliding-window memory."""
    if _DISABLED:
        return True
    if REDIS_URL:
        return _redis_fixed_window_allow(ip)
    _METRICS["memory_checks"] += 1
    return life_extract_limiter.check(ip)


def enforce_extract_rate_limit(request: Request) -> None:
    """Dependency helper for routers."""
    ip = client_ip_from_request(request)
    allowed = check_extract_rate_limit(ip)
    if not allowed:
        _METRICS["rate_limited"] += 1
        logger.warning(
            "rate_limit.block ip=%s redis=%s metrics=%s",
            ip,
            bool(REDIS_URL),
            _METRICS,
        )
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="rate_limited")


def rate_limit_metrics_snapshot() -> dict[str, int]:
    """Operational counters for logs/tests."""
    return dict(_METRICS)
