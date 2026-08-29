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
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, selectinload

from app.config import get_settings
from app.live.cache import Cache, cache_key, default_cache
from app.live.client import MAX_FORECAST_DAYS, OpenMeteoClient, default_client
from app.live.consensus import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    confidence_from_spread,
)
from app.live.models import consensus_models, select_model
from app.models import Spot, SpotWeatherProfile, WeatherObservation, WeatherStation
from app.weather.consensus import WindMember, calculate_wind_consensus
from app.weather.units import WindSpeedUnit, convert_wind_speed
from app.weather.physics import apply_local_physics
from app.weather.physics.coast import coastal_class
from app.weather.vectors import uv_to_wind, wind_to_uv
from app.weather.profiles import resolve_weather_profile
from app.weather.verification import lead_bucket, load_calibrations, store_forecast_samples
from app.weather.shadow import physics_shadow
from app.weather.observations import public_measurement
from app.live.weather_contract import (
    Availability, MODEL_NOWCAST_STALE_SECONDS, WEATHER_CONTRACT_VERSION,
    WMO_MAPPING_VERSION, age_seconds, distance_km, is_stale,
    marine_classification, provider_axis_utc, provider_time_utc, provider_timezone, valid_number,
    weather_condition,
)


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
    # Pure unit-test doubles expose only ``get``. Real sessions fetch exactly the
    # weather fields instead of transferring the editorial/image JSON columns.
    if not hasattr(db, "scalar"):
        spot = db.get(Spot, spot_id)
    else:
        spot = db.scalar(
            select(Spot)
            .where(Spot.id == spot_id)
            .options(
                load_only(Spot.id, Spot.location, Spot.model_pref, Spot.water_type),
                selectinload(Spot.weather_profile).load_only(
                    SpotWeatherProfile.active,
                    SpotWeatherProfile.timezone,
                    SpotWeatherProfile.elevation_m,
                    SpotWeatherProfile.coastal_normal_deg,
                    SpotWeatherProfile.quality_tier,
                    SpotWeatherProfile.physics_version,
                ),
            )
        )
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    return spot


def _forecast_sample_issued_at(forecast: dict) -> datetime:
    """Stable identity for all samples derived from one provider cache capture."""
    return _parse_provider_time(forecast.get("_cache_captured_at")) or datetime.now(
        timezone.utc
    )


def _store_forecast_samples_once(
    db,
    spot_id,
    forecast: dict,
    models: list[str],
    issued_at: datetime,
    cache: Cache,
) -> int:
    """Run verification persistence once for each provider-cache capture."""
    marker = (
        f"weather:{WEATHER_CONTRACT_VERSION}:forecast-samples:"
        f"{spot_id}:{issued_at.isoformat()}"
    )
    try:
        if cache.get(marker) is not None:
            return 0
    except Exception:
        pass
    stored = store_forecast_samples(db, spot_id, forecast, models, issued_at)
    try:
        cache.set(
            marker,
            {"complete": True, "stored": stored},
            get_settings().weather_forecast_cache_ttl,
        )
    except Exception:
        pass
    return stored


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
    data = {**data, "_cache_captured_at": datetime.now(timezone.utc).isoformat()}
    cache.set(key, data, get_settings().weather_forecast_cache_ttl)
    return data


def _cached_nowcast(lat, lon, models_csv, *, client, cache) -> dict:
    key = cache_key(models_csv, lat, lon, "atmosphere_nowcast_v1")
    hit = cache.get(key)
    if hit is not None:
        return hit
    fetch = getattr(client, "fetch_nowcast", None)
    data = fetch(lat, lon, models_csv) if fetch else client.fetch_forecast(lat, lon, models_csv, 1)
    data = {**data, "_cache_captured_at": datetime.now(timezone.utc).isoformat()}
    cache.set(key, data, get_settings().weather_nowcast_cache_ttl)
    return data


def _cached_marine(
    lat: float, lon: float, *, client: OpenMeteoClient, cache: Cache, current_only: bool = False
) -> dict:
    # Marine model is independent of the atmospheric model -> fixed key segment.
    key = cache_key("marine", lat, lon, "marine_current_v1" if current_only else "marine_forecast_v1")
    hit = cache.get(key)
    if hit is not None:
        return hit
    fetch = getattr(client, "fetch_current_marine", None) if current_only else None
    data = fetch(lat, lon) if fetch else client.fetch_marine(lat, lon, MAX_FORECAST_DAYS)
    data = {**data, "_cache_captured_at": datetime.now(timezone.utc).isoformat()}
    ttl = get_settings().weather_marine_current_cache_ttl if current_only else get_settings().weather_forecast_cache_ttl
    cache.set(key, data, ttl)
    return data


def _marine_for_spot(spot, lat: float, lon: float, *, client, cache, current_only=False):
    eligibility = marine_classification(spot)
    diagnostics = {"status": eligibility.value, "requested_coordinate": {"latitude": lat, "longitude": lon}}
    if eligibility is not Availability.AVAILABLE:
        return {}, diagnostics
    try:
        marine = _cached_marine(lat, lon, client=client, cache=cache, current_only=current_only)
    except Exception as exc:
        diagnostics.update(status=Availability.UNAVAILABLE_PROVIDER.value, error_class=type(exc).__name__)
        return {}, diagnostics
    used_lat, used_lon = valid_number(marine.get("latitude")), valid_number(marine.get("longitude"))
    if used_lat is not None and used_lon is not None:
        grid_distance = distance_km(lat, lon, used_lat, used_lon)
        diagnostics.update(used_coordinate={"latitude": used_lat, "longitude": used_lon}, grid_distance_km=round(grid_distance, 3))
        if grid_distance > get_settings().weather_marine_grid_max_km:
            diagnostics["status"] = Availability.UNAVAILABLE_OUT_OF_RANGE.value
            return {}, diagnostics
    diagnostics["status"] = Availability.AVAILABLE.value
    return marine, diagnostics


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
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
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
    if value_ms is None or not math.isfinite(value_ms) or value_ms < 0:
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
    result = get_live_conditions_for_spot(spot, client=client, cache=cache)
    result["measurement"] = _latest_measurement(db, spot.id)
    measurement = result["measurement"]
    if measurement:
        current = result["current"]
        current.update({
            "wind_ms": measurement["wind_speed_ms"], "gust_ms": measurement["wind_gust_ms"],
            "wind": _knots(measurement["wind_speed_ms"]), "gust": _knots(measurement["wind_gust_ms"]),
            "dir": measurement["wind_direction_from_deg"],
        })
        result["sources"]["wind"] = measurement["provenance"]
    return result


def _latest_measurement(db, spot_id) -> dict | None:
    """Return an actual station observation separately from the model nowcast."""
    if not hasattr(db, "scalar"):
        return None
    station = db.scalar(select(WeatherStation).where(
        WeatherStation.spot_id == spot_id, WeatherStation.active.is_(True)
    ).order_by(WeatherStation.distance_km.asc().nullslast()).limit(1))
    if station is None:
        return None
    observation = db.scalar(select(WeatherObservation).where(
        WeatherObservation.station_id == station.id
    ).order_by(WeatherObservation.observed_at.desc()).limit(1))
    if observation is None:
        return None
    now = datetime.now(timezone.utc)
    observed = observation.observed_at.astimezone(timezone.utc)
    eligible, _reasons = public_measurement(station, observation, now=now)
    if not eligible:
        return None
    return {
        "observation_type": "measurement", "station_id": str(station.id),
        "provider": station.provider, "provider_station_id": station.provider_station_id,
        "observed_at": observed.isoformat(), "age_seconds": max(0, int((now - observed).total_seconds())),
        "distance_km": station.distance_km, "wind_speed_ms": observation.wind_speed_ms,
        "wind_gust_ms": observation.wind_gust_ms, "wind_direction_from_deg": observation.wind_direction_deg,
        "quality": observation.quality,
        "station_name": station.name, "stale": False,
        "provenance": {
            "source_type": "measurement", "observation_type": "measurement",
            "source": "station", "provider": station.provider.upper(),
            "observation_at": observed, "valid_at": observed,
            "captured_at": observation.fetched_at or observation.created_at,
            "model_run_quality": "unknown", "age_seconds": max(0, int((now-observed).total_seconds())),
            "stale": False, "availability": "available", "quality_tier": "quality_checked_station",
            "spot_timezone": "UTC", "requested_coordinate": {"latitude": station.latitude, "longitude": station.longitude},
            "grid_distance_km": station.distance_km, "uncertainty": "limited", "data_issues": observation.data_issues or [],
        },
    }


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
    fc = _cached_nowcast(lat, lon, ",".join(models), client=client, cache=cache)
    mar, marine_diagnostics = _marine_for_spot(spot, lat, lon, client=client, cache=cache, current_only=True)
    cur_f = fc.get("current") or {}
    cur_m = mar.get("current") or {}
    captured_at = _parse_provider_time(fc.get("_cache_captured_at")) or datetime.now(timezone.utc)
    marine_captured_at = _parse_provider_time(mar.get("_cache_captured_at")) if mar else None

    # Open-Meteo returns the `current` block UNSUFFIXED even for multi-model
    # requests (only `hourly` carries per-model suffixes), so read the
    # instantaneous values directly. The consensus spread band is taken from the
    # current hour of the multi-model hourly series.
    hourly = fc.get("hourly") or {}
    idx = _hour_index(hourly.get("time") or [], cur_f.get("time"))
    consensus, resolution, calculated_time = _current_consensus(fc, models, profile)
    calculated_instant = provider_time_utc(calculated_time, provider_timezone(fc))
    canonical_time = calculated_instant.isoformat() if calculated_instant else None
    atmosphere_valid_at = provider_time_utc(cur_f.get("time"), provider_timezone(fc)) or calculated_instant
    marine_valid_at = provider_time_utc(cur_m.get("time"), provider_timezone(mar)) if mar else None
    atmosphere_age = age_seconds(atmosphere_valid_at, now=captured_at)
    marine_age = age_seconds(marine_valid_at, now=datetime.now(timezone.utc))
    atmosphere_stale = is_stale(atmosphere_age, 0, threshold_seconds=MODEL_NOWCAST_STALE_SECONDS)
    marine_stale = is_stale(marine_age, 0, threshold_seconds=MODEL_NOWCAST_STALE_SECONDS * 2)
    previous = _wind_consensus_at(hourly, models, max(0, idx - 1), 0.0, profile)
    following = _wind_consensus_at(hourly, models, min(len(hourly.get("time") or []) - 1, idx + 1), 1.0, profile)
    trend = None
    if previous and following:
        change_ms = (following.speed_ms - previous.speed_ms) / 2.0
        threshold_ms = convert_wind_speed(1.25, WindSpeedUnit.KNOTS, WindSpeedUnit.METRES_PER_SECOND)
        trend = "steigend" if change_ms > threshold_ms else "fallend" if change_ms < -threshold_ms else "stabil"
    wind_band = None if consensus is None or consensus.member_count < 2 else {
        "median": _knots(consensus.speed_ms), "low": _knots(consensus.low_ms),
        "high": _knots(consensus.high_ms), "n": consensus.member_count,
    }
    gust_band = None
    local = apply_local_physics(0.0, consensus.direction_deg, profile) if consensus and consensus.direction_deg is not None else None
    coastal_normal = getattr(profile, "coastal_normal_deg", None) if profile else None
    return {
        "spot_id": spot.id,
        "model": primary_model,
        "models": models,
        "time": canonical_time,  # deprecated: valid time of the headline wind value
        "observation_type": "nowcast",
        "calculated": True,
        "resolution": resolution,
        "trend": trend,
        "quality_tier": local.quality_tier if local else "coordinates",
        "coastal_classification": local.coastal_classification if local else None,
        "coastal_normal_deg": coastal_normal,
        "availability": {"atmosphere": "available", "solar": "available", "marine": marine_diagnostics["status"]},
        "provenance": {
            "source_type": "model_nowcast", "observation_type": "nowcast",
            "source": "model", "provider": "Surfwinddata · Open-Meteo",
            "model": None, "model_family": None,
            "model_run": None, "model_run_at": None, "model_run_quality": "capture-time-only",
            "issued_at": None, "observation_at": None,
            "valid_at": atmosphere_valid_at,
            "captured_at": captured_at, "calculated_at": captured_at,
            "spot_timezone": provider_timezone(fc),
            "requested_coordinate": {"latitude": lat, "longitude": lon},
            "used_coordinate": marine_diagnostics.get("used_coordinate"),
            "grid_distance_km": marine_diagnostics.get("grid_distance_km"),
            "spatial_resolution_km": None, "temporal_resolution_minutes": 15,
            "age_seconds": atmosphere_age, "stale": atmosphere_stale,
            "availability": "available_stale" if atmosphere_stale else "available",
            "quality_tier": local.quality_tier if local else "coordinates",
            "attribution": [{"provider": "Open-Meteo", "text": "Modelldaten via Open-Meteo"}],
            "uncertainty": "determined" if wind_band else "not_determined",
            "data_issues": [] if atmosphere_valid_at else ["valid_at:unknown"],
        },
        "sources": {
            "wind": {
                "source_type": "model_nowcast", "observation_type": "nowcast", "source": "model",
                "provider": "Surfwinddata · Open-Meteo", "model_run_quality": "capture-time-only",
                "valid_at": atmosphere_valid_at, "captured_at": captured_at,
                "calculated_at": captured_at, "spot_timezone": provider_timezone(fc),
                "requested_coordinate": {"latitude": lat, "longitude": lon},
                "temporal_resolution_minutes": 15 if resolution == "15min" else 60,
                "age_seconds": atmosphere_age, "stale": atmosphere_stale,
                "availability": "available_stale" if atmosphere_stale else "available",
                "quality_tier": local.quality_tier if local else "coordinates",
                "uncertainty": "determined" if wind_band else "not_determined",
                "data_issues": [] if atmosphere_valid_at else ["valid_at:unknown"],
            },
            "air": {
                "source_type": "model_nowcast", "observation_type": "nowcast", "source": "model",
                "provider": "Open-Meteo", "model_run_quality": "capture-time-only",
                "valid_at": atmosphere_valid_at, "captured_at": captured_at,
                "spot_timezone": provider_timezone(fc),
                "requested_coordinate": {"latitude": lat, "longitude": lon},
                "temporal_resolution_minutes": 15 if resolution == "15min" else 60,
                "age_seconds": atmosphere_age, "stale": atmosphere_stale,
                "availability": "available_stale" if atmosphere_stale else "available",
                "quality_tier": "provider_point", "uncertainty": "not_determined",
                "data_issues": [] if atmosphere_valid_at else ["valid_at:unknown"],
            },
            "marine": {
                "source_type": "model_nowcast", "observation_type": "nowcast", "source": "model",
                "provider": "Open-Meteo Marine", "model_run_quality": "capture-time-only",
                "valid_at": marine_valid_at, "captured_at": marine_captured_at or captured_at,
                "spot_timezone": provider_timezone(mar) if mar else "UTC",
                "requested_coordinate": {"latitude": lat, "longitude": lon},
                "used_coordinate": marine_diagnostics.get("used_coordinate"),
                "grid_distance_km": marine_diagnostics.get("grid_distance_km"),
                "temporal_resolution_minutes": 60, "age_seconds": marine_age,
                "stale": marine_stale,
                "availability": "available_stale" if marine_stale and mar else marine_diagnostics["status"],
                "quality_tier": "provider_point", "uncertainty": "not_determined",
                "data_issues": [] if marine_valid_at or not mar else ["valid_at:unknown"],
            },
        },
        "measurement": None,
        "current": {
            "wind": _knots(consensus.speed_ms) if consensus else None,
            "gust": _knots(consensus.gust_ms) if consensus and consensus.gust_ms is not None and consensus.gust_ms >= consensus.speed_ms else None,
            "wind_ms": round(consensus.speed_ms, 3) if consensus else None,
            "gust_ms": round(consensus.gust_ms, 3) if consensus and consensus.gust_ms is not None and consensus.gust_ms >= consensus.speed_ms else None,
            "dir": round(consensus.direction_deg, 1) if consensus and consensus.direction_deg is not None else None,
            "air": valid_number(cur_f.get("temperature_2m"), minimum=-90, maximum=60),
            "sst": cur_m.get("sea_surface_temperature"),
            "swell": cur_m.get("swell_wave_height"),
            "period": cur_m.get("swell_wave_period"),
            "swell_dir": cur_m.get("swell_wave_direction"),
            "coastal_normal_deg": coastal_normal,
            "coastal_classification": coastal_class(consensus.direction_deg if consensus else None, coastal_normal),
            "wave_coastal_classification": coastal_class(cur_m.get("swell_wave_direction"), coastal_normal),
            "waves": {
                "total_wave": {
                    "significant_height_m": valid_number(cur_m.get("wave_height"), minimum=0, maximum=30),
                    "mean_period_s": valid_number(cur_m.get("wave_period"), minimum=0.5, maximum=35),
                    "mean_direction_from_deg": valid_number(cur_m.get("wave_direction"), minimum=0, maximum=359.999),
                    "source": "Open-Meteo Marine", "quality_tier": "provider_point",
                },
                "primary_swell": {
                    "significant_height_m": valid_number(cur_m.get("swell_wave_height"), minimum=0, maximum=30),
                    "mean_period_s": valid_number(cur_m.get("swell_wave_period"), minimum=0.5, maximum=35),
                    "mean_direction_from_deg": valid_number(cur_m.get("swell_wave_direction"), minimum=0, maximum=359.999),
                    "source": "Open-Meteo Marine", "quality_tier": "provider_point",
                },
            } if mar else None,
            "wind_spread": wind_band,
            "gust_spread": gust_band,
        },
    }


def _index_marine_hours(marine: dict) -> dict[str, dict]:
    hourly = marine.get("hourly") or {}
    times = hourly.get("time") or []
    total_height = hourly.get("wave_height") or []
    total_period = hourly.get("wave_period") or []
    total_direction = hourly.get("wave_direction") or []
    swell_height = hourly.get("swell_wave_height") or []
    swell_period = hourly.get("swell_wave_period") or []
    swell_direction = hourly.get("swell_wave_direction") or []
    sst = hourly.get("sea_surface_temperature") or []
    by_time: dict[str, dict] = {}
    for i, instant in enumerate(provider_axis_utc(times, provider_timezone(marine))):
        if instant is None:
            continue
        by_time[instant.isoformat()] = {
            # Deprecated compatibility fields retain their physical meaning:
            # they contain primary swell only, never total-wave values.
            "swell": valid_number(swell_height[i] if i < len(swell_height) else None, minimum=0, maximum=30),
            "period": valid_number(swell_period[i] if i < len(swell_period) else None, minimum=0.5, maximum=35),
            "swell_dir": valid_number(swell_direction[i] if i < len(swell_direction) else None, minimum=0, maximum=359.999),
            "waves": {
                "total_wave": {
                    "significant_height_m": valid_number(total_height[i] if i < len(total_height) else None, minimum=0, maximum=30),
                    "mean_period_s": valid_number(total_period[i] if i < len(total_period) else None, minimum=0.5, maximum=35),
                    "mean_direction_from_deg": valid_number(total_direction[i] if i < len(total_direction) else None, minimum=0, maximum=359.999),
                    "source": "Open-Meteo Marine", "quality_tier": "provider_point",
                },
                "primary_swell": {
                    "significant_height_m": valid_number(swell_height[i] if i < len(swell_height) else None, minimum=0, maximum=30),
                    "mean_period_s": valid_number(swell_period[i] if i < len(swell_period) else None, minimum=0.5, maximum=35),
                    "mean_direction_from_deg": valid_number(swell_direction[i] if i < len(swell_direction) else None, minimum=0, maximum=359.999),
                    "source": "Open-Meteo Marine", "quality_tier": "provider_point",
                },
            },
            "sst": valid_number(sst[i] if i < len(sst) else None, minimum=-5, maximum=45),
        }
    return by_time


def _merge_hours(forecast: dict, marine: dict, models: list[str], profile=None, calibrations=None) -> list[dict]:
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    multi = len(models) > 1
    src = models[0] if models else None  # dir/air from the primary model

    air_series = _column(hourly, "temperature_2m", src, multi) if src else []
    precip_series = _column(hourly, "precipitation", src, multi) if src else []
    apparent_series = _column(hourly, "apparent_temperature", src, multi) if src else []
    cloud_series = _column(hourly, "cloud_cover", src, multi) if src else []
    pressure_series = _column(hourly, "pressure_msl", src, multi) if src else []
    uv_series = _column(hourly, "uv_index", src, multi) if src else []
    code_series = _column(hourly, "weather_code", src, multi) if src else []
    day_series = _column(hourly, "is_day", src, multi) if src else []
    marine_by_time = _index_marine_hours(marine)
    timezone_name = provider_timezone(forecast)
    reference = provider_time_utc((forecast.get("current") or {}).get("time"), timezone_name)
    coastal_normal = getattr(profile, "coastal_normal_deg", None) if profile else None
    quality_tier = getattr(profile, "quality_tier", "coordinates") if profile else "coordinates"

    hours: list[dict] = []
    for i, valid_at in enumerate(provider_axis_utc(times, timezone_name)):
        if valid_at is None:
            continue
        # Open-Meteo includes elapsed hours of the current day. They must not
        # influence a forward-looking daily summary or learned lead-time weight.
        if reference and valid_at and valid_at < reference.replace(minute=0, second=0, microsecond=0):
            continue
        lead_hours = max(0.0, (valid_at - reference).total_seconds() / 3600) if reference and valid_at else float(i)
        consensus = _wind_consensus_at(hourly, models, i, lead_hours, profile, calibrations)
        wind_band = None if consensus is None or consensus.member_count < 2 else {
            "median": _knots(consensus.speed_ms), "low": _knots(consensus.low_ms),
            "high": _knots(consensus.high_ms), "n": consensus.member_count,
        }
        utc_time = valid_at.isoformat()
        m = marine_by_time.get(utc_time, {})
        code = code_series[i] if i < len(code_series) else None
        code = int(code) if isinstance(code, (int, float)) and not isinstance(code, bool) else None
        hours.append(
            {
                "time": utc_time,
                "wind": _knots(consensus.speed_ms) if consensus else None,
                "gust": _knots(consensus.gust_ms) if consensus and consensus.gust_ms is not None and consensus.gust_ms >= consensus.speed_ms else None,
                "wind_ms": round(consensus.speed_ms, 3) if consensus else None,
                "gust_ms": round(consensus.gust_ms, 3) if consensus and consensus.gust_ms is not None and consensus.gust_ms >= consensus.speed_ms else None,
                "dir": round(consensus.direction_deg, 1) if consensus and consensus.direction_deg is not None else None,
                "air": valid_number(air_series[i] if i < len(air_series) else None, minimum=-90, maximum=60),
                "apparent_temperature_c": valid_number(apparent_series[i] if i < len(apparent_series) else None, minimum=-100, maximum=70),
                "precip": valid_number(precip_series[i] if i < len(precip_series) else None, minimum=0, maximum=500),
                "cloud_cover_pct": valid_number(cloud_series[i] if i < len(cloud_series) else None, minimum=0, maximum=100),
                "pressure_msl_hpa": valid_number(pressure_series[i] if i < len(pressure_series) else None, minimum=800, maximum=1100),
                "uv_index": valid_number(uv_series[i] if i < len(uv_series) else None, minimum=0),
                "weather_code": code,
                "weather_condition": weather_condition(code),
                "is_day": bool(day_series[i]) if i < len(day_series) and day_series[i] in (0, 1, False, True) else None,
                "swell": m.get("swell"),
                "period": m.get("period"),
                "swell_dir": m.get("swell_dir"),
                "coastal_normal_deg": coastal_normal,
                "coastal_classification": coastal_class(consensus.direction_deg if consensus else None, coastal_normal),
                "wave_coastal_classification": coastal_class(m.get("swell_dir"), coastal_normal),
                "quality_tier": quality_tier,
                "stale": False,
                "waves": m.get("waves"),
                "observation_type": "forecast",
                "sst": m.get("sst"),
                "wind_spread": wind_band,
                "_weights": consensus.weights if consensus else {},
            }
        )
    return hours


def _nums(values: list) -> list[float]:
    return [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]


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
    total_waves = _nums([((h.get("waves") or {}).get("total_wave") or {}).get("significant_height_m") for h in hours])
    wind_low, wind_high = _peak_wind_band(hours)
    return {
        "wind_avg": round(sum(winds) / len(winds), 1) if winds else None,
        "wind_max": round(max(winds), 1) if winds else None,
        "gust_max": round(max(gusts), 1) if gusts else None,
        "air_min": round(min(airs), 1) if airs else None,
        "air_max": round(max(airs), 1) if airs else None,
        "swell_max": round(max(swells), 1) if swells else None,
        "primary_swell_max": round(max(swells), 1) if swells else None,
        "total_wave_max": round(max(total_waves), 1) if total_waves else None,
        "wind_low": wind_low,
        "wind_high": wind_high,
    }


def _daily_weather(forecast: dict, models: list[str]) -> dict[str, dict]:
    daily = forecast.get("daily") or {}
    dates = daily.get("time") or []
    primary, multi = (models[0] if models else None), len(models) > 1
    def col(name):
        # Open-Meteo daily aggregates are commonly unsuffixed even when hourly
        # model members are suffixed. Prefer the explicit member column but do
        # not discard a valid public daily field merely because it is shared.
        member = _column(daily, name, primary, multi) if primary else []
        return member or (daily.get(name) or [])
    columns = {name: col(name) for name in (
        "temperature_2m_min", "temperature_2m_max", "apparent_temperature_min",
        "apparent_temperature_max", "precipitation_sum", "uv_index_max", "weather_code",
        "sunrise", "sunset", "daylight_duration", "cloud_cover_mean",
        "precipitation_probability_max",
    )}
    timezone_name = provider_timezone(forecast)
    result = {}
    for i, local_date in enumerate(dates):
        def at(name, **bounds):
            values = columns[name]
            return valid_number(values[i] if i < len(values) else None, **bounds)
        minimum, maximum = at("temperature_2m_min"), at("temperature_2m_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            minimum = maximum = None
        code_value = columns["weather_code"][i] if i < len(columns["weather_code"]) else None
        code = int(code_value) if isinstance(code_value, (int, float)) and not isinstance(code_value, bool) else None
        sunrise_raw = columns["sunrise"][i] if i < len(columns["sunrise"]) else None
        sunset_raw = columns["sunset"][i] if i < len(columns["sunset"]) else None
        sunrise = provider_time_utc(sunrise_raw, timezone_name)
        sunset = provider_time_utc(sunset_raw, timezone_name)
        daylight = at("daylight_duration", minimum=0)
        solar_state = "normal" if sunrise and sunset else "polar_day" if daylight is not None and daylight >= 86399 else "polar_night" if daylight == 0 else "unavailable"
        result[str(local_date)] = {
            "local_date": str(local_date), "temperature_min_c": minimum,
            "temperature_max_c": maximum, "apparent_temperature_min_c": at("apparent_temperature_min"),
            "apparent_temperature_max_c": at("apparent_temperature_max"),
            "precipitation_sum_mm": at("precipitation_sum", minimum=0),
            "precipitation_probability_max_pct": at("precipitation_probability_max", minimum=0, maximum=100),
            "cloud_cover_mean_pct": at("cloud_cover_mean", minimum=0, maximum=100),
            "uv_index_max": at("uv_index_max", minimum=0), "weather_code": code,
            "weather_condition": weather_condition(code),
            "sunrise_at": sunrise.isoformat() if sunrise else None,
            "sunset_at": sunset.isoformat() if sunset else None, "solar_state": solar_state,
        }
    return result


def _day_confidence(hours: list[dict], day_index: int) -> tuple[str, str]:
    """Confidence from the day's mean wind model-disagreement, plus its source.

    Falls back to the calendar tier when the day has no hour with >= 2 models
    reporting (graceful degradation -- e.g. single-model coverage). The source
    ("spread" vs "calendar") lets the client show when confidence is backed by
    real model disagreement versus the coarser calendar heuristic.
    """
    widths = [
        wb["high"] - wb["low"]
        for h in hours
        if (wb := h.get("wind_spread")) and wb["n"] >= 2
    ]
    if not widths:
        return confidence_for_day(day_index), "calendar"
    return confidence_from_spread(sum(widths) / len(widths)), "spread"


def get_forecast_series(
    spot_id,
    days: int = MAX_FORECAST_DAYS,
    *,
    db: Session,
    client: OpenMeteoClient | None = None,
    cache: Cache | None = None,
) -> dict:
    """Daily + hourly forecast with a consensus band and per-day confidence.

    Returns at most :data:`MAX_FORECAST_DAYS` days (the horizon is hard-capped).
    Days 1–5 may contain hourly detail. Days 6–10 are daily trends without
    synthetic or leaked hourly values.
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
    mar, marine_diagnostics = _marine_for_spot(spot, lat, lon, client=client, cache=cache)
    resolved_profile = resolve_weather_profile(getattr(spot, "weather_profile", None))
    # Open-Meteo does not reliably expose a run time for every selected model.
    # The cache capture is the stable sample identity: repeated requests for the
    # same provider payload therefore hit the verification uniqueness key.
    issued_at = _forecast_sample_issued_at(fc)
    calibrations = load_calibrations(db, spot.id)
    _store_forecast_samples_once(db, spot.id, fc, models, issued_at, cache)
    hours = _merge_hours(fc, mar, models, resolved_profile, calibrations)

    instants = [h["time"] for h in hours]
    if instants != sorted(instants) or len(instants) != len(set(instants)):
        raise ValueError("forecast hourly time axis must be strictly sorted and unique")
    timezone_name = provider_timezone(fc)
    timezone_info = ZoneInfo(timezone_name)
    daily_weather = _daily_weather(fc, models)

    # Group hours by calendar date, preserving order.
    by_date: dict[str, list[dict]] = {}
    for h in hours:
        date = datetime.fromisoformat(h["time"]).astimezone(timezone_info).date().isoformat()
        by_date.setdefault(date, []).append(h)

    ordered_dates = list(by_date.keys())[:days]  # hard horizon cap
    day_records = []
    for i, date in enumerate(ordered_dates):
        confidence, confidence_source = _day_confidence(by_date[date], i)
        day_records.append({
            "date": date,
            "local_date": date,
            "confidence": confidence,
            "confidence_source": confidence_source,
            "summary": {**_day_summary(by_date[date]), **daily_weather.get(date, {})},
            "hours": by_date[date] if i < 5 else [],
            "detail": "hourly" if i < 5 else "trend",
        })

    generated_at = datetime.now(timezone.utc)
    marine_used = marine_diagnostics.get("used_coordinate")
    for hour in hours:
        hour["provenance"] = {
            "source_type": "forecast", "observation_type": "forecast",
            "source": "model", "provider": "Surfwinddata Forecast · Open-Meteo",
            "model": None, "model_family": None, "model_run": None,
            "model_run_at": None, "model_run_quality": "capture-time-only",
            "issued_at": None, "observation_at": None,
            "valid_at": hour["time"], "captured_at": generated_at,
            "calculated_at": generated_at, "spot_timezone": timezone_name,
            "requested_coordinate": {"latitude": lat, "longitude": lon},
            "used_coordinate": marine_used, "grid_distance_km": marine_diagnostics.get("grid_distance_km"),
            "spatial_resolution_km": None, "temporal_resolution_minutes": 60,
            "age_seconds": 0, "stale": False,
            "availability": Availability.AVAILABLE.value, "quality_tier": resolved_profile.quality_tier if resolved_profile else "coordinates",
            "attribution": [{"provider": "Open-Meteo", "text": "Vorhersagedaten via Open-Meteo"}],
            "uncertainty": "determined" if hour.get("wind_spread") else "not_determined",
            "data_issues": hour.get("data_issues", []),
        }

    return {
        "spot_id": spot.id,
        "model": primary_model,
        "models": models,
        "generated_at": generated_at.isoformat(),
        "observation_type": "forecast",
        "contract_version": WEATHER_CONTRACT_VERSION,
        "timezone": timezone_name,
        "calibrated": bool(calibrations),
        "availability": {
            "atmosphere": Availability.AVAILABLE.value,
            "solar": Availability.AVAILABLE.value if daily_weather else Availability.UNAVAILABLE_PROVIDER.value,
            "marine": marine_diagnostics["status"],
        },
        "days": day_records,
        "internal": {
            "units": "m/s",
            "consensus_version": "family-uv-v1",
            "physics_version": getattr(getattr(spot, "weather_profile", None), "physics_version", "wind-v1"),
            "quality_tier": resolved_profile.quality_tier if resolved_profile else "coordinates",
            "calibrated": bool(calibrations),
            "physics_shadow": physics_shadow(spot, resolved_profile),
            "model_run_quality": "capture-time-only",
            "weather_contract_version": WEATHER_CONTRACT_VERSION,
            "weather_mapping_version": WMO_MAPPING_VERSION,
            "marine": marine_diagnostics,
            "horizons": {
                "atmosphere_hours": len(hours),
                "marine_hours": len(_index_marine_hours(mar)),
                "daily_days": len(daily_weather),
            },
        },
    }
