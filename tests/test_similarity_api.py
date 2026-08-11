"""DB-gated tests for the similarity endpoints over seed spots. Skip w/o Postgres."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Spot
from app.seed.seed import seed


def _kite_clim(good_weeks: set[int], good_sector: int = 9) -> dict:
    weeks = []
    for w in range(1, 53):
        joint = [[0] * 6 for _ in range(16)]
        joint[good_sector][3 if w in good_weeks else 0] = 10
        weeks.append({"week": w, "daylight_hours": 10,
                      "wind": {"joint": joint, "p50_kt": 16,
                               "dir_dominant_deg": good_sector * 22.5}, "swell": {}})
    return {"window": "2006-2025", "weeks": weeks}


@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
        targets = {
            "laboe": set(range(20, 35)),
            "stein": set(range(20, 35)),
            "schilksee": set(range(20, 35)),
        }
        # This module asserts on the exact set of "running" alternatives, so it
        # must own the full climatology picture. Earlier modules (scoring/open-
        # axes) leave synthetic climatology on shared seed spots in the session
        # DB; clear every non-target spot so only our three have data.
        for spot in db.scalars(select(Spot)).all():
            spot.climatology = _kite_clim(targets[spot.slug]) if spot.slug in targets else None
        db.commit()
    finally:
        db.close()


@pytest.fixture
def laboe_id(db):
    return db.scalar(select(Spot.id).where(Spot.slug == "laboe"))


def test_similar_character_endpoint(client, laboe_id):
    resp = client.get(f"/spots/{laboe_id}/similar",
                      params={"mode": "charakter", "sport": "kitesurf"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "charakter"
    slugs = [s["slug"] for s in body["results"]]
    assert "laboe" not in slugs                       # target excluded
    # the other flatwater beginner spots are the closest in character
    assert slugs[0] in {"stein", "schilksee"}
    assert all(r["character"] is not None for r in body["results"])
    assert all("image" in r and "region" in r and "wind" in r for r in body["results"])


def test_similar_season_endpoint(client, laboe_id):
    resp = client.get(f"/spots/{laboe_id}/similar",
                      params={"mode": "saison", "sport": "kitesurf"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    # spots sharing Laboe's summer window correlate highly (low season distance)
    summer = {r["slug"]: r["season"] for r in results if r["slug"] in {"stein", "schilksee"}}
    assert summer and all(d < 0.2 for d in summer.values())


def test_similar_bad_mode_is_422(client, laboe_id):
    resp = client.get(f"/spots/{laboe_id}/similar", params={"mode": "nonsense"})
    assert resp.status_code == 422


def test_alternatives_endpoint_filters_running(client, laboe_id):
    # week 26 is inside the summer window -> flatwater neighbours run
    resp = client.get(f"/spots/{laboe_id}/alternatives",
                      params={"sport": "kitesurf", "week": 26})
    assert resp.status_code == 200
    running = {s["slug"] for s in resp.json()["alternatives"]}
    assert {"stein", "schilksee"} & running
    assert "laboe" not in running

    # week 45 is outside everyone's window -> nothing runs
    off = client.get(f"/spots/{laboe_id}/alternatives",
                     params={"sport": "kitesurf", "week": 45}).json()
    assert off["alternatives"] == []


def test_similar_404(client):
    import uuid

    resp = client.get(f"/spots/{uuid.uuid4()}/similar")
    assert resp.status_code == 404
