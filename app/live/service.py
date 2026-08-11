"""Calculated current conditions and 10-day forecast assembly.

The cached fetch always pulls the full 10-day horizon once, so the live and the
forecast endpoints share a single cache entry per (model-set, location). The
forecast is then capped/sliced to the requested number of days.

Sprint 18 (Phase 1): the forecast fetches several independent models in **one**
request (:func:`app.live.models.consensus_models`) and reports the **consensus**
(median across models) as the headline value plus a **spread band** (min/max
across models) as honest, data-driven uncertainty. Per-day confidence is derived
from that model disagreement (:func:`app.live.consensus.confidence_from_spread`),
replacing the old calendar rule; the calendar rule remains only as a graceful
fallback when a day has fewer than two models with data, so no spot falls out.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math

from sqlalchemy.orm import Session

from app.config import get_settings
from app.live.cache import Cache, cache_key, default_cache
from app.live.client import MAX_FORECAST_DAYS, OpenMeteoClient, default_client
from app.live.consensus import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    confidence_from_spread,
    spread,
)
from app.live.models import consensus_models, select_model
from app.models import Spot
from app.weather.consensus import WindMember, calculate_wind_consensus
from app.weather.units import WindSpeedUnit, convert_wind_speed
from app.weather.physics import apply_local_physics
from app.weather.vectors import uv_to_wind, wind_to_uv
from app.weather.profiles import resolve_weather_profile
from app.weather.verification import lead_bucket, load_calibrations, store_forecast_samples
from app.weather.shadow import physics_shadow


class InvalidSpotCoordinates(ValueError):
    pass


def confidence_for_day(day_index: int) -> str:
    """0-based day index -> confidence tier (days 1-3 / 4-5 / 6-7).

    The old calendar heuristic, kept only as the graceful fallback for days with
    fewer than two models reporting (see :func:`_day_confidence`).
    """
    if day_index <= 2:
        return CONFIDENCE_HIGH
    if day_index <= 4:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _configured_globals() -> list[str] | None:
    raw = get_settings().live_consensus_models
    if not raw:
        return None
    parsed = [m.strip() for m in raw.split(",") if m.strip()]
    return parsed or None


def _spot_coords(spot: Spot) -> tuple[float, float]:
    from geoalchemy2.shape import to_shape

    point = to_shape(spot.location)
    lat, lon = float(point.y), float(point.x)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise InvalidSpotCoordinates(f"spot {spot.id} has invalid coordinates")
    return lat, lon  # (lat, lon)


def _load_spot(db: Session, spot_id) -> Spot:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    return spot


def _model_set(lat: float, lon: float, pref: str | None) -> tuple[str, list[str]]:
    """Return ``(primary_model, model_set)`` for a location.

    ``primary_model`` is the home/high-res pick (and the back-compat ``model``
    label); ``model_set`` is what we actually fetch for the consensus.
    """
    primary = select_model(lat, lon, pref)
    models = consensus_models(lat, lon, pref, globals_=_configured_globals())
    return primary, models


# --- cached fetches --------------------------------------------------------

def _cached_forecast(
    lat: float,
    lon: float,
    cache_model: str,
    models_csv: str,
    *,
    client: OpenMeteoClient,
    cache: Cache,
) -> dict:
    # `forecast_multi` namespaces the multi-model payload away from any legacy
    # single-model `forecast` entries. One request covers every model in the set.
    key = cache_key(models_csv, lat, lon, f"forecast_multi_{MAX_FORECAST_DAYS}d_v2")
    hit = cache.get(key)
    if hit is not None:
        return hit
    data = client.fetch_forecast(lat, lon, models_csv, MAX_FORECAST_DAYS)
    cache.set(key, data, get_settings().live_cache_ttl)
    return data


def _cached_marine(
    lat: float, lon: float, *, client: OpenMeteoClient, cache: Cache
) -> dict:
    # Marine model is independent of the atmospheric model -> fixed key segment.
    key = cache_key("marine", lat, lon, "marine")
    hit = cache.get(key)
    if hit is not None:
        return hit
    data = client.fetch_marine(lat, lon, MAX_FORECAST_DAYS)
    cache.set(key, data, get_settings().live_cache_ttl)
    return data


# --- multi-model field access ----------------------------------------------

def _field(block: dict, var: str, mid: str, multi: bool):
    """One model's value for ``var`` from a forecast block (hourly or current).

    Multi-model responses suffix the key (``wind_speed_10m_icon_eu``); a single
    model uses the bare key.
    """
    return block.get(f"{var}_{mid}" if multi else var)


def _column(block: dict, var: str, mid: str, multi: bool) -> list:
    v = _field(block, var, mid, multi)
    return v if isinstance(v, list) else []


def _hour_index(times: list, now_iso: str | None) -> int:
    """Index of the current hour on an hourly time axis (else the first hour)."""
    if now_iso and times:
        hour = now_iso[:13]  # 'YYYY-MM-DDTHH'
        for i, t in enumerate(times):
            if isinstance(t, str) and t[:13] == hour:
                return i
    return 0


def _hour_at(block: dict, var: str, mid: str, multi: bool, idx: int):
    col = _column(block, var, mid, multi)
    return col[idx] if 0 <= idx < len(col) else None


def _number(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _wind_consensus_at(hourly: dict, models: list[str], idx: int, lead_hours: float, profile=None, calibrations=None):
    multi = len(models) > 1
    members: list[WindMember] = []
    for model in models:
        speed = _number(_hour_at(hourly, "wind_speed_10m", model, multi, idx))
        direction = _number(_hour_at(hourly, "wind_direction_10m", model, multi, idx))
        gust = _number(_hour_at(hourly, "wind_gusts_10m", model, multi, idx))
        if speed is not None and direction is not None:
            calibration = (calibrations or {}).get((model, lead_bucket(lead_hours)))
            if calibration is not None:
                speed = max(0.0, speed - calibration.bias_ms)
            corrected = apply_local_physics(speed, direction, profile)
            gust_factor = corrected.speed_ms / speed if speed > 0 else 1.0
            members.append(WindMember(model, corrected.speed_ms, corrected.direction_deg, gust * gust_factor if gust is not None else None))
    multipliers = {
        model: row.weight_multiplier
        for (model, bucket), row in (calibrations or {}).items()
        if bucket == lead_bucket(lead_hours)
    }
    return calculate_wind_consensus(members, lead_hours, multipliers=multipliers)


def _knots(value_ms: float | None) -> float | None:
    if value_ms is None:
        return None
    return round(convert_wind_speed(value_ms, WindSpeedUnit.METRES_PER_SECOND, WindSpeedUnit.KNOTS), 1)


def _parse_provider_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _current_consensus(forecast: dict, models: list[str], profile=None):
    """Prefer native 15-minute data; otherwise interpolate hourly vectors."""
    current_time = (forecast.get("current") or {}).get("time")
    target = _parse_provider_time(current_time)
    minutely = forecast.get("minutely_15") or {}
    minutely_times = minutely.get("time") or []
    if target and minutely_times:
        parsed = [_parse_provider_time(value) for value in minutely_times]
        candidates = [(abs((value - target).total_seconds()), i) for i, value in enumerate(parsed) if value]
        if candidates:
            idx = min(candidates)[1]
            return _wind_consensus_at(minutely, models, idx, 0.0, profile), "15min", minutely_times[idx]

    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    if not target or not times:
        idx = _hour_index(times, current_time)
        return _wind_consensus_at(hourly, models, idx, 0.0, profile), "hourly", times[idx] if times else current_time
    parsed = [_parse_provider_time(value) for value in times]
    right = next((i for i, value in enumerate(parsed) if value and value >= target), len(times) - 1)
    left = max(0, right - 1)
    if left == right or not parsed[left] or not parsed[right]:
        return _wind_consensus_at(hourly, models, right, 0.0, profile), "hourly", current_time
    span = (parsed[right] - parsed[left]).total_seconds()
    ratio = 0.0 if span <= 0 else (target - parsed[left]).total_seconds() / span
    multi = len(models) > 1
    members: list[WindMember] = []
    for model in models:
        s0 = _number(_hour_at(hourly, "wind_speed_10m", model, multi, left))
        s1 = _number(_hour_at(hourly, "wind_speed_10m", model, multi, right))
        d0 = _number(_hour_at(hourly, "wind_direction_10m", model, multi, left))
        d1 = _number(_hour_at(hourly, "wind_direction_10m", model, multi, right))
        if None in (s0, s1, d0, d1):
            continue
        u0, v0 = wind_to_uv(s0, d0)
        u1, v1 = wind_to_uv(s1, d1)
        speed, direction = uv_to_wind(u0 + (u1 - u0) * ratio, v0 + (v1 - v0) * ratio)
        if direction is None:
            continue
        corrected = apply_local_physics(speed, direction, profile)
        gusts = [_number(_hour_at(hourly, "wind_gusts_10m", model, multi, index)) for index in {left, right}]
        gust = max((value for value in gusts if value is not None), default=None)
        factor = corrected.speed_ms / speed if speed > 0 else 1.0
        members.append(WindMember(model, corrected.speed_ms, corrected.direction_deg, gust * factor if gust is not None else None))
    return calculate_wind_consensus(members, 0.0), "hourly", current_time


# --- public service entry points -------------------------------------------

def get_live_conditions(
    spot_id,
    *,
    db: Session,
    client: OpenMeteoClient | None = None,
    cache: Cache | None = None,
) -> dict:
    """Current conditions for a spot, from cache or a fresh fetch.

    Wind/gust are the **consensus** (median across models) with a ``wind_spread``
    / ``gust_spread`` band; direction and air come from the primary model. Never
    persisted to Postgres.
    """
    spot = _load_spot(db, spot_id)
    return get_live_conditions_for_spot(spot, client=client, cache=cache)


def get_live_conditions_for_spot(
    spot: Spot,
    *,
    client: OpenMeteoClient | None = None,
    cache: Cache | None = None,
) -> dict:
    """Assemble live conditions for an already-loaded spot.

    Batch callers use this variant so database work stays in the request thread
    while the independent weather requests can run with bounded concurrency.
    """
    client = client or default_client()
    cache = cache or default_cache()
    lat, lon = _spot_coords(spot)
    profile = resolve_weather_profile(getattr(spot, "weather_profile", None))
    primary_model, models = _model_set(lat, lon, spot.model_pref)
    multi = len(models) > 1

    fc = _cached_forecast(
        lat, lon, primary_model, ",".join(models), client=client, cache=cache
    )
    mar = _cached_marine(lat, lon, client=client, cache=cache)
    cur_f = fc.get("current") or {}
    cur_m = mar.get("current") or {}

    # Open-Meteo returns the `current` block UNSUFFIXED even for multi-model
    # requests (only `hourly` carries per-model suffixes), so read the
    # instantaneous values directly. The consensus spread band is taken from the
    # current hour of the multi-model hourly series.
    hourly = fc.get("hourly") or {}
    idx = _hour_index(hourly.get("time") or [], cur_f.get("time"))
    consensus, resolution, calculated_time = _current_consensus(fc, models, profile)
    previous = _wind_consensus_at(hourly, models, max(0, idx - 1), 0.0, profile)
    following = _wind_consensus_at(hourly, models, min(len(hourly.get("time") or []) - 1, idx + 1), 1.0, profile)
    trend = None
    if previous and following:
        change_ms = (following.speed_ms - previous.speed_ms) / 2.0
        threshold_ms = convert_wind_speed(1.25, WindSpeedUnit.KNOTS, WindSpeedUnit.METRES_PER_SECOND)
        trend = "steigend" if change_ms > threshold_ms else "fallend" if change_ms < -threshold_ms else "stabil"
    wind_band = None if consensus is None else {
        "median": _knots(consensus.speed_ms), "low": _knots(consensus.low_ms),
        "high": _knots(consensus.high_ms), "n": consensus.member_count,
    }
    gust_band = None if consensus is None or consensus.gust_ms is None else {
        "median": _knots(consensus.gust_ms), "low": None, "high": None,
        "n": consensus.member_count,
    }
    local = apply_local_physics(0.0, consensus.direction_deg, profile) if consensus and consensus.direction_deg is not None else None
    times = hourly.get("time") or []

    return {
        "spot_id": spot.id,
        "model": primary_model,
        "models": models,
        "time": calculated_time,
        "calculated": True,
        "resolution": resolution,
        "trend": trend,
        "quality_tier": local.quality_tier if local else "coordinates",
        "coastal_classification": local.coastal_classification if local else None,
        "current": {
            "wind": _knots(consensus.speed_ms) if consensus else None,
            "gust": _knots(consensus.gust_ms) if consensus else None,
            "wind_ms": round(consensus.speed_ms, 3) if consensus else None,
            "gust_ms": round(consensus.gust_ms, 3) if consensus and consensus.gust_ms is not None else None,
            "dir": round(consensus.direction_deg, 1) if consensus and consensus.direction_deg is not None else None,
            "air": cur_f.get("temperature_2m"),
            "sst": cur_m.get("sea_surface_temperature"),
            "swell": cur_m.get("swell_wave_height"),
            "period": cur_m.get("swell_wave_period"),
            "swell_dir": cur_m.get("swell_wave_direction"),
            "wind_spread": wind_band,
            "gust_spread": gust_band,
        },
    }


def _index_marine_hours(marine: dict) -> dict[str, dict]:
    hourly = marine.get("hourly") or {}
    times = hourly.get("time") or []
    swh = hourly.get("swell_wave_height") or []
    per = hourly.get("swell_wave_period") or []
    sdir = hourly.get("swell_wave_direction") or []
    sst = hourly.get("sea_surface_temperature") or []
    by_time: dict[str, dict] = {}
    for i, t in enumerate(times):
        by_time[t] = {
            "swell": swh[i] if i < len(swh) else None,
            "period": per[i] if i < len(per) else None,
            "swell_dir": sdir[i] if i < len(sdir) else None,
            "sst": sst[i] if i < len(sst) else None,
        }
    return by_time


def _merge_hours(forecast: dict, marine: dict, models: list[str], profile=None, calibrations=None) -> list[dict]:
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    multi = len(models) > 1
    src = models[0] if models else None  # dir/air from the primary model

    air_series = _column(hourly, "temperature_2m", src, multi) if src else []
    precip_series = _column(hourly, "precipitation", src, multi) if src else []
    marine_by_time = _index_marine_hours(marine)
    reference = _parse_provider_time((forecast.get("current") or {}).get("time"))

    hours: list[dict] = []
    for i, t in enumerate(times):
        valid_at = _parse_provider_time(t)
        # Open-Meteo includes elapsed hours of the current day. They must not
        # influence a forward-looking daily summary or learned lead-time weight.
        if reference and valid_at and valid_at < reference.replace(minute=0, second=0, microsecond=0):
            continue
        lead_hours = max(0.0, (valid_at - reference).total_seconds() / 3600) if reference and valid_at else float(i)
        consensus = _wind_consensus_at(hourly, models, i, lead_hours, profile, calibrations)
        wind_band = None if consensus is None else {
            "median": _knots(consensus.speed_ms), "low": _knots(consensus.low_ms),
            "high": _knots(consensus.high_ms), "n": consensus.member_count,
        }
        m = marine_by_time.get(t, {})
        hours.append(
            {
                "time": t,
                "wind": _knots(consensus.speed_ms) if consensus else None,
                "gust": _knots(consensus.gust_ms) if consensus else None,
                "wind_ms": round(consensus.speed_ms, 3) if consensus else None,
                "gust_ms": round(consensus.gust_ms, 3) if consensus and consensus.gust_ms is not None else None,
                "dir": round(consensus.direction_deg, 1) if consensus and consensus.direction_deg is not None else None,
                "air": air_series[i] if i < len(air_series) else None,
                "precip": precip_series[i] if i < len(precip_series) else None,
                "swell": m.get("swell"),
                "period": m.get("period"),
                "swell_dir": m.get("swell_dir"),
                "sst": m.get("sst"),
                "wind_spread": wind_band,
                "_weights": consensus.weights if consensus else {},
            }
        )
    return hours


def _nums(values: list) -> list[float]:
    return [v for v in values if isinstance(v, (int, float))]


def _peak_wind_band(hours: list[dict]) -> tuple[float | None, float | None]:
    """Model-spread band (low, high) at the day's peak-wind hour, for the strip."""
    best: tuple[float, float, float] | None = None
    for h in hours:
        wb = h.get("wind_spread")
        w = h.get("wind")
        if not wb or w is None:
            continue
        if best is None or w > best[0]:
            best = (w, wb["low"], wb["high"])
    return (best[1], best[2]) if best else (None, None)


def _day_summary(hours: list[dict]) -> dict:
    winds = _nums([h["wind"] for h in hours])
    gusts = _nums([h["gust"] for h in hours])
    airs = _nums([h["air"] for h in hours])
    swells = _nums([h["swell"] for h in hours])
    wind_low, wind_high = _peak_wind_band(hours)
    return {
        "wind_avg": round(sum(winds) / len(winds), 1) if winds else None,
        "wind_max": round(max(winds), 1) if winds else None,
        "gust_max": round(max(gusts), 1) if gusts else None,
        "air_min": round(min(airs), 1) if airs else None,
        "air_max": round(max(airs), 1) if airs else None,
        "swell_max": round(max(swells), 1) if swells else None,
        "wind_low": wind_low,
        "wind_high": wind_high,
    }


def _day_confidence(hours: list[dict], day_index: int) -> str:
    """Confidence from the day's mean wind model-disagreement.

    Falls back to the calendar tier when the day has no hour with >= 2 models
    reporting (graceful degradation -- e.g. single-model coverage).
    """
    widths = [
        wb["high"] - wb["low"]
        for h in hours
        if (wb := h.get("wind_spread")) and wb["n"] >= 2
    ]
    if not widths:
        return confidence_for_day(day_index)
    return confidence_from_spread(sum(widths) / len(widths))


def get_forecast_series(
    spot_id,
    days: int = MAX_FORECAST_DAYS,
    *,
    db: Session,
    client: OpenMeteoClient | None = None,
    cache: Cache | None = None,
) -> dict:
    """Daily + hourly forecast with a consensus band and per-day confidence.

    Returns at most :data:`MAX_FORECAST_DAYS` days (the horizon is hard-capped);
    days 1-5 contain hourly detail; days 6-10 contain summaries only.
    """
    client = client or default_client()
    cache = cache or default_cache()
    days = max(1, min(days, MAX_FORECAST_DAYS))

    spot = _load_spot(db, spot_id)
    lat, lon = _spot_coords(spot)
    primary_model, models = _model_set(lat, lon, spot.model_pref)

    fc = _cached_forecast(
        lat, lon, primary_model, ",".join(models), client=client, cache=cache
    )
    mar = _cached_marine(lat, lon, client=client, cache=cache)
    resolved_profile = resolve_weather_profile(getattr(spot, "weather_profile", None))
    issued_at = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    calibrations = load_calibrations(db, spot.id)
    store_forecast_samples(db, spot.id, fc, models, issued_at)
    hours = _merge_hours(fc, mar, models, resolved_profile, calibrations)

    # Group hours by calendar date, preserving order.
    by_date: dict[str, list[dict]] = {}
    for h in hours:
        date = str(h["time"])[:10]
        by_date.setdefault(date, []).append(h)

    ordered_dates = list(by_date.keys())[:days]  # hard horizon cap
    day_records = [
        {
            "date": date,
            "confidence": _day_confidence(by_date[date], i),
            "summary": _day_summary(by_date[date]),
            "hours": by_date[date] if i < 5 else [],
            "detail": "hourly" if i < 5 else "trend",
        }
        for i, date in enumerate(ordered_dates)
    ]

    return {
        "spot_id": spot.id,
        "model": primary_model,
        "models": models,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": day_records,
        "internal": {
            "units": "m/s",
            "consensus_version": "family-uv-v1",
            "physics_version": getattr(getattr(spot, "weather_profile", None), "physics_version", "wind-v1"),
            "quality_tier": resolved_profile.quality_tier if resolved_profile else "coordinates",
            "calibrated": bool(calibrations),
            "physics_shadow": physics_shadow(spot, resolved_profile),
            "model_run_quality": "capture-time-only",
        },
    }
