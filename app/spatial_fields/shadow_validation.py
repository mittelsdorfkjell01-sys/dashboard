"""Phase-5 shadow comparison of legacy spot forecasts and published fields.

This module writes internal evidence only. It never changes a forecast snapshot,
field publication, model preference, calibration, or public cache.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import uuid

from geoalchemy2.shape import to_shape
from sqlalchemy import select

from app.models import ForecastSnapshot, Region, Spot
from app.models.weather_field import WeatherFieldPublication, WeatherFieldRun
from app.models.weather_field_shadow import (
    WeatherFieldShadowMetric,
    WeatherFieldShadowRun,
    WeatherFieldShadowSample,
)
from app.spatial_fields.serving import FieldSampleUnavailable, sample_active_field
from app.weather.vectors import wind_to_uv

KNOT_TO_MS = 0.514444
PROFILE_VERSION = "field-shadow-v1"


def horizon_bucket(hours: int) -> str | None:
    if 0 <= hours < 6:
        return "T+0-6"
    if 6 <= hours < 24:
        return "T+6-24"
    if 24 <= hours < 48:
        return "T+24-48"
    if 48 <= hours <= 72:
        return "T+48-72"
    if hours > 72:
        return "T+72+"
    return None


def circular_difference_deg(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return abs((float(left) - float(right) + 180.0) % 360.0 - 180.0)


def _direction_sector(direction: float | None) -> str:
    if direction is None:
        return "calm_or_unknown"
    labels = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return labels[int((float(direction) + 22.5) % 360 // 45)]


def _speed_band(speed_ms: float) -> str:
    if speed_ms < 5:
        return "0-5m/s"
    if speed_ms < 10:
        return "5-10m/s"
    if speed_ms < 15:
        return "10-15m/s"
    return "15m/s+"


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _legacy_wind(hour: dict) -> dict | None:
    speed = _number(hour.get("wind_ms"))
    if speed is None:
        knots = _number(hour.get("wind"))
        speed = knots * KNOT_TO_MS if knots is not None else None
    if speed is None or speed < 0:
        return None
    direction = _number(hour.get("dir"))
    if direction is not None:
        direction %= 360.0
    u = _number(hour.get("wind_u_ms"))
    v = _number(hour.get("wind_v_ms"))
    if (u is None or v is None) and direction is not None:
        u, v = wind_to_uv(speed, direction)
    gust = _number(hour.get("gust_ms"))
    if gust is None:
        gust_knots = _number(hour.get("gust"))
        gust = gust_knots * KNOT_TO_MS if gust_knots is not None else None
    return {"speed": speed, "direction": direction, "u": u, "v": v, "gust": gust}


def _forecast_hours(snapshot: ForecastSnapshot):
    for day in (snapshot.payload or {}).get("days", []):
        for hour in day.get("hours", []):
            try:
                valid_at = datetime.fromisoformat(str(hour["time"]).replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                continue
            if valid_at.tzinfo is None:
                continue
            yield valid_at.astimezone(timezone.utc), hour


def _pilot_entries(path: str, group: str) -> tuple[set[uuid.UUID], set[str]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), set()
    ids: set[uuid.UUID] = set()
    names: set[str] = set()
    for item in payload if isinstance(payload, list) else []:
        if group != "all" and item.get("group") != group:
            continue
        if item.get("name"):
            names.add(str(item["name"]).strip().casefold())
        try:
            if item.get("spot_id"):
                ids.add(uuid.UUID(str(item["spot_id"])))
        except ValueError:
            continue
    return ids, names


def _pilot_spots(db, *, settings, explicit_spot_ids=None):
    configured_ids, configured_names = _pilot_entries(
        settings.weather_field_shadow_pilot_config,
        settings.weather_field_shadow_pilot_group,
    )
    ids = {uuid.UUID(str(value)) for value in explicit_spot_ids or configured_ids}
    if explicit_spot_ids:
        configured_names = set()
    rows = db.execute(
        select(Spot, Region)
        .join(Region, Region.id == Spot.region_id, isouter=True)
        .where(Spot.status == "published")
        .order_by(Spot.name)
    ).all()
    selected = []
    for spot, region in rows:
        if ids or configured_names:
            if spot.id not in ids and spot.name.strip().casefold() not in configured_names:
                continue
        snapshot = db.scalar(
            select(ForecastSnapshot)
            .where(
                ForecastSnapshot.spot_id == spot.id,
                ForecastSnapshot.active.is_(True),
            )
            .order_by(ForecastSnapshot.generated_at.desc())
            .limit(1)
        )
        selected.append((spot, region, snapshot))
        if len(selected) >= settings.weather_field_shadow_max_spots:
            break
    return selected


def comparison_metrics(samples: list[dict]) -> dict:
    speed = [float(row["speed_delta_ms"]) for row in samples]
    direction = [
        float(row["direction_delta_deg"])
        for row in samples
        if row.get("direction_delta_deg") is not None
    ]
    gust = [
        float(row["gust_delta_ms"])
        for row in samples
        if row.get("gust_delta_ms") is not None
    ]

    def errors(values: list[float]) -> dict | None:
        if not values:
            return None
        return {
            "bias_ms": sum(values) / len(values),
            "mae_ms": sum(abs(value) for value in values) / len(values),
            "rmse_ms": math.sqrt(sum(value * value for value in values) / len(values)),
            "count": len(values),
        }

    return {
        "speed": errors(speed),
        "direction_mae_deg": (
            sum(direction) / len(direction) if direction else None
        ),
        "direction_count": len(direction),
        "gust": errors(gust),
        "interpretation": "field_minus_existing_spot_forecast",
    }


def _metric_groups(samples: list[dict]):
    groups: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        dimensions = sample["dimensions"]
        groups[json.dumps({"scope": "overall"}, sort_keys=True)].append(sample)
        for keys in (
            ("horizon",),
            ("region", "horizon"),
            ("country", "horizon"),
            ("water_type", "horizon"),
            ("direction_sector", "horizon"),
            ("speed_band", "horizon"),
        ):
            selected = {key: dimensions[key] for key in keys}
            groups[json.dumps(selected, sort_keys=True)].append(sample)
    for serialized, rows in groups.items():
        yield json.loads(serialized), rows


def run_shadow_validation(
    db,
    *,
    job_id: uuid.UUID,
    publication_id: uuid.UUID,
    settings,
    storage,
    explicit_spot_ids=None,
    now: datetime | None = None,
) -> dict:
    instant = now or datetime.now(timezone.utc)
    publication = db.get(WeatherFieldPublication, publication_id)
    if publication is None:
        raise LookupError("weather-field shadow publication not found")
    field_run = db.get(WeatherFieldRun, publication.run_id)
    if field_run is None or field_run.status != "ready":
        raise ValueError("weather-field shadow run is not ready")

    shadow = WeatherFieldShadowRun(
        job_id=job_id,
        publication_id=publication.id,
        field_run_id=field_run.id,
        profile_version=settings.weather_field_shadow_profile_version,
        status="processing",
        config={
            "pilot_config": settings.weather_field_shadow_pilot_config,
            "pilot_group": settings.weather_field_shadow_pilot_group,
            "max_spots": settings.weather_field_shadow_max_spots,
            "max_samples": settings.weather_field_shadow_max_samples,
            "max_horizon_hours": settings.weather_field_shadow_max_horizon_hours,
            "public_effect": "none",
        },
        started_at=instant,
    )
    db.add(shadow)
    db.flush()

    comparisons: list[dict] = []
    skipped = defaultdict(int)
    selected = _pilot_spots(
        db, settings=settings, explicit_spot_ids=explicit_spot_ids
    )
    valid_start = datetime.fromisoformat(field_run.valid_times[0].replace("Z", "+00:00"))
    valid_end = datetime.fromisoformat(field_run.valid_times[-1].replace("Z", "+00:00"))
    for spot, region, snapshot in selected:
        if snapshot is None:
            skipped["active_snapshot_missing"] += 1
            continue
        point = to_shape(spot.location)
        for valid_at, hour in _forecast_hours(snapshot):
            lead_hours = int((valid_at - snapshot.generated_at).total_seconds() // 3600)
            field_lead = int((valid_at - field_run.model_run_at).total_seconds() // 3600)
            if lead_hours < 0 or field_lead < 0:
                skipped["negative_lead"] += 1
                continue
            if lead_hours > settings.weather_field_shadow_max_horizon_hours:
                continue
            if not valid_start <= valid_at <= valid_end:
                skipped["outside_field_horizon"] += 1
                continue
            legacy = _legacy_wind(hour)
            if legacy is None:
                skipped["legacy_wind_missing"] += 1
                continue
            try:
                field = sample_active_field(
                    db,
                    storage=storage,
                    scope_key=settings.weather_field_scope_key,
                    latitude=point.y,
                    longitude=point.x,
                    valid_at=valid_at,
                )
            except FieldSampleUnavailable:
                skipped["field_sample_missing"] += 1
                continue
            if field["publication_id"] != str(publication.id):
                raise RuntimeError("active weather-field publication changed during shadow validation")
            bucket = horizon_bucket(lead_hours)
            if bucket is None:
                continue
            dimensions = {
                "horizon": bucket,
                "region": region.slug if region else "unassigned",
                "country": region.country if region and region.country else "unknown",
                "water_type": sorted(spot.water_type or ["unknown"])[0],
                "direction_sector": _direction_sector(legacy["direction"]),
                "speed_band": _speed_band(legacy["speed"]),
                "field_model": field["model"],
            }
            direction_delta = circular_difference_deg(
                field["direction_from_deg"], legacy["direction"]
            )
            gust_delta = (
                float(field["gust_ms"]) - legacy["gust"]
                if field.get("gust_ms") is not None and legacy["gust"] is not None
                else None
            )
            comparison = {
                "dimensions": dimensions,
                "speed_delta_ms": float(field["speed_ms"]) - legacy["speed"],
                "direction_delta_deg": direction_delta,
                "gust_delta_ms": gust_delta,
            }
            comparisons.append(comparison)
            db.add(
                WeatherFieldShadowSample(
                    shadow_run_id=shadow.id,
                    spot_id=spot.id,
                    snapshot_id=snapshot.id,
                    valid_at=valid_at,
                    lead_hours=lead_hours,
                    field_lead_hours=field_lead,
                    horizon_bucket=bucket,
                    dimensions=dimensions,
                    legacy_u_ms=legacy["u"],
                    legacy_v_ms=legacy["v"],
                    legacy_speed_ms=legacy["speed"],
                    legacy_direction_deg=legacy["direction"],
                    legacy_gust_ms=legacy["gust"],
                    field_u_ms=field["u_ms"],
                    field_v_ms=field["v_ms"],
                    field_speed_ms=field["speed_ms"],
                    field_direction_deg=field["direction_from_deg"],
                    field_gust_ms=field.get("gust_ms"),
                    speed_delta_ms=comparison["speed_delta_ms"],
                    direction_delta_deg=direction_delta,
                    gust_delta_ms=gust_delta,
                )
            )
            if len(comparisons) >= settings.weather_field_shadow_max_samples:
                break
        if len(comparisons) >= settings.weather_field_shadow_max_samples:
            break

    if comparisons:
        for dimensions, rows in _metric_groups(comparisons):
            canonical = json.dumps(dimensions, sort_keys=True, separators=(",", ":"))
            db.add(
                WeatherFieldShadowMetric(
                    shadow_run_id=shadow.id,
                    dimension_hash=hashlib.sha256(canonical.encode()).hexdigest(),
                    dimensions=dimensions,
                    sample_count=len(rows),
                    metrics=comparison_metrics(rows),
                    computed_at=instant,
                )
            )
        shadow.status = "succeeded"
    else:
        shadow.status = "no_data"
    shadow.completed_at = datetime.now(timezone.utc)
    shadow.diagnostics = {
        "pilot_spots": len(selected),
        "samples": len(comparisons),
        "skipped": dict(skipped),
        "evidence_status": "collecting" if comparisons else "awaiting_forecast_snapshots",
        "cutover_authorized": False,
        "public_effect": "none",
    }
    db.flush()
    return {
        "shadow_run_id": str(shadow.id),
        "status": shadow.status,
        **shadow.diagnostics,
    }
