"""Shared public weather-result cache helpers.

The provider cache avoids repeated Open-Meteo calls.  This second cache layer
stores the already assembled public response so a hit needs neither Postgres
nor the provider.  Forecast entries never outlive their source snapshot.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
import uuid
from typing import Any

from app.config import get_settings
from app.live.cache import Cache
from app.live.weather_contract import FORECAST_PRODUCT_VERSION, WEATHER_CONTRACT_VERSION

logger = logging.getLogger(__name__)
PUBLIC_WEATHER_GENERATION_TTL = 24 * 60 * 60
# The station-measurement layer self-expires quickly so a stale reading drops
# out on its own even if no import invalidates it first.
PUBLIC_MEASUREMENT_TTL = 30 * 60


def public_weather_generation_key(spot_id) -> str:
    return f"public:{WEATHER_CONTRACT_VERSION}:generation:{spot_id}"


def public_weather_generation(cache: Cache, spot_id) -> str:
    try:
        value = cache.get(public_weather_generation_key(spot_id))
    except Exception as exc:
        logger.warning(
            "public weather generation get failed (%s)", type(exc).__name__
        )
        return "0"
    return value if isinstance(value, str) and value else "0"


def public_live_key(spot_id, generation: str = "0") -> str:
    # The model-nowcast product layer (keyed ``nowcast``), distinct from the
    # separate ``measurement`` layer (P0.1). The function name is kept for its
    # many call sites; the key names the product it actually stores.
    base = f"public:{WEATHER_CONTRACT_VERSION}:nowcast:{spot_id}"
    return base if generation == "0" else f"{base}:{generation}"


def public_forecast_key(spot_id, generation: str = "0") -> str:
    base = (
        f"public:{WEATHER_CONTRACT_VERSION}:forecast:"
        f"{FORECAST_PRODUCT_VERSION}:{spot_id}"
    )
    return base if generation == "0" else f"{base}:{generation}"


def public_measurement_key(spot_id) -> str:
    """Key for the SEPARATE station-measurement product (P0.1).

    A measurement is never folded into the model-nowcast cache: it lives in its
    own layer, attached at serve time.  Keeping it out of the nowcast key is
    what makes single and batch serving order-independent.
    """
    return f"public:{WEATHER_CONTRACT_VERSION}:measurement:{spot_id}"


def get_public_live(
    cache: Cache, spot_id, *, generation: str | None = None
) -> dict[str, Any] | None:
    generation = generation or public_weather_generation(cache, spot_id)
    return _safe_get(cache, public_live_key(spot_id, generation))


def set_public_live(
    cache: Cache,
    spot_id,
    payload: dict[str, Any],
    *,
    generation: str | None = None,
) -> None:
    generation = generation or public_weather_generation(cache, spot_id)
    # The assembled model-nowcast cache must NEVER pin a station measurement
    # (P0.1): it is a separate product attached at serve time.  Forcing it to
    # ``None`` keeps the stored product order-independent no matter which
    # endpoint warmed the cache.
    stored = {**payload, "measurement": None}
    _safe_set(
        cache,
        public_live_key(spot_id, generation),
        stored,
        get_settings().weather_public_live_cache_ttl,
    )


def get_public_measurement(cache: Cache, spot_id) -> dict[str, Any] | None:
    """The station-measurement product from its own cache layer (cache-only).

    Cache hits on the live endpoints read the measurement from here so they stay
    database-free; a miss simply means no warm reading (the caller computes it).
    """
    return _safe_get(cache, public_measurement_key(spot_id))


def set_public_measurement(cache: Cache, spot_id, payload: dict[str, Any] | None) -> None:
    """Warm the separate measurement layer with a freshly computed reading."""
    if payload is None:
        return
    _safe_set(cache, public_measurement_key(spot_id), payload, PUBLIC_MEASUREMENT_TTL)


def invalidate_public_measurement(cache: Cache, spot_id) -> None:
    """Drop the cached measurement (e.g. after a station import persists rows).

    The import layer calls this instead of hand-rolling a cache entry, so the
    next serve recomputes from the freshly stored, quality-gated observation.
    """
    _safe_delete(cache, public_measurement_key(spot_id))


def get_public_forecast(
    cache: Cache, spot_id, *, generation: str | None = None
) -> dict[str, Any] | None:
    generation = generation or public_weather_generation(cache, spot_id)
    payload = _safe_get(cache, public_forecast_key(spot_id, generation))
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
    generation: str | None = None,
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
    generation = generation or public_weather_generation(cache, spot_id)
    _safe_set(cache, public_forecast_key(spot_id, generation), stored, ttl)


def invalidate_public_weather(cache: Cache, spot_id) -> None:
    """Drop assembled values after a serving-affecting profile change.

    Provider responses use different keys and deliberately remain cached: the
    next request can recalculate local physics without another upstream call.
    """
    previous = public_weather_generation(cache, spot_id)
    replacement = uuid.uuid4().hex
    try:
        cache.set(
            public_weather_generation_key(spot_id),
            replacement,
            PUBLIC_WEATHER_GENERATION_TTL,
        )
    except Exception as exc:
        logger.warning(
            "public weather generation bump failed (%s)", type(exc).__name__
        )
    else:
        logger.info(
            "public_weather_cache_generation_advanced",
            extra={
                "weather_event": "public_weather_cache_generation_advanced",
                "weather_spot_id": str(spot_id),
                "weather_previous_cache_generation": previous,
                "weather_cache_generation": replacement,
            },
        )
    _safe_delete(cache, public_live_key(spot_id, previous))
    _safe_delete(cache, public_forecast_key(spot_id, previous))


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


def _safe_delete(cache: Cache, key: str) -> None:
    delete = getattr(cache, "delete", None)
    if delete is None:
        return
    try:
        delete(key)
    except Exception as exc:
        logger.warning("public weather cache delete failed (%s)", type(exc).__name__)


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
