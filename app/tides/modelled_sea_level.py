"""Conservative public fallback built from Open-Meteo modelled sea level.

This is deliberately not an astronomical FES prediction. The source combines
ocean tide, inverted-barometer and other sea-level components on a coarse
marine grid. It gives European marine spots a useful zero-cost trend while the
private FES atlas is unavailable, with explicit provenance and safety limits.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tides.calculation import CurvePoint, detect_extrema, phase_at

SOURCE_NAME = "Open-Meteo Marine"
SOURCE_URL = "https://open-meteo.com/en/docs/marine-weather-api"
ATTRIBUTION = "Open-Meteo Marine · Datenquelle: Copernicus Marine / Météo-France"
MODEL_NAME = "Open-Meteo Marine Best Match"
EVENT_UNCERTAINTY_MINUTES = 90


def _instant(value: object, timezone_name: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
            except ZoneInfoNotFoundError:
                parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _captured_at(payload: dict, fallback: datetime) -> datetime:
    parsed = _instant(payload.get("_cache_captured_at"), "UTC")
    return parsed or fallback


def _unavailable(message: str) -> dict:
    return {
        "available": False,
        "product_type": "modelled_sea_level",
        "message": message,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "attribution": ATTRIBUTION,
    }


def public_modelled_sea_level(
    spot_id: uuid.UUID,
    payload: dict,
    *,
    days: int,
    display_timezone: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Normalize one cached Marine API response into the public tide contract."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    requested_days = max(1, min(10, int(days)))
    hourly = payload.get("hourly") or {}
    raw_times = hourly.get("time") or []
    raw_levels = hourly.get("sea_level_height_msl") or []
    if not isinstance(raw_times, list) or not isinstance(raw_levels, list):
        return _unavailable("Der modellierte Wasserstand ist momentan nicht verfügbar.")

    provider_timezone = str(payload.get("timezone") or "UTC")
    points: list[CurvePoint] = []
    for raw_time, raw_level in zip(raw_times, raw_levels, strict=False):
        instant = _instant(raw_time, provider_timezone)
        try:
            level = float(raw_level)
        except (TypeError, ValueError):
            continue
        if instant is not None and math.isfinite(level):
            points.append(CurvePoint(instant, level))
    points.sort(key=lambda item: item.time)

    requested_end = current + timedelta(days=requested_days)
    context_start = current - timedelta(hours=15)
    window = [point for point in points if context_start <= point.time <= requested_end]
    future = [point for point in window if point.time >= current]
    if len(window) < 4 or len(future) < 2:
        return _unavailable("Für diesen Küstenpunkt liefert das Modell derzeit keine vollständige Wasserstandskurve.")

    extrema = detect_extrema(window, minimum_separation_minutes=180)
    event_pairs = [(item.event_type, item.time) for item in extrema]
    phase, cycle_position = phase_at(event_pairs, current)
    if phase == "unavailable":
        phase = "rising" if future[1].height >= future[0].height else "falling"

    low = min(point.height for point in future)
    high = max(point.height for point in future)
    spread = high - low
    series = []
    for point in future:
        point_phase, _ = phase_at(event_pairs, point.time)
        if point_phase == "unavailable":
            point_phase = phase
        normalized = 0.5 if spread <= 1e-9 else (point.height - low) / spread
        series.append({
            "time": point.time,
            "level_normalized": round(min(1.0, max(0.0, normalized)), 4),
            "level_m": round(point.height, 3),
            "phase": point_phase,
        })

    namespace = uuid.UUID("d98dddb2-8797-4bc8-b748-a9b7da94972e")
    events = [{
        "id": uuid.uuid5(namespace, f"{spot_id}:{item.event_type}:{item.time.isoformat()}"),
        "event_type": item.event_type,
        "time": item.time,
        "uncertainty_minutes": EVENT_UNCERTAINTY_MINUTES,
    } for item in extrema if context_start <= item.time <= requested_end]

    forecast_end = min(requested_end, future[-1].time)
    partial = forecast_end < requested_end - timedelta(hours=1)
    current_point = min(future, key=lambda item: abs((item.time - current).total_seconds()))
    available_hours = max(0.0, (forecast_end - current).total_seconds() / 3600)
    horizon_days = max(1, min(requested_days, math.ceil(available_hours / 24)))
    shown_timezone = display_timezone or ("UTC" if provider_timezone == "GMT" else provider_timezone)

    return {
        "available": True,
        "product_type": "modelled_sea_level",
        "message": (
            "Der verfügbare Modellhorizont ist kürzer als angefordert. "
            if partial else ""
        ) + "Begrenzte Genauigkeit an Küsten, in Buchten und Flussmündungen.",
        "timezone": shown_timezone,
        "phase": phase,
        "cycle_position": cycle_position,
        "quality": "model_only",
        "approximate": True,
        "last_calculated_at": _captured_at(payload, current),
        "valid_until": forecast_end,
        "forecast_start": future[0].time,
        "forecast_end": forecast_end,
        "horizon_days": horizon_days,
        "partial": partial,
        "datum": "mean_sea_level",
        "current_level_m": round(current_point.height, 3),
        "navigational": False,
        "model_name": MODEL_NAME,
        "model_version": None,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "attribution": ATTRIBUTION,
        "events": events,
        "series": series,
    }
