from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import TideObservation, TideSensor, TideStation
from app.schemas.common import GeoPoint


router = APIRouter(prefix="/tide-stations", tags=["tide-stations"])


def _station_dict(row: TideStation) -> dict:
    point = GeoPoint.from_geo(row.location)
    now = datetime.now(timezone.utc)
    age = (now - row.latest_observation_at).total_seconds() if row.latest_observation_at else None
    freshness = "unavailable"
    if age is not None:
        freshness = "fresh" if age <= 3600 else "delayed" if age <= 6 * 3600 else "stale"
    return {
        "id": row.id,
        "name": row.name,
        "country_code": row.country_code,
        "operator": row.operator,
        "latitude": point.lat,
        "longitude": point.lon,
        "basin": row.basin,
        "timezone": row.timezone,
        "quality": row.quality_status,
        "latest_observation_at": row.latest_observation_at,
        "freshness": freshness,
    }


@router.get("")
def list_tide_stations(
    west: float | None = Query(default=None, ge=-180, le=180),
    south: float | None = Query(default=None, ge=-90, le=90),
    east: float | None = Query(default=None, ge=-180, le=180),
    north: float | None = Query(default=None, ge=-90, le=90),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(TideStation).where(
        TideStation.public_enabled.is_(True), TideStation.status == "active"
    )
    if None not in (west, south, east, north):
        if west > east or south > north:
            raise HTTPException(status_code=422, detail="Invalid bounding box")
        polygon = (
            f"SRID=4326;POLYGON(({west} {south},{east} {south},"
            f"{east} {north},{west} {north},{west} {south}))"
        )
        stmt = stmt.where(func.ST_Intersects(
            TideStation.location, func.ST_GeogFromText(polygon)
        ))
    rows = list(db.scalars(stmt.order_by(TideStation.name).limit(limit)))
    return {"stations": [_station_dict(row) for row in rows], "count": len(rows)}


@router.get("/{station_id}/observations")
def station_observations(
    station_id: uuid.UUID,
    hours: int = Query(default=24, ge=1, le=24 * 31),
    db: Session = Depends(get_db),
) -> dict:
    station = db.get(TideStation, station_id)
    if station is None or not station.public_enabled:
        raise HTTPException(status_code=404, detail="Tide station not found")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.execute(
        select(TideObservation, TideSensor)
        .join(TideSensor, TideSensor.id == TideObservation.sensor_id)
        .where(TideSensor.station_id == station_id, TideObservation.observed_at >= since)
        .order_by(TideObservation.observed_at)
    ).all()
    return {
        "station_id": station_id,
        "observations": [
            {
                "observed_at": observation.observed_at,
                "value_m": observation.value_m,
                "datum": observation.vertical_datum or sensor.vertical_datum,
                "quality": observation.quality_status,
                "provider": sensor.provider,
            }
            for observation, sensor in rows
        ],
    }
