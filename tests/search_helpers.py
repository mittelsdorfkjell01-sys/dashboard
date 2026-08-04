"""Test doubles for search: fake geocoder, fake scorer, in-memory spot/region."""

from __future__ import annotations

import uuid
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.models import Region, Spot
from app.search.geocode import GeocodeResult


def make_spot(
    name: str,
    lat: float,
    lon: float,
    sports: list[str],
    *,
    slug: str | None = None,
    aliases: list[str] | None = None,
    confidence: float | None = None,
    climatology: dict | None = None,
    water_type: str | None = None,
    bottom_type: str | None = None,
    level: str | None = None,
    facing: int | None = None,
    editorial: dict | None = None,
) -> Spot:
    if editorial is None and aliases:
        editorial = {"aliases": aliases}
    spot = Spot(
        slug=slug or name.lower().replace(" ", "-"),
        name=name,
        region_id=uuid.uuid4(),
        location=from_shape(Point(lon, lat), srid=4326),
        sports=sports,
        status="published",
        confidence=confidence,
        climatology=climatology,
        # water_type / level are multi-select array columns; callers still pass a
        # single scalar for brevity, so wrap into a one-element list.
        water_type=[water_type] if water_type else [],
        bottom_type=bottom_type,
        level=[level] if level else [],
        facing=facing,
        editorial=editorial,
    )
    spot.id = uuid.uuid4()
    return spot


def make_region(
    name: str,
    *,
    slug: str | None = None,
    country: str | None = None,
    center: tuple[float, float] | None = None,
    aliases: list[str] | None = None,
) -> Region:
    region = Region(
        slug=slug or name.lower().replace(" ", "-"),
        name=name,
        country=country,
        center=from_shape(Point(center[1], center[0]), srid=4326) if center else None,
        defaults={"aliases": aliases} if aliases else None,
    )
    region.id = uuid.uuid4()
    return region


class FakeGeocoder:
    """Returns canned :class:`GeocodeResult`s keyed by normalised query."""

    def __init__(self, results: dict[str, list[GeocodeResult]] | None = None) -> None:
        self._results = results or {}
        self.calls: list[str] = []

    def geocode(self, query: str) -> list[GeocodeResult]:
        self.calls.append(query)
        return self._results.get(query.strip().lower(), [])


class FakeScorer:
    """Deterministic scorer keyed by spot slug."""

    def __init__(self, scores: dict[str, float], default: float = 0.5) -> None:
        self._scores = scores
        self._default = default

    def score(self, spot: Any, time_context=None, profile=None) -> float:
        return self._scores.get(getattr(spot, "slug", None), self._default)
