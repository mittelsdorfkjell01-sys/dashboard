from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import date, datetime, timezone

from geoalchemy2.shape import to_shape
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Spot, WindClimatologyCell, WindClimatologyRun
from app.wind_climatology.aggregate import ALGORITHM_VERSION, aggregate
from app.wind_climatology.client import WindHistoryClient


def full_year_window(today: date | None = None) -> tuple[int, int]:
    end = (today or date.today()).year - 1
    return end - 19, end


def spot_coordinates(spot: Spot) -> tuple[float, float]:
    point = to_shape(spot.location)
    return float(point.y), float(point.x)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cell(db: Session, spot: Spot) -> WindClimatologyCell:
    lat, lon = spot_coordinates(spot)
    cell = db.scalar(select(WindClimatologyCell).where(WindClimatologyCell.spot_id == spot.id))
    if cell is None:
        cell = WindClimatologyCell(spot_id=spot.id, spot_lat=lat, spot_lon=lon, requested_lat=lat, requested_lon=lon)
        db.add(cell)
        db.flush()
    elif cell.selection_mode == "automatic":
        cell.spot_lat = cell.requested_lat = lat
        cell.spot_lon = cell.requested_lon = lon
    return cell


def enqueue(db: Session, spot_id: uuid.UUID, *, force: bool = False) -> tuple[WindClimatologyRun, bool]:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError("spot not found")
    cell = _cell(db, spot)
    start, end = full_year_window()
    config = {"algorithm": ALGORITHM_VERSION, "start": start, "end": end, "spot": [cell.spot_lat, cell.spot_lon], "request": [cell.requested_lat, cell.requested_lon]}
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot.id, WindClimatologyRun.config_hash == digest, WindClimatologyRun.status.in_(("pending", "processing"))))
    if existing:
        return existing, False
    active = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot.id, WindClimatologyRun.config_hash == digest, WindClimatologyRun.is_active.is_(True)))
    if active and not force:
        return active, False
    run = WindClimatologyRun(spot_id=spot.id, cell_id=cell.id, start_year=start, end_year=end, algorithm_version=ALGORITHM_VERSION, config_hash=digest)
    cell.status = "pending"
    db.add(run)
    db.commit()
    return run, True


def process(db: Session, run_id: uuid.UUID, client: WindHistoryClient | None = None) -> WindClimatologyRun:
    run = db.get(WindClimatologyRun, run_id)
    if run is None:
        raise LookupError("climatology run not found")
    if run.status == "ready":
        return run
    cell, spot = db.get(WindClimatologyCell, run.cell_id), db.get(Spot, run.spot_id)
    if cell is None or spot is None:
        raise LookupError("climatology cell or spot not found")
    run.status, run.started_at, cell.status = "processing", datetime.now(timezone.utc), "processing"
    db.commit()
    try:
        raw = (client or WindHistoryClient()).fetch(cell.requested_lat, cell.requested_lon, run.start_year, run.end_year)
        annual, public = aggregate(raw["times"], raw["speeds_kn"], timezone_name=raw["timezone"], spot_lat=cell.spot_lat, spot_lon=cell.spot_lon, start_year=run.start_year, end_year=run.end_year)
        distance = haversine_km(cell.spot_lat, cell.spot_lon, raw["actual_lat"], raw["actual_lon"])
        warnings = ([{"code": "large_cell_distance", "distance_km": round(distance, 1)}] if distance > 30 else [])
        now = datetime.now(timezone.utc)
        public.update({"updated_at": now.isoformat(), "grid": {"resolution_degrees": 0.25}, "attribution": "Open-Meteo Historical Weather API · ERA5"})
        db.execute(update(WindClimatologyRun).where(WindClimatologyRun.spot_id == run.spot_id, WindClimatologyRun.is_active.is_(True)).values(is_active=False))
        run.status, run.quality_status, run.is_active = "ready", "passed", True
        run.annual_aggregates, run.public_data, run.warnings = annual, public, warnings
        run.timezone, run.grid_lat, run.grid_lon, run.unit = raw["timezone"], raw["actual_lat"], raw["actual_lon"], "kn"
        run.completed_at = run.activated_at = now
        cell.actual_lat, cell.actual_lon, cell.distance_km = raw["actual_lat"], raw["actual_lon"], distance
        cell.status, cell.warnings = "ready", warnings
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(WindClimatologyRun, run_id)
        cell = db.get(WindClimatologyCell, run.cell_id)
        run.status, run.quality_status, run.error = "failed", "failed", f"{type(exc).__name__}: {exc}"
        run.completed_at, cell.status = datetime.now(timezone.utc), "failed"
        db.commit()
    return run


def public_state(db: Session, spot_id: uuid.UUID) -> dict:
    active = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot_id, WindClimatologyRun.is_active.is_(True)))
    latest = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot_id).order_by(WindClimatologyRun.created_at.desc()))
    if active:
        data = dict(active.public_data or {})
        data["status"] = "ready"
        if latest and latest.id != active.id and latest.status in {"pending", "processing"}:
            data["refresh_status"] = latest.status
        return data
    return {"status": latest.status if latest else "unavailable"}


def set_cell(db: Session, spot_id: uuid.UUID, *, mode: str, lat: float | None = None, lon: float | None = None) -> WindClimatologyRun:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError("spot not found")
    cell = _cell(db, spot)
    spot_lat, spot_lon = spot_coordinates(spot)
    if mode == "automatic":
        cell.requested_lat, cell.requested_lon = spot_lat, spot_lon
    elif mode == "manual" and lat is not None and lon is not None:
        cell.requested_lat, cell.requested_lon = lat, lon
    else:
        raise ValueError("manual mode requires latitude and longitude")
    cell.selection_mode, cell.spot_lat, cell.spot_lon = mode, spot_lat, spot_lon
    cell.selected_at, cell.status = datetime.now(timezone.utc), "pending"
    db.commit()
    return enqueue(db, spot_id, force=True)[0]


def backfill(db: Session, *, limit: int = 2) -> list[WindClimatologyRun]:
    spots = db.scalars(select(Spot).where(Spot.status == "published").order_by(Spot.updated_at)).all()
    queued = []
    for spot in spots:
        run, created = enqueue(db, spot.id)
        if created:
            queued.append(run)
            if len(queued) >= limit:
                break
    return queued
