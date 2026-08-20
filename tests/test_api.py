import pytest
from sqlalchemy import select

from app.seed.seed import seed
from app.admin.spots import _point
from app.models import Region, Spot


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


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # Granular per-dependency status. DB must be up (the suite needs it); Redis
    # may be up or down depending on the environment, but must be reported.
    assert body["db"] == "ok"
    assert body["schema"] == "ok"
    assert body["status"] in {"ok", "degraded"}
    assert body["redis"] in {"ok", "down"}


def test_list_spots_structure_and_coords(client):
    resp = client.get("/spots")
    assert resp.status_code == 200
    spots = resp.json()
    assert len(spots) >= 6

    los_lances = next(s for s in spots if s["slug"] == "tarifa-los-lances")
    for key in ("id", "name", "region_id", "location", "sports", "status"):
        assert key in los_lances

    loc = los_lances["location"]
    assert loc["lon"] == pytest.approx(-5.6280, abs=1e-4)
    assert loc["lat"] == pytest.approx(36.0250, abs=1e-4)
    assert "kitesurf" in los_lances["sports"]


def test_get_spot_by_id(client):
    spots = client.get("/spots").json()
    spot_id = spots[0]["id"]
    resp = client.get(f"/spots/{spot_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == spot_id


def test_get_spot_by_display_name_and_legacy_slug(client):
    by_name = client.get("/spots/Los-Lances")
    by_slug = client.get("/spots/tarifa-los-lances")
    assert by_name.status_code == by_slug.status_code == 200
    assert by_name.json()["id"] == by_slug.json()["id"]
    assert by_name.json()["region_name"] == "Tarifa"


def test_get_spot_by_display_name_when_punctuation_is_lost_in_url(client, db):
    region = db.scalar(select(Region).where(Region.slug == "tarifa"))
    spot = Spot(
        slug="naxos-agios-georgios-laguna",
        name="Agios Georgios / Laguna",
        region_id=region.id,
        location=_point(37.08, 25.37),
        sports=["windsurf"],
        status="published",
    )
    db.add(spot)
    db.commit()
    try:
        response = client.get("/spots/Agios-Georgios-Laguna")
        assert response.status_code == 200
        assert response.json()["id"] == str(spot.id)
    finally:
        db.delete(spot)
        db.commit()


def test_get_spot_404(client):
    resp = client.get("/spots/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_filter_spots_by_sport(client):
    resp = client.get("/spots", params={"sport": "wing"})
    assert resp.status_code == 200
    slugs = {s["slug"] for s in resp.json()}
    # Both seed spots that offer wing (poetto + the Baltic Fehmarn all-rounder).
    assert slugs == {"sardinia-poetto", "fehmarn-wulfener-hals"}


def test_list_regions(client):
    resp = client.get("/regions")
    assert resp.status_code == 200
    regions = resp.json()
    slugs = {r["slug"] for r in regions}
    assert {"tarifa", "sardinia"}.issubset(slugs)

    tarifa = next(r for r in regions if r["slug"] == "tarifa")
    assert tarifa["center"]["lon"] == pytest.approx(-5.6035, abs=1e-4)
    assert tarifa["bounds"]["rings"][0][0] == pytest.approx([-5.80, 35.95], abs=1e-4)


def test_get_region_by_id(client):
    regions = client.get("/regions").json()
    region_id = regions[0]["id"]
    resp = client.get(f"/regions/{region_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == region_id


def test_region_spot_count_and_sports_from_published_spots(client):
    # Tarifa's three seed spots are all published and, between them, cover
    # exactly kitesurf + windsurf.
    regions = client.get("/regions").json()
    tarifa = next(r for r in regions if r["slug"] == "tarifa")
    assert tarifa["spot_count"] == 3
    assert tarifa["sports"] == ["kitesurf", "windsurf"]

    by_id = client.get(f"/regions/{tarifa['id']}").json()
    assert by_id["spot_count"] == 3
    assert by_id["sports"] == ["kitesurf", "windsurf"]

    by_slug = client.get("/regions/by-slug/tarifa").json()
    assert by_slug["spot_count"] == 3
    assert by_slug["sports"] == ["kitesurf", "windsurf"]


def test_region_spot_count_excludes_unpublished_spots(client, db):
    region = db.scalar(select(Region).where(Region.slug == "tarifa"))
    draft = Spot(
        slug="tarifa-draft-count-test",
        name="Draft Count Test Spot",
        region_id=region.id,
        location=_point(36.0, -5.6),
        sports=["surf"],
        status="draft",
    )
    db.add(draft)
    db.commit()
    try:
        body = client.get(f"/regions/{region.id}").json()
        assert body["spot_count"] == 3
        assert "surf" not in body["sports"]
    finally:
        db.delete(draft)
        db.commit()
