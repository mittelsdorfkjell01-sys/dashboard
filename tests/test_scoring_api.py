"""DB-gated scoring params, climatology, and protected inspector tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.live.cache import InMemoryCache
from app.live.deps import get_cache, get_om_client
from app.main import app
from app.models import ScoringParams, Spot
from app.scoring import get_params, score_climatology_week, spot_confidence
from app.seed.seed import seed
from tests.live_helpers import FakeOpenMeteoClient


def _wind_week(cells: dict, week: int) -> dict:
    joint = [[0] * 6 for _ in range(16)]
    for (sector, mag), hours in cells.items():
        joint[sector][mag] = hours
    total = sum(cells.values())
    return {"week": week, "daylight_hours": total,
            "wind": {"joint": joint, "p50_kt": 16, "p10_kt": 10, "p90_kt": 24,
                     "dir_dominant_deg": 90, "dir_dominant": 4},
            "swell": {}, "air_p50_c": 15, "sst_p50_c": 16}


@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
        # give one spot a synthetic 52-week climatology to score
        spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
        spot.climatology = {
            "window": "2006-2025",
            "weeks": [_wind_week({(4, 3): 10, (4, 0): 5}, w) for w in range(1, 53)],
        }
        db.commit()
    finally:
        db.close()


@pytest.fixture
def spot_id(db):
    return db.scalar(select(Spot.id).where(Spot.slug == "tarifa-los-lances"))


@pytest.fixture
def mocked_live(client):
    app.dependency_overrides[get_om_client] = lambda: FakeOpenMeteoClient()
    app.dependency_overrides[get_cache] = lambda: InMemoryCache()
    yield
    app.dependency_overrides.pop(get_om_client, None)
    app.dependency_overrides.pop(get_cache, None)


# --- scoring_params seeding ------------------------------------------------

def test_scoring_params_seeded(db):
    rows = db.scalars(
        select(ScoringParams).where(ScoringParams.active.is_(True))
    ).all()
    sports = {r.sport for r in rows}
    assert {"kitesurf", "windsurf", "wing", "surf"}.issubset(sports)
    assert all(r.version == 3 for r in rows)
    versions = {
        (row.sport, row.version)
        for row in db.scalars(select(ScoringParams)).all()
    }
    assert all(
        (sport, version) in versions
        for sport in ("kitesurf", "windsurf", "wing", "surf")
        for version in (1, 2, 3)
    )
    kite = get_params("kitesurf", db)
    assert kite["d0_km"] == 40.0
    assert "kitesurf" in kite["rider_model"]
    assert "kitesurf" in kite["default_rider"]


# --- climatology scoring on a stored spot ----------------------------------

def test_score_climatology_week_on_seed_spot(db, spot_id):
    res = score_climatology_week(spot_id, 1, None, "kitesurf", db=db)
    # 10 good hours + 5 too-light hours -> 10/15 usable
    assert res["total_hours"] == 15
    assert res["usable_hours"] == 10
    assert res["pct_usable"] == round(10 / 15, 4)


def test_spot_confidence_on_seed_spot(db, spot_id):
    assert spot_confidence(spot_id, "kitesurf", db=db) == "hoch"
    assert spot_confidence(spot_id, "surf", db=db) == "mittel"  # wave lower


# --- endpoints -------------------------------------------------------------

def test_season_stage2_endpoint_is_admin_only(client, anon_client, spot_id, mocked_live):
    assert anon_client.get(f"/spots/{spot_id}/season").status_code == 404
    resp = client.get(
        f"/admin/scoring/spots/{spot_id}/season",
        params={"stage": 2, "sport": "kitesurf"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == 2
    assert len(body["curve"]) == 52
    assert body["scoring_params_version"] == 3


def test_season_stage1_endpoint(client, spot_id, mocked_live):
    resp = client.get(f"/admin/scoring/spots/{spot_id}/season", params={"stage": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == 1
    assert len(body["weeks"]) == 52
    assert "rating" not in body["weeks"][0]  # stage 1 is descriptive only


def test_badge_endpoint_is_admin_only(client, anon_client, spot_id, mocked_live):
    assert anon_client.get(f"/spots/{spot_id}/badge").status_code == 404
    resp = client.get(
        f"/admin/scoring/spots/{spot_id}/badge", params={"sport": "kitesurf"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sport"] == "kitesurf"
    assert body["rating"] in {"gut", "mäßig", "nein"}
    assert body["confidence"] in {"hoch", "mittel", "niedrig"}


def test_badge_404_for_unknown_spot(client, mocked_live):
    import uuid

    resp = client.get(f"/admin/scoring/spots/{uuid.uuid4()}/badge")
    assert resp.status_code == 404
