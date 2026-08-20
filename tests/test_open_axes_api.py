"""DB-gated tests for Sprint 6: region aggregate over seed spots + the open-axes
endpoints. Skip when the test database is unavailable."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Region, Spot
from app.scoring.region import aggregate_region_season
from app.seed.seed import seed


def _week(week: int, kind: str, *, wind_p50=18.0, sst=20.0, air=17.0) -> dict:
    joint = [[0] * 6 for _ in range(16)]
    if kind == "full":
        joint[4][3] = 10
    else:
        joint[4][0] = 10
    return {
        "week": week, "daylight_hours": 10,
        "wind": {"joint": joint, "p50_kt": wind_p50, "dir_dominant_deg": 90},
        "swell": {}, "air_p50_c": air, "sst_p50_c": sst,
    }


def _clim(good_weeks: set[int]) -> dict:
    return {"window": "2006-2025",
            "weeks": [_week(w, "full" if w in good_weeks else "off") for w in range(1, 53)]}


@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
        # Give Sardinian spots distinct seasonal windows.
        windows = {
            "sardinia-porto-pollo": set(range(23, 31)),  # summer
            "sardinia-poetto": set(range(25, 33)),        # late summer
            "sardinia-capo-mannu": set(range(1, 9)),      # winter
        }
        for slug, weeks in windows.items():
            spot = db.scalar(select(Spot).where(Spot.slug == slug))
            spot.climatology = _clim(weeks)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def sardinia_id(db):
    return db.scalar(select(Region.id).where(Region.slug == "sardinia"))


# --- region aggregate ------------------------------------------------------

def test_aggregate_region_season_counts_working_spots(db, sardinia_id):
    season = aggregate_region_season(sardinia_id, db=db, sport="kitesurf")
    weeks = {w["week"]: w for w in season["weeks"]}
    # week 26 (June): both summer spots run -> spots_working >= 2
    assert weeks[26]["spots_working"] >= 2
    # a winter week: at most the surf spot's window, summer spots off
    assert weeks[40]["spots_working"] == 0
    assert weeks[26]["wind_p50"] is not None


def test_region_season_endpoint(client, sardinia_id):
    """GET /regions/{id}/season is a deliberate stub: the legacy per-spot-
    climatology-based aggregate() tested above (test_aggregate_region_season_
    counts_working_spots) is still correct, but it is not wired into any
    public endpoint — a region-level V2 aggregation needs product approval
    first (see the "deliberately unknown" comment on RegionRead in
    app/schemas/region.py). Serving the old V1 aggregate here would quietly
    reintroduce the system that decision moved away from."""
    resp = client.get(f"/regions/{sardinia_id}/season", params={"sport": "kitesurf"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"region_id": str(sardinia_id), "status": "unknown", "season": None}


# --- open-axes endpoints ---------------------------------------------------

def test_best_spots_in_region_summer(client, sardinia_id):
    resp = client.get(
        "/search/best-spots",
        params={"region_id": str(sardinia_id), "sport": "kitesurf", "month": 7},
    )
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()["spots"]]
    # the summer spots cover July; capo-mannu (winter) should trail
    assert "sardinia-porto-pollo" in slugs[:2]
    assert resp.json()["spots"][0]["coverage"] >= resp.json()["spots"][-1]["coverage"]


def test_best_spots_open_place_ranks_catalogue(client):
    resp = client.get("/search/best-spots", params={"sport": "kitesurf", "month": 7})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "europe"
    assert any(s["slug"] == "sardinia-porto-pollo" for s in body["spots"])


def test_best_regions_for_window(client):
    resp = client.get("/search/best-regions", params={"sport": "kitesurf", "month": 7})
    assert resp.status_code == 200
    regions = resp.json()["regions"]
    assert any(r["slug"] == "sardinia" for r in regions)
    # ranked by coverage descending
    covs = [r["coverage"] for r in regions]
    assert covs == sorted(covs, reverse=True)


def test_areas_best_weeks_open_time(client, sardinia_id):
    resp = client.get(
        "/areas/best-weeks",
        params={"region_id": str(sardinia_id), "sport": "kitesurf", "top": 5},
    )
    assert resp.status_code == 200
    weeks = resp.json()["weeks"]
    assert len(weeks) == 5
    # best weeks for Sardinia are in its good windows (summer or winter), score 1.0
    assert weeks[0]["score"] == 1.0
