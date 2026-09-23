"""Integration tests against seed spots (PostGIS). DB-gated: skip when DB is down.

Covers the Sprint 5 acceptance criteria: 'Laboe' returns nearby spots incl. Stein
score-ranked; an area input uses bounds (not a centre radius); drawn geometry;
and the sport toggle changing the result set.
"""

from __future__ import annotations

import pytest

from app.search import service
from app.search.geocode import GeocodeResult
from app.search.spatial import (
    bounds_query,
    search_by_geometry,
    search_nearby_spots,
)
from app.seed.seed import seed
from tests.search_helpers import FakeGeocoder, FakeScorer


@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


def _slugs(spots_rows):
    return {row[0].slug for row in spots_rows}


# --- 'Laboe' -> nearby incl. Stein, score-ranked ---------------------------

def test_search_laboe_returns_nearby_incl_stein(db):
    result = service.search(
        "Laboe",
        db=db,
        geocoder=FakeGeocoder(),
        scorer=FakeScorer({"stein": 0.9, "laboe": 0.1}),
    )
    assert result["resolved"] == "entities"
    slugs = [s["slug"] for s in result["spots"]]
    assert "laboe" in slugs
    assert "stein" in slugs        # the neighbouring spot is pulled in
    assert slugs.index("stein") < slugs.index("laboe")
    assert all("score" not in spot and "rank_score" not in spot for spot in result["spots"])


def test_search_nearby_adaptive_radius(db):
    point = {"lat": 54.4097, "lon": 10.2206}  # Laboe
    rows = search_nearby_spots(point, None, db=db)
    slugs = _slugs(rows)
    assert {"laboe", "stein", "schilksee"}.issubset(slugs)


# --- area input uses bounds, not a centre radius ---------------------------

def test_area_query_uses_bounds(db):
    # Sardinia bbox is tall (~270 km); a centre radius would miss the extremes.
    sardinia_bounds = {
        "min_lon": 8.1, "min_lat": 38.85, "max_lon": 9.7, "max_lat": 41.3
    }
    rows = bounds_query(sardinia_bounds, None, db=db)
    slugs = _slugs(rows)
    # both the far-north and the west-coast spots are inside the bounds
    assert {"sardinia-porto-pollo", "sardinia-capo-mannu"}.issubset(slugs)
    assert not any(s.startswith("tarifa-") for s in slugs)


def test_search_area_path_via_geocoder(db):
    # a non-entity query geocodes to an area -> bounds query
    geocoder = FakeGeocoder(
        {
            "mittelmeerinsel": [
                GeocodeResult(
                    "Sardinia", 39.2, 8.9, feature_code="ISL",
                    bbox=[8.1, 38.85, 9.7, 41.3],
                )
            ]
        }
    )
    result = service.search("Mittelmeerinsel", db=db, geocoder=geocoder)
    assert result["resolved"] == "area"
    slugs = {s["slug"] for s in result["spots"]}
    assert "sardinia-capo-mannu" in slugs


# --- drawn geometry --------------------------------------------------------

def test_geometry_circle(db):
    shape = {
        "type": "circle",
        "center": {"lat": 54.4097, "lon": 10.2206},
        "radius_km": 6,
    }
    slugs = _slugs(search_by_geometry(shape, None, db=db))
    assert "laboe" in slugs and "stein" in slugs
    assert "heidkate" not in slugs  # ~8 km, outside the 6 km circle


def test_geometry_rectangle(db):
    shape = {
        "type": "rectangle",
        "bounds": {"min_lon": 10.0, "min_lat": 54.2, "max_lon": 11.3, "max_lat": 54.6},
    }
    slugs = _slugs(search_by_geometry(shape, None, db=db))
    assert {"laboe", "stein", "fehmarn-wulfener-hals"}.issubset(slugs)
    assert not any(s.startswith("tarifa-") for s in slugs)


# --- sport toggle changes the result set -----------------------------------

def test_sport_toggle_drops_flatwater(db):
    ctx = {"kind": "search", "query": "Laboe"}
    all_res = service.toggle_sport(None, ctx, db=db, geocoder=FakeGeocoder())
    surf_res = service.toggle_sport("surf", ctx, db=db, geocoder=FakeGeocoder())

    all_slugs = {s["slug"] for s in all_res["spots"]}
    surf_slugs = {s["slug"] for s in surf_res["spots"]}

    assert "laboe" in all_slugs               # flatwater spot present unfiltered
    assert "laboe" not in surf_slugs          # ...and gone in wave mode
    assert "stein" in surf_slugs              # wave-capable spot remains
