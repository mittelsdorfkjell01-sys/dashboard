"""Low-cost cross-instance revision signal for collaborative admin views."""

from __future__ import annotations

import logging
import threading
import time

from app.config import get_settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_local_revision = 0
_redis = None
_last_warning_at = 0.0
_WARNING_INTERVAL_SECONDS = 60.0


def _warn_degraded(operation: str, exc: Exception) -> None:
    """Avoid flooding logs while Redis is temporarily unavailable."""
    global _last_warning_at
    now = time.monotonic()
    with _lock:
        if now - _last_warning_at < _WARNING_INTERVAL_SECONDS:
            return
        _last_warning_at = now
    logger.warning(
        "admin realtime revision %s failed (%s); using process-local fallback",
        operation,
        type(exc).__name__,
    )


def _redis_client():
    global _redis
    if _redis is None:
        import redis

        _redis = redis.Redis.from_url(
            get_settings().redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _redis


def bump_revision() -> int:
    """Increment the shared revision, falling back to this process if needed."""
    global _local_revision
    try:
        revision = int(_redis_client().incr("admin:realtime:revision"))
        with _lock:
            _local_revision = max(_local_revision, revision)
        return revision
    except Exception as exc:
        _warn_degraded("increment", exc)
        with _lock:
            _local_revision += 1
            return _local_revision


def current_revision() -> int:
    """Read the shared revision without making Redis a dashboard dependency."""
    try:
        raw = _redis_client().get("admin:realtime:revision")
        if raw is not None:
            revision = int(raw)
            with _lock:
                global _local_revision
                _local_revision = max(_local_revision, revision)
            return revision
    except Exception as exc:
        _warn_degraded("read", exc)
    with _lock:
        return _local_revision
