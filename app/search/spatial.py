"""PostGIS spatial queries: nearby radius, drawn geometry, area bounds.

All functions return ``list[(Spot, distance_m | None)]`` ordered by distance from
the relevant reference point, optionally filtered to spots offering ``sport``.
"""

from __future__ import annotations

from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models import Spot
from app.public_catalog import PUBLISHED

# Adaptive-radius defaults for nearby search.
START_RADIUS_KM = 25.0
MAX_RADIUS_KM = 200.0
MIN_RESULTS = 3


def _point_geog(lat: float, lon: float):
    return cast(func.ST_MakePoint(lon, lat), Geography)


def _sport_filter(stmt, sport: str | None):
    return stmt.where(Spot.sports.any(sport)) if sport else stmt


def _within_radius(
    db: Session, lat: float, lon: float, radius_km: float, sport: str | None
) -> list[tuple[Spot, float]]:
    center = _point_geog(lat, lon)
    dist = func.ST_Distance(Spot.location, center).label("d")
    stmt = _sport_filter(
        select(Spot, dist).where(
            Spot.status == PUBLISHED,
            func.ST_DWithin(Spot.location, center, radius_km * 1000.0),
        ),
        sport,
    ).order_by("d").limit(2_000)
    return [(row[0], float(row[1])) for row in db.execute(stmt).all()]


def search_nearby_spots(
    point: dict,
    sport: str | None,
    *,
    db: Session,
    start_km: float = START_RADIUS_KM,
    max_km: float = MAX_RADIUS_KM,
    min_results: int = MIN_RESULTS,
) -> list[tuple[Spot, float]]:
    """``ST_DWithin`` with an adaptive radius.

    Starts at ``start_km`` (default 25 km) and doubles the radius until at least
    ``min_results`` spots are found or ``max_km`` is reached.
    """
    lat, lon = point["lat"], point["lon"]
    all_rows = _within_radius(db, lat, lon, max_km, sport)
    radius = start_km
    while radius < max_km:
        rows = [row for row in all_rows if row[1] <= radius * 1000]
        if len(rows) >= min_results:
            return rows
        radius = min(radius * 2.0, max_km)
    return all_rows


def search_by_geometry(
    shape: dict, sport: str | None, *, db: Session
) -> list[tuple[Spot, float | None]]:
    """Spots inside a drawn geometry.

    ``shape`` is either ``{"type": "circle", "center": {lat, lon}, "radius_km": r}``
    -> ``ST_DWithin``, or ``{"type": "rectangle", "bounds": {...}}`` -> ``ST_Within``.
    """
    kind = shape.get("type")
    if kind == "circle":
        c = shape["center"]
        return _within_radius(db, c["lat"], c["lon"], float(shape["radius_km"]), sport)
    if kind == "rectangle":
        return bounds_query(shape["bounds"], sport, db=db)
    raise ValueError(f"unsupported shape type: {kind!r}")


def bounds_query(
    bounds: dict, sport: str | None, *, db: Session
) -> list[tuple[Spot, float | None]]:
    """Spots within an axis-aligned bbox via ``ST_Within`` (not a centre radius)."""
    envelope = func.ST_MakeEnvelope(
        bounds["min_lon"], bounds["min_lat"], bounds["max_lon"], bounds["max_lat"], 4326
    )
    center = _point_geog(
        (bounds["min_lat"] + bounds["max_lat"]) / 2.0,
        (bounds["min_lon"] + bounds["max_lon"]) / 2.0,
    )
    dist = func.ST_Distance(Spot.location, center).label("d")
    stmt = _sport_filter(
        select(Spot, dist).where(
            Spot.status == PUBLISHED,
            func.ST_Within(cast(Spot.location, Geometry), envelope)
        ),
        sport,
    ).order_by("d").limit(2_000)
    return [(row[0], float(row[1])) for row in db.execute(stmt).all()]


def filter_spots_by_sport(spots: list[Any], sport: str | None) -> list[Any]:
    """Pure helper mirroring the SQL ``sports`` filter (used for sport toggles)."""
    if not sport:
        return list(spots)
    return [s for s in spots if sport in (getattr(s, "sports", None) or [])]
