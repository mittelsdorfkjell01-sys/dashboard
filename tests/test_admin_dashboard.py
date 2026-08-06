"""Sprint B admin-dashboard endpoint tests: /admin/overview, /admin/spots,
/admin/regions. DB-gated; seeds the small core catalogue."""

from __future__ import annotations

import pytest

from app.seed.seed import seed


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


def test_overview_shape_and_counts(client):
    resp = client.get("/admin/overview")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(
        ["spots", "regions", "readiness_open", "not_live", "drafts", "recent", "review"]
    ).issubset(body)
    assert body["spots"]["total"] >= 1
    # total equals the sum of the per-status buckets
    assert body["spots"]["total"] == (
        body["spots"]["draft"] + body["spots"]["published"] + body["spots"]["archived"]
    )
    assert body["regions"] >= 1
    assert isinstance(body["recent"], list)
    assert isinstance(body["climatology_missing"], int)


def test_list_spots_paginates_with_total(client):
    resp = client.get("/admin/spots", params={"limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 2
    assert len(body["items"]) <= 2
    assert body["total"] >= len(body["items"])


def test_list_spots_status_filter(client):
    published = client.get("/admin/spots", params={"status": "published", "limit": 500}).json()
    assert all(s["status"] == "published" for s in published["items"])
    assert published["total"] == len(published["items"])


def test_list_spots_free_text_q(client):
    # 'laboe' is a seeded core spot.
    resp = client.get("/admin/spots", params={"q": "laboe"})
    assert resp.status_code == 200
    slugs = {s["slug"] for s in resp.json()["items"]}
    assert any("laboe" in s for s in slugs)


def test_regions_with_spot_counts(client):
    resp = client.get("/admin/regions")
    assert resp.status_code == 200
    regions = resp.json()
    assert regions
    for entry in regions:
        assert "region" in entry and "spot_counts" in entry
        counts = entry["spot_counts"]
        assert counts["total"] == counts["draft"] + counts["published"] + counts["archived"]


def test_incomplete_spot_is_saved_and_shows_as_open_points(db):
    """A spot uploaded with only the mandatory parts is saved as a draft and
    surfaces in both the 'Entwürfe' (drafts) and 'Offene Punkte' (not_live)
    columns with its missing fields listed."""
    from sqlalchemy import delete, select

    from app.admin import dashboard as dash
    from app.admin.spots import create_spot
    from app.models import Era5Job, Region, Spot

    region = db.scalar(select(Region))
    spot = create_spot(
        {
            "name": "ZZ Unvollständig Test",
            "region_id": region.id,
            "lat": 54.0,
            "lon": 10.0,
            "sports": ["kitesurf"],
        },
        db=db,
        actor="test",
    )
    try:
        assert spot.status == "draft"
        ov = dash.overview(db)

        draft = next((d for d in ov["drafts"] if d["id"] == str(spot.id)), None)
        assert draft is not None, "incomplete spot missing from drafts column"
        assert draft["ready"] is False
        assert draft["gaps"], "an incomplete spot must list open points"

        assert str(spot.id) in {s["id"] for s in ov["not_live"]}
    finally:
        db.execute(delete(Era5Job).where(Era5Job.spot_id == spot.id))
        db.execute(delete(Spot).where(Spot.id == spot.id))
        db.commit()


def test_dashboard_requires_auth(anon_client):
    assert anon_client.get("/admin/overview").status_code == 401


def test_curator_may_read_dashboard(curator_client):
    # curators keep read access to the operator surface (not user mgmt)
    assert curator_client.get("/admin/overview").status_code == 200
