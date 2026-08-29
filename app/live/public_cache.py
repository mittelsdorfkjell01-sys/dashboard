"""Shared public weather-result cache helpers.

The provider cache avoids repeated Open-Meteo calls.  This second cache layer
stores the already assembled public response so a hit needs neither Postgres
nor the provider.  Forecast entries never outlive their source snapshot.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
from typing import Any

from app.config import get_settings
from app.live.cache import Cache
from app.live.weather_contract import WEATHER_CONTRACT_VERSION

logger = logging.getLogger(__name__)


def public_live_key(spot_id) -> str:
    return f"public:{WEATHER_CONTRACT_VERSION}:live:{spot_id}"


def public_forecast_key(spot_id) -> str:
    return f"public:{WEATHER_CONTRACT_VERSION}:forecast:{spot_id}"


def get_public_live(cache: Cache, spot_id) -> dict[str, Any] | None:
    return _safe_get(cache, public_live_key(spot_id))


def set_public_live(cache: Cache, spot_id, payload: dict[str, Any]) -> None:
    _safe_set(
        cache,
        public_live_key(spot_id),
        payload,
        get_settings().weather_public_live_cache_ttl,
    )


def get_public_forecast(cache: Cache, spot_id) -> dict[str, Any] | None:
    payload = _safe_get(cache, public_forecast_key(spot_id))
    if payload is None:
        return None
    payload.pop("_cache_captured_at", None)
    fresh_until = _as_utc(payload.pop("_fresh_until", None))
    if fresh_until is not None:
        payload["stale"] = fresh_until < datetime.now(timezone.utc)
    return payload


def set_public_forecast(
    cache: Cache,
    spot_id,
    payload: dict[str, Any],
    *,
    valid_until: datetime,
) -> None:
    """Cache a public forecast only for the remaining snapshot lifetime."""
    valid_until = _as_utc(valid_until)
    if valid_until is None:
        return
    remaining = math.ceil((valid_until - datetime.now(timezone.utc)).total_seconds())
    ttl = min(remaining, get_settings().weather_public_forecast_cache_ttl)
    if ttl <= 0:
        return
    stored = dict(payload)
    stored.pop("_cache_captured_at", None)
    stored["_fresh_until"] = valid_until.isoformat()
    _safe_set(cache, public_forecast_key(spot_id), stored, ttl)


def _safe_get(cache: Cache, key: str) -> dict[str, Any] | None:
    try:
        value = cache.get(key)
    except Exception as exc:
        logger.warning("public weather cache get failed (%s)", type(exc).__name__)
        return None
    if not isinstance(value, dict):
        return None
    result = dict(value)
    result.pop("_cache_captured_at", None)
    return result


def _safe_set(cache: Cache, key: str, value: dict[str, Any], ttl: int) -> None:
    if ttl <= 0:
        return
    try:
        cache.set(key, value, ttl)
    except Exception as exc:
        logger.warning("public weather cache set failed (%s)", type(exc).__name__)


def _as_utc(value: datetime | str | None) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
