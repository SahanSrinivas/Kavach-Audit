"""Simple in-memory sliding-window rate limiting (per deploy instance)."""

from __future__ import annotations

import os
import time
from collections import defaultdict

_DISABLED = os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes")


class SlidingWindowRateLimiter:
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


# Public life extract: 12 requests / minute / IP (tune via env)
_EXTRACT_PER_MIN = int(os.environ.get("LIFE_EXTRACT_RATE_PER_MIN", "12"))
life_extract_limiter = SlidingWindowRateLimiter(max_calls=_EXTRACT_PER_MIN, period_seconds=60.0)


def client_ip_from_request(request) -> str:
    """Best-effort client id behind reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
