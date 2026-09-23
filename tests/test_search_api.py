"""API tests for /search, /search/geometry, /map, /portfolio with the geocoder +
scorer mocked via dependency overrides. DB-gated (skip when DB is down)."""

from __future__ import annotations

import pytest

from app.main import app
from app.search.deps import get_geocoder, get_scorer
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


@pytest.fixture
def mocked_search(client):
    app.dependency_overrides[get_geocoder] = lambda: FakeGeocoder()
    app.dependency_overrides[get_scorer] = lambda: FakeScorer({}, default=0.6)
    yield
    app.dependency_overrides.pop(get_geocoder, None)
    app.dependency_overrides.pop(get_scorer, None)


def test_search_endpoint_laboe(client, mocked_search):
    resp = client.get("/search", params={"q": "Laboe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved"] == "entities"
    assert "laboe" in {s["slug"] for s in body["spots"]}


def test_search_endpoint_sport_toggle(client, mocked_search):
    flat = client.get("/search", params={"q": "Laboe"}).json()
    wave = client.get("/search", params={"q": "Laboe", "sport": "surf"}).json()
    assert "laboe" in {s["slug"] for s in flat["spots"]}
    assert "laboe" not in {s["slug"] for s in wave["spots"]}


def test_map_endpoint(client, mocked_search):
    resp = client.get(
        "/map",
        params={"min_lon": 10.0, "min_lat": 54.2, "max_lon": 11.3, "max_lat": 54.6},
    )
    assert resp.status_code == 200
    pins = resp.json()["pins"]
    slugs = {p["slug"] for p in pins}
    assert {"laboe", "stein"}.issubset(slugs)
    assert all("color" not in p and "value" not in p for p in pins)


def test_geometry_endpoint_circle(client, mocked_search):
    resp = client.post(
        "/search/geometry",
        json={
            "type": "circle",
            "center_lat": 54.4097,
            "center_lon": 10.2206,
            "radius_km": 6,
        },
    )
    assert resp.status_code == 200
    assert "laboe" in {s["slug"] for s in resp.json()["spots"]}


def test_geometry_endpoint_rectangle_requires_bounds(client, mocked_search):
    resp = client.post("/search/geometry", json={"type": "rectangle"})
    assert resp.status_code == 422


def test_portfolio_endpoint(client, mocked_search):
    resp = client.get("/portfolio", params={"level": "region"})
    assert resp.status_code == 200
    maps = resp.json()["maps"]
    assert len(maps) >= 1
    assert any(m.get("pins") for m in maps)
