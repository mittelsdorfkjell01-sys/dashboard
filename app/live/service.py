"""Live conditions and 7-day forecast assembly.

The cached fetch always pulls the full 7-day horizon once, so the live and the
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
    return point.y, point.x  # (lat, lon)


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
    key = cache_key(cache_model, lat, lon, "forecast_multi")
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
    wind_band = spread([_hour_at(hourly, "wind_speed_10m", m, multi, idx) for m in models])
    gust_band = spread([_hour_at(hourly, "wind_gusts_10m", m, multi, idx) for m in models])

    return {
        "spot_id": spot.id,
        "model": primary_model,
        "models": models,
        "time": cur_f.get("time"),
        "current": {
            "wind": cur_f.get("wind_speed_10m"),
            "gust": cur_f.get("wind_gusts_10m"),
            "dir": cur_f.get("wind_direction_10m"),
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


def _merge_hours(forecast: dict, marine: dict, models: list[str]) -> list[dict]:
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    multi = len(models) > 1
    src = models[0] if models else None  # dir/air from the primary model

    wind_by_model = {m: _column(hourly, "wind_speed_10m", m, multi) for m in models}
    gust_by_model = {m: _column(hourly, "wind_gusts_10m", m, multi) for m in models}
    dir_series = _column(hourly, "wind_direction_10m", src, multi) if src else []
    air_series = _column(hourly, "temperature_2m", src, multi) if src else []
    precip_series = _column(hourly, "precipitation", src, multi) if src else []
    marine_by_time = _index_marine_hours(marine)

    hours: list[dict] = []
    for i, t in enumerate(times):
        wind_vals = [wind_by_model[m][i] for m in models if i < len(wind_by_model[m])]
        gust_vals = [gust_by_model[m][i] for m in models if i < len(gust_by_model[m])]
        wind_band = spread(wind_vals)
        gust_band = spread(gust_vals)
        m = marine_by_time.get(t, {})
        hours.append(
            {
                "time": t,
                "wind": wind_band["median"] if wind_band else None,
                "gust": gust_band["median"] if gust_band else None,
                "dir": dir_series[i] if i < len(dir_series) else None,
                "air": air_series[i] if i < len(air_series) else None,
                "precip": precip_series[i] if i < len(precip_series) else None,
                "swell": m.get("swell"),
                "period": m.get("period"),
                "swell_dir": m.get("swell_dir"),
                "sst": m.get("sst"),
                "wind_spread": wind_band,
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
    nothing beyond 7 days and no climatology blending.
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
    hours = _merge_hours(fc, mar, models)

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
            "hours": by_date[date],
        }
        for i, date in enumerate(ordered_dates)
    ]

    return {
        "spot_id": spot.id,
        "model": primary_model,
        "models": models,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": day_records,
    }
