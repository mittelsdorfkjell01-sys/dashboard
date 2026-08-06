"""Central duplicate classification for catalogue writes.

Exact duplicates are never overridable and remain race-safe through database
unique constraints. Likely duplicates require an explicit, per-request admin
override; no persistent bypass flag is stored.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.names import normalize_name


@dataclass(frozen=True)
class DuplicateResult:
    exact: list[dict[str, Any]]
    likely: list[dict[str, Any]]


class ExactDuplicateError(ValueError):
    def __init__(self, entity: str, candidates: list[dict[str, Any]]):
        article = "Dieser" if entity == "Spot" else "Diese"
        super().__init__(f"{article} {entity} existiert bereits.")
        self.entity = entity
        self.candidates = candidates


class LikelyDuplicateError(ValueError):
    def __init__(self, entity: str, candidates: list[dict[str, Any]]):
        super().__init__(f"Mögliche Dublette für {entity} gefunden.")
        self.entity = entity
        self.candidates = candidates


def _distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat_a), math.radians(lat_b)
    dp = math.radians(lat_b - lat_a)
    dl = math.radians(lon_b - lon_a)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _coordinates(value) -> tuple[float, float] | None:
    if value is None:
        return None
    point = to_shape(value)
    return float(point.y), float(point.x)


def _rounded_distance(distance: float | None) -> int | None:
    return round(distance) if distance is not None else None


def find_spot_duplicates(
    db: Session,
    *,
    name: str,
    region_id: uuid.UUID | None,
    lat: float,
    lon: float,
    exclude_id: uuid.UUID | None = None,
) -> DuplicateResult:
    from app.models import Region, Spot

    normalized = normalize_name(name)
    similarity = func.similarity(Spot.normalized_name, normalized)
    stmt = (
        select(Spot, Region.name, similarity)
        .outerjoin(Region, Region.id == Spot.region_id)
        .where(similarity >= 0.60)
        .order_by(similarity.desc())
        .limit(50)
    )
    if exclude_id is not None:
        stmt = stmt.where(Spot.id != exclude_id)

    exact: list[dict[str, Any]] = []
    likely: list[dict[str, Any]] = []
    for candidate, region_name, score in db.execute(stmt).all():
        coords = _coordinates(candidate.location)
        distance = _distance_m(lat, lon, *coords) if coords is not None else None
        same_region = candidate.region_id == region_id
        item = {
            "id": str(candidate.id),
            "name": candidate.name,
            "region_id": str(candidate.region_id) if candidate.region_id else None,
            "region_name": region_name,
            "distance_m": _rounded_distance(distance),
            "similarity": round(float(score), 3),
        }
        if candidate.normalized_name == normalized and same_region:
            exact.append(item)
        elif (same_region and score >= 0.82) or (
            distance is not None and distance <= 10_000 and score >= 0.72
        ):
            likely.append(item)
    return DuplicateResult(exact=exact, likely=likely)


def find_region_duplicates(
    db: Session,
    *,
    name: str,
    country: str | None,
    lat: float | None,
    lon: float | None,
    bounds=None,
    exclude_id: uuid.UUID | None = None,
) -> DuplicateResult:
    from app.models import Region

    normalized = normalize_name(name)
    country = country.upper() if country else None
    similarity = func.similarity(Region.normalized_name, normalized)
    stmt = (
        select(Region, similarity)
        .where(similarity >= 0.55)
        .order_by(similarity.desc())
        .limit(50)
    )
    if exclude_id is not None:
        stmt = stmt.where(Region.id != exclude_id)

    proposed_bounds = to_shape(bounds) if bounds is not None else None
    exact: list[dict[str, Any]] = []
    likely: list[dict[str, Any]] = []
    for candidate, score in db.execute(stmt).all():
        coords = _coordinates(candidate.center)
        distance = (
            _distance_m(lat, lon, *coords)
            if lat is not None and lon is not None and coords is not None
            else None
        )
        overlaps = bool(
            proposed_bounds is not None
            and candidate.bounds is not None
            and proposed_bounds.intersects(to_shape(candidate.bounds))
        )
        same_country = bool(country and candidate.country and candidate.country.upper() == country)
        item = {
            "id": str(candidate.id),
            "name": candidate.name,
            "country": candidate.country,
            "distance_m": _rounded_distance(distance),
            "similarity": round(float(score), 3),
            "bounds_overlap": overlaps,
        }
        # The existing global normalized-name constraint is intentionally
        # stricter than name+country and remains authoritative.
        if candidate.normalized_name == normalized:
            exact.append(item)
        elif (same_country and score >= 0.82) or (
            distance is not None and distance <= 150_000 and score >= 0.68
        ) or (overlaps and score >= 0.60):
            likely.append(item)
    return DuplicateResult(exact=exact, likely=likely)


def enforce_duplicates(
    entity: str,
    result: DuplicateResult,
    *,
    allow_likely: bool,
) -> list[dict[str, Any]]:
    if result.exact:
        raise ExactDuplicateError(entity, result.exact)
    if result.likely and not allow_likely:
        raise LikelyDuplicateError(entity, result.likely)
    return result.likely


def duplicate_detail(
    exc: ExactDuplicateError | LikelyDuplicateError, *, role: str
) -> dict[str, Any]:
    exact = isinstance(exc, ExactDuplicateError)
    return {
        "code": "exact_duplicate" if exact else "likely_duplicate",
        "entity": exc.entity.lower(),
        "message": str(exc),
        "candidates": exc.candidates,
        "override_allowed": not exact and role == "admin",
    }
