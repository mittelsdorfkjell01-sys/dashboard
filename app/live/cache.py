"""Redis cache for Open-Meteo responses.

Keys follow ``om:{model}:{lat_r}:{lon_r}:{var}`` where coordinates are rounded to
2 decimals (~1 km) so nearby spots share an entry, and ``var`` distinguishes the
forecast vs marine payloads. Values are JSON. Default TTL is 30 minutes (well
within the 30-60 min band the live path targets).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 900  # 15 min


def cache_key(model: str, lat: float, lon: float, var: str) -> str:
    # Four decimals (~11 m latitude) prevent an edited spot from inheriting a
    # neighbouring coordinate's forecast while still normalising float noise.
    return f"om:{model}:{round(lat, 4)}:{round(lon, 4)}:{var}"


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl: int) -> None: ...


class RedisCache:
    """JSON-over-Redis cache.

    Fail-open: Redis is a non-critical accelerator here (the same stance the
    /health check takes — a dead cache is "degraded", not fatal). If Redis is
    unreachable or slow, a ``get`` reports a miss and a ``set`` is dropped, so the
    live path just fetches fresh from Open-Meteo instead of 500-ing the request.
    Short socket timeouts keep a hung Redis from blocking the call.
    """

    def __init__(self, url: str | None = None) -> None:
        import redis

        self._r = redis.Redis.from_url(
            url or get_settings().redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )

    def get(self, key: str) -> Any | None:
        try:
            raw = self._r.get(key)
        except Exception as exc:  # redis.RedisError + socket errors
            logger.warning("live cache get failed (%s) — treating as miss", exc)
            return None
        return json.loads(raw) if raw is not None else None

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        try:
            self._r.set(key, json.dumps(value), ex=ttl)
        except Exception as exc:  # redis.RedisError + socket errors
            logger.warning("live cache set failed (%s) — skipping cache", exc)


class InMemoryCache:
    """Thread-safe process-local TTL cache, lost completely on restart."""

    def __init__(self, clock=time.monotonic) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._clock = clock
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= self._clock():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        if ttl <= 0:
            return
        with self._lock:
            self._store[key] = (self._clock() + ttl, value)


_default_cache: Cache | None = None


def default_cache() -> Cache:
    global _default_cache
    if _default_cache is None:
        # Product requirement: live weather must never survive a backend
        # restart. Redis remains available for unrelated application features.
        _default_cache = InMemoryCache()
    return _default_cache


def cache_get(key: str) -> Any | None:
    """Module-level convenience over the default (Redis) cache."""
    return default_cache().get(key)


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
    """Module-level convenience over the default (Redis) cache."""
    default_cache().set(key, value, ttl)
