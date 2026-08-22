"""Persistence/orchestration for the protected V3 shadow path."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models import Spot, SpotWeatherProfile, WindClimatologyCell, WindClimatologyV3Run, WindClimatologyV3Variant
from app.wind_climatology.client import WindHistoryClient
from app.wind_climatology.service import _cell, full_year_window, haversine_km, spot_coordinates
from app.wind_climatology.v3_artifact import decode_cube, encode_cube
from app.wind_climatology.v3_direction import canonical_windows
from app.wind_climatology.v3_engine import (
    ALGORITHM_VERSION,
    COMPLETENESS_THRESHOLD,
    MIN_SAMPLE_YEARS,
    SESSION_HOURS,
    SUCCESSFUL_DAYS,
    build_variant_cube,
    prepare_hours,
    variant_key,
)

VARIANT_RANGE = {"min": 5, "max": 40, "step": 1, "open_upper": True}


def reviewed_direction_windows(db: Session, spot_id: uuid.UUID) -> list[dict[str, float]]:
    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id, SpotWeatherProfile.active.is_(True)).options(selectinload(SpotWeatherProfile.sectors)))
    if profile is None or profile.reviewed_at is None:
        return []
    return canonical_windows([{"start_deg": row.start_deg, "end_deg": row.end_deg} for row in profile.sectors if row.enabled])


def _config(*, start: int, end: int, spot_coords, requested_coords, actual_coords, windows) -> dict:
    return {
        "algorithm": ALGORITHM_VERSION,
        "period": [start, end],
        "spot_coordinates": list(spot_coords),
        "requested_coordinates": list(requested_coords),
        "actual_coordinates": list(actual_coords) if actual_coords else None,
        "direction_windows": windows,
        "session_hours": SESSION_HOURS,
        "successful_days": SUCCESSFUL_DAYS,
        "quality": {"completeness": COMPLETENESS_THRESHOLD, "min_sample_years": MIN_SAMPLE_YEARS},
        "variants": VARIANT_RANGE,
    }


def _hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def enqueue(db: Session, spot_id: uuid.UUID) -> tuple[WindClimatologyV3Run, bool]:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError("spot not found")
    cell = _cell(db, spot)
    start, end = full_year_window()
    windows = reviewed_direction_windows(db, spot.id)
    request_config = _config(start=start, end=end, spot_coords=spot_coordinates(spot), requested_coords=(cell.requested_lat, cell.requested_lon), actual_coords=(cell.actual_lat, cell.actual_lon) if cell.actual_lat is not None else None, windows=windows)
    digest = _hash(request_config)
    existing = db.scalar(select(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == spot.id, WindClimatologyV3Run.config_hash == digest, WindClimatologyV3Run.status.in_(("pending", "processing"))))
    if existing:
        return existing, False
    active = db.scalar(select(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == spot.id, WindClimatologyV3Run.config_hash == digest, WindClimatologyV3Run.is_active.is_(True)))
    if active:
        return active, False
    run = WindClimatologyV3Run(spot_id=spot.id, cell_id=cell.id, start_year=start, end_year=end, algorithm_version=ALGORITHM_VERSION, config_hash=digest, direction_windows=windows)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run, True


def process(db: Session, run_id: uuid.UUID, client: WindHistoryClient | None = None) -> WindClimatologyV3Run:
    run = db.get(WindClimatologyV3Run, run_id)
    if run is None:
        raise LookupError("V3 run not found")
    if run.status == "ready":
        return run
    spot, cell = db.get(Spot, run.spot_id), db.get(WindClimatologyCell, run.cell_id)
    if spot is None or cell is None:
        raise LookupError("V3 spot or cell not found")
    run.status, run.started_at, run.error = "processing", datetime.now(timezone.utc), None
    db.commit()
    try:
        raw = (client or WindHistoryClient()).fetch_v3(cell.requested_lat, cell.requested_lon, run.start_year, run.end_year)
        hours = prepare_hours(raw["times"], raw["speeds_kn"], raw["directions_deg"], timezone_name=raw["timezone"], spot_lat=cell.spot_lat, spot_lon=cell.spot_lon)
        cube = build_variant_cube(hours, start_year=run.start_year, end_year=run.end_year, timezone_name=raw["timezone"], usable_windows=run.direction_windows)
        artifacts = []
        artifact_bytes = 0
        for value in cube.values():
            blob, digest = encode_cube(value)
            artifact_bytes += len(blob)
            artifacts.append(WindClimatologyV3Variant(run_id=run.id, min_wind_kn=value["min_wind_kn"], max_wind_kn=value["max_wind_kn"], direction_mode=value["direction_mode"], payload_blob=blob, payload_sha256=digest, payload_bytes=len(blob)))
        final_config = _config(start=run.start_year, end=run.end_year, spot_coords=(cell.spot_lat, cell.spot_lon), requested_coords=(cell.requested_lat, cell.requested_lon), actual_coords=(raw["actual_lat"], raw["actual_lon"]), windows=run.direction_windows)
        now = datetime.now(timezone.utc)
        db.execute(update(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == run.spot_id, WindClimatologyV3Run.is_active.is_(True)).values(is_active=False))
        run.status, run.is_active, run.activated_at, run.completed_at = "ready", True, now, now
        run.config_hash, run.timezone = _hash(final_config), raw["timezone"]
        run.grid_lat, run.grid_lon = raw["actual_lat"], raw["actual_lon"]
        cell.actual_lat, cell.actual_lon = raw["actual_lat"], raw["actual_lon"]
        cell.distance_km = round(haversine_km(cell.spot_lat, cell.spot_lon, raw["actual_lat"], raw["actual_lon"]), 3)
        cell.status, cell.warnings = "ready", []
        db.add_all(artifacts)
        run.variant_count, run.artifact_bytes = len(artifacts), artifact_bytes
        run.quality_metadata = {"completeness_threshold": COMPLETENESS_THRESHOLD, "minimum_sample_years": MIN_SAMPLE_YEARS, "variant_count": len(cube), "direction_modes": ["all", "usable"] if run.direction_windows else ["all"], "grid_distance_km": round(haversine_km(cell.spot_lat, cell.spot_lon, raw["actual_lat"], raw["actual_lon"]), 3), "public_effect": "none"}
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(WindClimatologyV3Run, run_id)
        run.status, run.error, run.completed_at = "failed", f"{type(exc).__name__}: {exc}", datetime.now(timezone.utc)
        db.commit()
    return run


def status(db: Session, spot_id: uuid.UUID) -> dict:
    latest = db.scalar(select(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == spot_id).order_by(WindClimatologyV3Run.created_at.desc()))
    active = db.scalar(select(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == spot_id, WindClimatologyV3Run.is_active.is_(True)))
    cell = db.scalar(select(WindClimatologyCell).where(WindClimatologyCell.spot_id == spot_id))
    windows = reviewed_direction_windows(db, spot_id)
    def view(row):
        if row is None:
            return None
        return {"id": str(row.id), "status": row.status, "period": [row.start_year, row.end_year],
                "algorithm_version": row.algorithm_version, "config_hash": row.config_hash,
                "started_at": row.started_at, "completed_at": row.completed_at,
                "activated_at": row.activated_at, "is_active": row.is_active,
                "quality": row.quality_metadata, "warnings": row.warnings,
                "error_category": error_category(row.error), "error": row.error}
    current_hash = None
    if cell:
        spot = db.get(Spot, spot_id)
        start, end = full_year_window()
        current_hash = _hash(_config(start=start, end=end, spot_coords=spot_coordinates(spot),
            requested_coords=(cell.requested_lat, cell.requested_lon),
            actual_coords=(cell.actual_lat, cell.actual_lon) if cell.actual_lat is not None else None,
            windows=windows))
    stale = bool(active and current_hash and active.config_hash != current_hash)
    return {"state": state_label(latest, active, stale), "stale": stale, "latest": view(latest),
            "active": view(active), "directions": {"reviewed": bool(windows), "windows": windows,
            "usable_available": bool(windows)}, "cell": cell_view(cell), "public_effect": "none"}


def cell_view(cell: WindClimatologyCell | None) -> dict | None:
    if cell is None:
        return None
    return {"mode": cell.selection_mode, "spot": [cell.spot_lat, cell.spot_lon],
            "requested": [cell.requested_lat, cell.requested_lon],
            "actual": [cell.actual_lat, cell.actual_lon] if cell.actual_lat is not None else None,
            "distance_km": cell.distance_km, "model": cell.model,
            "resolution_degrees": cell.resolution_deg, "status": cell.status,
            "warnings": cell.warnings}


def state_label(latest, active, stale: bool) -> str:
    if latest is None: return "not_calculated"
    if latest.status == "pending": return "refresh_pending" if active else "pending"
    if latest.status == "processing": return "refresh_processing" if active else "processing"
    if latest.status == "failed": return "failed_active_preserved" if active else "failed_no_active"
    if stale: return "stale"
    quality = (active.quality_metadata or {}).get("quality_status") if active else None
    return "limited" if quality == "limited" else "complete"


def error_category(error: str | None) -> str | None:
    if not error: return None
    value = error.lower()
    if any(key in value for key in ("coordinate", "grid", "latitude", "longitude")): return "coordinates"
    if any(key in value for key in ("valid", "schema", "missing", "timezone")): return "validation"
    if any(key in value for key in ("timeout", "http", "network", "provider", "open-meteo")): return "provider"
    return "unknown"


def set_cell(db: Session, spot_id: uuid.UUID, *, mode: str, lat: float | None, lon: float | None):
    spot = db.get(Spot, spot_id)
    if spot is None: raise LookupError("spot not found")
    if mode not in {"automatic", "manual"}: raise ValueError("invalid cell selection mode")
    if mode == "manual" and (lat is None or lon is None): raise ValueError("manual coordinates required")
    if lat is not None and not -90 <= lat <= 90: raise ValueError("invalid latitude")
    if lon is not None and not -180 <= lon <= 180: raise ValueError("invalid longitude")
    cell = _cell(db, spot)
    spot_lat, spot_lon = spot_coordinates(spot)
    requested = (spot_lat, spot_lon) if mode == "automatic" else (float(lat), float(lon))
    changed = cell.selection_mode != mode or (cell.requested_lat, cell.requested_lon) != requested
    cell.selection_mode, cell.spot_lat, cell.spot_lon = mode, spot_lat, spot_lon
    cell.requested_lat, cell.requested_lon = requested
    if changed:
        cell.status, cell.actual_lat, cell.actual_lon, cell.distance_km = "pending", None, None, None
        db.flush()
        run, created = enqueue(db, spot_id)
        return cell, run, created
    db.commit()
    return cell, None, False


def operations(db: Session, *, limit: int = 30) -> dict:
    spots = db.scalars(select(Spot)).all()
    cells = {row.spot_id: row for row in db.scalars(select(WindClimatologyCell)).all()}
    profiles = {row.spot_id: row for row in db.scalars(select(SpotWeatherProfile).options(selectinload(SpotWeatherProfile.sectors))).all()}
    active_by_spot = {row.spot_id: row for row in db.scalars(select(WindClimatologyV3Run).where(WindClimatologyV3Run.is_active.is_(True))).all()}
    latest_by_spot = {row.spot_id: row for row in db.scalars(select(WindClimatologyV3Run).distinct(WindClimatologyV3Run.spot_id).order_by(WindClimatologyV3Run.spot_id, WindClimatologyV3Run.created_at.desc())).all()}
    start, end = full_year_window()
    stale_spots = set()
    for spot in spots:
        active, cell, profile = active_by_spot.get(spot.id), cells.get(spot.id), profiles.get(spot.id)
        if not active or not cell: continue
        windows = canonical_windows([{"start_deg": row.start_deg, "end_deg": row.end_deg}
            for row in profile.sectors if row.enabled]) if profile and profile.active and profile.reviewed_at else []
        digest = _hash(_config(start=start, end=end, spot_coords=spot_coordinates(spot),
            requested_coords=(cell.requested_lat, cell.requested_lon),
            actual_coords=(cell.actual_lat, cell.actual_lon) if cell.actual_lat is not None else None,
            windows=windows))
        if digest != active.config_hash: stale_spots.add(spot.id)
    latest_rows = db.scalars(select(WindClimatologyV3Run).order_by(WindClimatologyV3Run.created_at.desc()).limit(limit)).all()
    spot_ids = list({row.spot_id for row in latest_rows})
    names = {s.id: s.name for s in db.scalars(select(Spot).where(Spot.id.in_(spot_ids))).all()} if spot_ids else {}
    active_spots = set(active_by_spot)
    inflight_spots = {spot_id for spot_id, row in latest_by_spot.items() if row.status in {"pending", "processing"}}
    failed_spots = {spot_id for spot_id, row in latest_by_spot.items() if row.status == "failed"}
    missing_spots = {spot.id for spot in spots if spot.id not in latest_by_spot}
    current = len(active_spots - stale_spots)
    rows = []
    for run in latest_rows:
        rows.append({"run_id": str(run.id), "spot_id": str(run.spot_id), "spot_name": names.get(run.spot_id),
            "status": run.status, "period": [run.start_year, run.end_year], "algorithm_version": run.algorithm_version,
            "quality_status": (run.quality_metadata or {}).get("quality_status"), "created_at": run.created_at,
            "started_at": run.started_at, "completed_at": run.completed_at,
            "duration_s": round((run.completed_at-run.started_at).total_seconds(), 1) if run.started_at and run.completed_at else None,
            "error_category": error_category(run.error), "has_active_version": run.spot_id in active_spots})
    queue_depth = db.scalar(select(func.count()).select_from(WindClimatologyV3Run).where(WindClimatologyV3Run.status == "pending")) or 0
    return {"counts": {"current": current, "missing": len(missing_spots),
            "failed": len(failed_spots), "inflight": len(inflight_spots),
            "stale": len(stale_spots)}, "queue_depth": queue_depth, "recent_runs": rows, "public_effect": "none"}


def variant(db: Session, spot_id: uuid.UUID, *, min_wind_kn: int, max_wind_kn: int | None, direction_mode: str) -> dict:
    run = db.scalar(select(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == spot_id, WindClimatologyV3Run.is_active.is_(True)))
    if run is None:
        raise LookupError("no active V3 shadow run")
    if direction_mode not in {"all", "usable"}:
        raise ValueError("invalid direction mode")
    if not 5 <= min_wind_kn <= 40 or (max_wind_kn is not None and not min_wind_kn < max_wind_kn <= 40):
        raise ValueError("invalid V3 wind window")
    row = db.scalar(select(WindClimatologyV3Variant).where(WindClimatologyV3Variant.run_id == run.id, WindClimatologyV3Variant.min_wind_kn == min_wind_kn, WindClimatologyV3Variant.max_wind_kn.is_(None) if max_wind_kn is None else WindClimatologyV3Variant.max_wind_kn == max_wind_kn, WindClimatologyV3Variant.direction_mode == direction_mode))
    if row is None:
        raise LookupError("V3 variant unavailable")
    selected = decode_cube(row.payload_blob)
    key = variant_key(min_wind_kn, max_wind_kn, direction_mode)
    return {"run_id": str(run.id), "algorithm_version": run.algorithm_version, "period": [run.start_year, run.end_year], "quality": run.quality_metadata, "variant": selected, "cache_key": f"wind-climatology-v3:{run.id}:{key}", "public_effect": "none"}
