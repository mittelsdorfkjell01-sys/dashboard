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
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 900  # 15 min
CACHE_ENVELOPE_VERSION = 1
_metrics_lock = threading.Lock()
_metrics: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))


def _namespace(key: str) -> str:
    parts = key.split(":")
    if parts[0] == "public" and len(parts) > 1:
        return f"public:{parts[1]}"
    return parts[0] if parts and parts[0] else "other"


def _record_metric(
    key: str,
    event: str,
    *,
    count: int = 1,
    elapsed_seconds: float = 0.0,
) -> None:
    with _metrics_lock:
        values = _metrics[_namespace(key)]
        values[event] += count
        if elapsed_seconds > 0:
            values["latency_ms_total"] += elapsed_seconds * 1000
            values["latency_samples"] += 1


def record_provider_fetch(
    key: str,
    *,
    elapsed_seconds: float,
    success: bool,
) -> None:
    """Record bounded provider timing without coordinates or cache keys."""
    with _metrics_lock:
        values = _metrics[_namespace(key)]
        values["provider_fetch_success" if success else "provider_fetch_error"] += 1
        values["provider_fetch_latency_ms_total"] += elapsed_seconds * 1000
        values["provider_fetch_latency_samples"] += 1


def cache_metrics_snapshot(*, reset: bool = False) -> dict:
    """Return bounded process-local cache evidence for the admin dashboard."""
    with _metrics_lock:
        snapshot = {namespace: dict(values) for namespace, values in _metrics.items()}
        if reset:
            _metrics.clear()
    namespaces: dict[str, dict[str, float | int | None]] = {}
    for namespace, values in sorted(snapshot.items()):
        hits = int(values.get("hit", 0))
        misses = int(values.get("miss", 0))
        requests = hits + misses
        samples = int(values.get("latency_samples", 0))
        provider_samples = int(values.get("provider_fetch_latency_samples", 0))
        writes = int(values.get("write", 0))
        namespaces[namespace] = {
            "requests": requests,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / requests, 4) if requests else None,
            "errors": int(values.get("error", 0)),
            "writes": writes,
            "average_entry_bytes": (
                round(values.get("bytes_written", 0.0) / writes)
                if writes
                else None
            ),
            "lock_acquired": int(values.get("lock_acquired", 0)),
            "lock_contended": int(values.get("lock_contended", 0)),
            "average_latency_ms": (
                round(values.get("latency_ms_total", 0.0) / samples, 3)
                if samples
                else None
            ),
            "provider_fetches": int(values.get("provider_fetch_success", 0)),
            "provider_fetch_errors": int(values.get("provider_fetch_error", 0)),
            "provider_fetch_average_ms": (
                round(
                    values.get("provider_fetch_latency_ms_total", 0.0)
                    / provider_samples,
                    3,
                )
                if provider_samples
                else None
            ),
        }
    return {
        "scope": "current_process_since_start",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "namespaces": namespaces,
    }


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
            _record_metric(key, "error")
            return None
        if raw is None:
            return None
        try:
            return _unpack(json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "live cache payload invalid for namespace %s (%s) — deleting entry",
                _namespace(key),
                type(exc).__name__,
            )
            _record_metric(key, "error")
            self.delete(key)
            return None

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            return {}
        try:
            values = self._r.mget(keys)
        except Exception as exc:
            logger.warning("live cache mget failed (%s) — treating as misses", type(exc).__name__)
            for key in keys:
                _record_metric(key, "error")
            return {}
        result: dict[str, Any] = {}
        for key, raw in zip(keys, values):
            if raw is not None:
                try:
                    result[key] = _unpack(json.loads(raw))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    logger.warning(
                        "live cache payload invalid for namespace %s (%s) — deleting entry",
                        _namespace(key),
                        type(exc).__name__,
                    )
                    _record_metric(key, "error")
                    self.delete(key)
        return result

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        try:
            self._r.set(key, json.dumps(_pack(value)), ex=ttl)
        except Exception as exc:  # redis.RedisError + socket errors
            logger.warning("live cache set failed (%s) — skipping cache", type(exc).__name__)
            _record_metric(key, "error")

    def delete(self, key: str) -> None:
        try:
            self._r.delete(key)
        except Exception as exc:  # redis.RedisError + socket errors
            logger.warning("live cache delete failed (%s) — leaving entry to expire", type(exc).__name__)
            _record_metric(key, "error")

    def acquire_lock(self, key: str, token: str, ttl: int) -> bool | None:
        try:
            return bool(self._r.set(key, token, ex=max(1, ttl), nx=True))
        except Exception as exc:
            logger.warning("live cache lock failed (%s)", type(exc).__name__)
            _record_metric(key, "error")
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
            _record_metric(key, "error")


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
        started = time.perf_counter()
        value = self.primary.get(key)
        value = value if value is not None else self.fallback.get(key)
        _record_metric(
            key,
            "hit" if value is not None else "miss",
            elapsed_seconds=time.perf_counter() - started,
        )
        return value

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        started = time.perf_counter()
        primary_get_many = getattr(self.primary, "get_many", None)
        primary = primary_get_many(keys) if primary_get_many is not None else {
            key: value for key in keys if (value := self.primary.get(key)) is not None
        }
        missing = [key for key in keys if key not in primary]
        fallback: dict[str, Any] = {}
        if missing:
            fallback_get_many = getattr(self.fallback, "get_many", None)
            fallback = fallback_get_many(missing) if fallback_get_many is not None else {
                key: value for key in missing if (value := self.fallback.get(key)) is not None
            }
        result = {**fallback, **primary}
        elapsed = time.perf_counter() - started
        for key in keys:
            _record_metric(
                key,
                "hit" if key in result else "miss",
                elapsed_seconds=elapsed / max(1, len(keys)),
            )
        return result

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self.primary.set(key, value, ttl)
        self.fallback.set(key, value, ttl)
        _record_metric(key, "write")
        try:
            size = len(json.dumps(value, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            size = 0
        if size:
            _record_metric(key, "bytes_written", count=size)

    def delete(self, key: str) -> None:
        self.primary.delete(key)
        self.fallback.delete(key)

    def acquire_lock(self, key: str, token: str, ttl: int) -> bool:
        acquire = getattr(self.primary, "acquire_lock", None)
        if acquire is not None:
            acquired = acquire(key, token, ttl)
            if acquired is not None:
                _record_metric(key, "lock_acquired" if acquired else "lock_contended")
                return acquired
        fallback_acquire = getattr(self.fallback, "acquire_lock", None)
        acquired = bool(fallback_acquire and fallback_acquire(key, token, ttl))
        _record_metric(key, "lock_acquired" if acquired else "lock_contended")
        return acquired

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
