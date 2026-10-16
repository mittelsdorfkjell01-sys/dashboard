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
CACHE_ENVELOPE_VERSION = 1


def cache_key(model: str, lat: float, lon: float, var: str) -> str:
    # Four decimals (~11 m latitude) prevent an edited spot from inheriting a
    # neighbouring coordinate's forecast while still normalising float noise.
    return f"om:{model}:{round(lat, 4)}:{round(lon, 4)}:{var}"


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...

    def get_many(self, keys: list[str]) -> dict[str, Any]: ...

    def set(self, key: str, value: Any, ttl: int) -> None: ...

    def delete(self, key: str) -> None: ...

    def acquire_lock(self, key: str, token: str, ttl: int) -> bool | None: ...

    def release_lock(self, key: str, token: str) -> None: ...


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
            logger.warning("live cache get failed (%s) — treating as miss", type(exc).__name__)
            return None
        return _unpack(json.loads(raw)) if raw is not None else None

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            return {}
        try:
            values = self._r.mget(keys)
        except Exception as exc:
            logger.warning("live cache mget failed (%s) — treating as misses", type(exc).__name__)
            return {}
        result: dict[str, Any] = {}
        for key, raw in zip(keys, values):
            if raw is not None:
                result[key] = _unpack(json.loads(raw))
        return result

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        try:
            self._r.set(key, json.dumps(_pack(value)), ex=ttl)
        except Exception as exc:  # redis.RedisError + socket errors
            logger.warning("live cache set failed (%s) — skipping cache", type(exc).__name__)

    def delete(self, key: str) -> None:
        try:
            self._r.delete(key)
        except Exception as exc:  # redis.RedisError + socket errors
            logger.warning("live cache delete failed (%s) — leaving entry to expire", type(exc).__name__)

    def acquire_lock(self, key: str, token: str, ttl: int) -> bool | None:
        try:
            return bool(self._r.set(key, token, ex=max(1, ttl), nx=True))
        except Exception as exc:
            logger.warning("live cache lock failed (%s)", type(exc).__name__)
            return None

    def release_lock(self, key: str, token: str) -> None:
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            self._r.eval(script, 1, key, token)
        except Exception as exc:
            logger.warning("live cache unlock failed (%s)", type(exc).__name__)


class InMemoryCache:
    """Thread-safe bounded process-local TTL cache, lost on restart."""

    def __init__(self, clock=time.monotonic, max_entries: int = 500) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, tuple[float, str]] = {}
        self._clock = clock
        self._max_entries = max(1, max_entries)
        self._lock = threading.Lock()

    def _prune_expired(self, now: float) -> None:
        for key, (expires_at, _) in list(self._store.items()):
            if expires_at <= now:
                self._store.pop(key, None)
        for key, (expires_at, _) in list(self._locks.items()):
            if expires_at <= now:
                self._locks.pop(key, None)

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= self._clock():
                self._store.pop(key, None)
                return None
            return _unpack(value, expose_capture=key == "weather" or key.startswith(("om:", "weather:", "public:")))

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            return {}
        result: dict[str, Any] = {}
        with self._lock:
            now = self._clock()
            for key in keys:
                item = self._store.get(key)
                if item is None:
                    continue
                expires_at, value = item
                if expires_at <= now:
                    self._store.pop(key, None)
                    continue
                result[key] = _unpack(
                    value,
                    expose_capture=key == "weather" or key.startswith(("om:", "weather:", "public:")),
                )
        return result

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        if ttl <= 0:
            return
        with self._lock:
            self._store.pop(key, None)
            self._prune_expired(self._clock())
            while len(self._store) >= self._max_entries:
                self._store.pop(next(iter(self._store)))
            self._store[key] = (self._clock() + ttl, _pack(value))

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def acquire_lock(self, key: str, token: str, ttl: int) -> bool:
        if ttl <= 0:
            return False
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            current = self._locks.get(key)
            if current is not None and current[0] > now:
                return False
            self._locks.pop(key, None)
            while len(self._locks) >= self._max_entries:
                self._locks.pop(next(iter(self._locks)))
            self._locks[key] = (now + ttl, token)
            return True

    def release_lock(self, key: str, token: str) -> None:
        with self._lock:
            current = self._locks.get(key)
            if current is not None and current[1] == token:
                self._locks.pop(key, None)


def _pack(value: Any) -> dict[str, Any]:
    from datetime import datetime, timezone
    return {"version": CACHE_ENVELOPE_VERSION, "captured_at": datetime.now(timezone.utc).isoformat(), "payload": value}


def _unpack(value: Any, *, expose_capture: bool = True) -> Any:
    if not isinstance(value, dict) or value.get("version") != CACHE_ENVELOPE_VERSION or "payload" not in value:
        return value
    payload = value["payload"]
    if expose_capture and isinstance(payload, dict):
        payload = dict(payload)
        # Provider fetchers stamp the payload before the first caller sees it.
        # Preserve that exact instant on later hits so one cache capture maps to
        # one verification-sample identity.
        payload.setdefault("_cache_captured_at", value.get("captured_at"))
    return payload


class FailOpenCache:
    """Shared Redis first, bounded process memory as an outage fallback."""
    def __init__(self, primary: Cache, fallback: Cache) -> None:
        self.primary, self.fallback = primary, fallback

    def get(self, key: str) -> Any | None:
        value = self.primary.get(key)
        return value if value is not None else self.fallback.get(key)

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        primary_get_many = getattr(self.primary, "get_many", None)
        primary = primary_get_many(keys) if primary_get_many is not None else {
            key: value for key in keys if (value := self.primary.get(key)) is not None
        }
        missing = [key for key in keys if key not in primary]
        if not missing:
            return primary
        fallback_get_many = getattr(self.fallback, "get_many", None)
        fallback = fallback_get_many(missing) if fallback_get_many is not None else {
            key: value for key in missing if (value := self.fallback.get(key)) is not None
        }
        return {**fallback, **primary}

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self.primary.set(key, value, ttl)
        self.fallback.set(key, value, ttl)

    def delete(self, key: str) -> None:
        self.primary.delete(key)
        self.fallback.delete(key)

    def acquire_lock(self, key: str, token: str, ttl: int) -> bool:
        acquire = getattr(self.primary, "acquire_lock", None)
        if acquire is not None:
            acquired = acquire(key, token, ttl)
            if acquired is not None:
                return acquired
        fallback_acquire = getattr(self.fallback, "acquire_lock", None)
        return bool(fallback_acquire and fallback_acquire(key, token, ttl))

    def release_lock(self, key: str, token: str) -> None:
        for cache in (self.primary, self.fallback):
            release = getattr(cache, "release_lock", None)
            if release is not None:
                release(key, token)


_default_cache: Cache | None = None


def default_cache() -> Cache:
    global _default_cache
    if _default_cache is None:
        settings = get_settings()
        _default_cache = FailOpenCache(
            RedisCache(),
            InMemoryCache(max_entries=settings.cache_memory_max_entries),
        )
    return _default_cache


def cache_get(key: str) -> Any | None:
    """Module-level convenience over the default (Redis) cache."""
    return default_cache().get(key)


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
    """Module-level convenience over the default (Redis) cache."""
    default_cache().set(key, value, ttl)
