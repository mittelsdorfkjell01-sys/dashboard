"""Fixed-window rate limiting for the public write endpoints.

Mirrors the cache seam in ``app.live.cache``: a small ``RateLimiter`` protocol
with a Redis implementation for prod and an in-memory one for tests, provided via
a FastAPI dependency (``get_rate_limiter``) so tests can override it.
"""

from __future__ import annotations

import time
import threading
from typing import Protocol

from fastapi import HTTPException, Request

from app.community.security import ip_hash
from app.config import get_settings


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window: int) -> bool:
        """True if this hit is within ``limit`` per ``window`` seconds."""
        ...


class RedisRateLimiter:
    def __init__(self, url: str | None = None) -> None:
        import redis

        self._r = redis.Redis.from_url(url or get_settings().redis_url)
        self._fallback = InMemoryRateLimiter()

    def allow(self, key: str, limit: int, window: int) -> bool:
        try:
            n = self._r.incr(key)
            if n == 1:
                self._r.expire(key, window)
            return int(n) <= limit
        except Exception:
            # Preserve a per-process protection level during cache outages.
            return self._fallback.allow(key, limit, window)


class InMemoryRateLimiter:
    """Process-local fixed window (tests / no-Redis dev)."""

    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        with self._lock:
            if len(self._hits) > 10_000:
                self._hits = {
                    item_key: value
                    for item_key, value in self._hits.items()
                    if value[1] >= now
                }
            count, reset = self._hits.get(key, (0, now + window))
            if now > reset:
                count, reset = 0, now + window
            count += 1
            self._hits[key] = (count, reset)
            return count <= limit


class NoLimitRateLimiter:
    """Always allows — used by tests that aren't exercising the limiter."""

    def allow(self, key: str, limit: int, window: int) -> bool:  # noqa: D401
        return True


_default: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _default
    if _default is None:
        _default = RedisRateLimiter()
    return _default


def enforce(
    limiter: RateLimiter,
    request: Request,
    action: str,
    *,
    limit: int,
    window: int,
) -> None:
    """Raise 429 when the caller exceeds ``limit`` ``action`` hits per ``window``."""
    key = f"rl:{action}:{ip_hash(request)}"
    if not limiter.allow(key, limit, window):
        raise HTTPException(
            status_code=429,
            detail="Zu viele Anfragen. Bitte in einigen Minuten erneut versuchen.",
        )
