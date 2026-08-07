"""Gallery management: order, remove, promote — and the media work list that
reads the same data. DB-gated, real spots and regions from the core seed.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.media import gallery as media_gallery
from app.media.image_object import build_image
from app.models import MediaUsage, Region, Spot, SpotImage
from tests.conftest import require_db


@pytest.fixture(scope="module", autouse=True)
def _catalogue(_migrated_db):
    from app.db.session import SessionLocal
    from app.seed.seed import seed

    require_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean(db):
    require_db()
    db.execute(delete(SpotImage))
    db.execute(delete(MediaUsage))
    db.commit()
    yield
    db.execute(delete(SpotImage))
    db.execute(delete(MediaUsage))
    db.commit()


def _blank_image(db, entity):
    """Clear the entity's seeded placeholder for one test, then restore it.

    The test database is shared across the whole session — an earlier version
    of this fixture left `image` at None after the test, which made an
    unrelated module's seed-regression assertions fail. See the identical fix
    in test_media_adopt.py.
    """
    original = entity.image
    entity.image = None
    db.commit()
    try:
        yield entity
    finally:
        entity.image = original
        db.commit()


@pytest.fixture
def spot(db):
    entity = db.scalars(select(Spot).where(Spot.slug == "tarifa-los-lances")).first()
    yield from _blank_image(db, entity)


@pytest.fixture
def region(db):
    entity = db.scalars(select(Region).where(Region.slug == "tarifa")).first()
    yield from _blank_image(db, entity)


def _gallery_row(db, entity, *, entity_type: str, credit="Jo", provider="unsplash", external_id=None):
    row = SpotImage(
        spot_id=entity.id if entity_type == "spot" else None,
        region_id=entity.id if entity_type == "region" else None,
        url=f"https://img/{uuid.uuid4().hex}.jpg",
        kind="gallery",
        width=2000,
        height=1200,
        source=provider,
        provider=provider,
        external_id=external_id,
        delivery="hotlinked",
        credit=credit,
        license_name="Unsplash License",
        status="approved",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# --- listing + ordering -----------------------------------------------------

def test_new_rows_sort_newest_first_until_arranged(db, spot):
    first = _gallery_row(db, spot, entity_type="spot")
    second = _gallery_row(db, spot, entity_type="spot")
    rows = media_gallery.list_gallery(db, "spot", spot.id)
    assert [r.id for r in rows] == [second.id, first.id]


def test_reorder_persists_and_unlisted_rows_keep_their_relative_place(db, spot):
    a = _gallery_row(db, spot, entity_type="spot")
    b = _gallery_row(db, spot, entity_type="spot")
    c = _gallery_row(db, spot, entity_type="spot")
    media_gallery.reorder(db, "spot", spot.id, [c.id, a.id])
    rows = media_gallery.list_gallery(db, "spot", spot.id)
    assert [r.id for r in rows] == [c.id, a.id, b.id]


def test_reorder_rejects_an_id_from_another_entity(db, spot, region):
    foreign = _gallery_row(db, region, entity_type="region")
    with pytest.raises(media_gallery.GalleryError):
        media_gallery.reorder(db, "spot", spot.id, [foreign.id])


def test_a_region_has_its_own_gallery(db, region):
    """Regions had no gallery at all before Sprint 1 generalised the table."""
    row = _gallery_row(db, region, entity_type="region")
    rows = media_gallery.list_gallery(db, "region", region.id)
    assert [r.id for r in rows] == [row.id]
    assert media_gallery.list_gallery(db, "spot", region.id) == []


# --- removal -----------------------------------------------------------------

def test_remove_marks_removed_rather_than_deleting(db, spot):
    """A community photo carries a consent record; the row must survive."""
    row = _gallery_row(db, spot, entity_type="spot")
    media_gallery.remove(db, row.id)
    db.refresh(row)
    assert row.status == "removed"
    assert row not in media_gallery.list_gallery(db, "spot", spot.id)


def test_remove_unknown_image_is_a_lookup_error(db):
    with pytest.raises(LookupError):
        media_gallery.remove(db, uuid.uuid4())


# --- promotion -----------------------------------------------------------------

def test_promoting_a_gallery_image_becomes_the_hero(db, spot):
    row = _gallery_row(db, spot, entity_type="spot", external_id="ext-1")
    media_gallery.promote_to_hero(db, row.id)
    db.refresh(spot)
    db.refresh(row)
    assert spot.image["url"] == row.url
    assert spot.image["credit"] == "Jo"
    assert row.status == "published_hero"


def test_promoting_demotes_the_previous_hero_into_the_gallery(db, spot):
    spot.image = build_image(
        url="https://img/old-hero.jpg", source="unsplash", license="Unsplash License",
        credit="Old Credit", provider="unsplash", external_id="old-1", delivery="hotlinked",
    )
    db.commit()
    row = _gallery_row(db, spot, entity_type="spot", external_id="new-1")

    media_gallery.promote_to_hero(db, row.id)
    db.refresh(spot)

    demoted = db.scalars(
        select(SpotImage).where(SpotImage.spot_id == spot.id, SpotImage.url == "https://img/old-hero.jpg")
    ).first()
    assert demoted is not None and demoted.kind == "gallery"
    assert spot.image["url"] == row.url


def test_promoting_without_a_credit_is_refused(db, spot):
    row = _gallery_row(db, spot, entity_type="spot", credit=None)
    with pytest.raises(media_gallery.GalleryError):
        media_gallery.promote_to_hero(db, row.id)


def test_promoting_records_media_usage(db, spot):
    row = _gallery_row(db, spot, entity_type="spot", provider="unsplash", external_id="usage-1")
    media_gallery.promote_to_hero(db, row.id)
    usage = db.scalars(
        select(MediaUsage).where(MediaUsage.external_id == "usage-1")
    ).first()
    assert usage is not None and usage.role == "hero"


# --- HTTP surface ------------------------------------------------------------

def test_gallery_endpoints_require_authentication(anon_client, spot):
    assert anon_client.get(f"/admin/media/gallery/spot/{spot.id}").status_code in (401, 403)


def test_gallery_crud_through_the_api(client, db, spot):
    row = _gallery_row(db, spot, entity_type="spot")

    listed = client.get(f"/admin/media/gallery/spot/{spot.id}")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == str(row.id)

    removed = client.delete(f"/admin/media/gallery/{row.id}")
    assert removed.status_code == 204
    assert client.get(f"/admin/media/gallery/spot/{spot.id}").json()["items"] == []


def test_promote_endpoint_updates_the_spot_record(client, db, spot):
    row = _gallery_row(db, spot, entity_type="spot")
    resp = client.post(f"/admin/media/gallery/{row.id}/promote")
    assert resp.status_code == 200, resp.text
    assert resp.json()["image"]["url"] == row.url


def test_reorder_endpoint(client, db, spot):
    a = _gallery_row(db, spot, entity_type="spot")
    b = _gallery_row(db, spot, entity_type="spot")
    resp = client.patch(
        "/admin/media/gallery/order",
        json={"entity_type": "spot", "entity_id": str(spot.id), "image_ids": [str(b.id), str(a.id)]},
    )
    assert resp.status_code == 200, resp.text
    assert [i["id"] for i in resp.json()["items"]] == [str(b.id), str(a.id)]


# --- work list -----------------------------------------------------------------

def test_worklist_flags_a_missing_hero(client, spot):
    resp = client.get("/admin/spots", params={"media": "no_hero", "limit": 500})
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(spot.id) in ids


def test_worklist_flags_an_unverified_hero_but_not_a_verified_one(db, client, spot):
    spot.image = build_image(
        url="https://img/x.jpg", source="unsplash", license="Unsplash License",
        credit="Jo", geo_verified=False,
    )
    db.commit()
    unverified = client.get(
        "/admin/spots", params={"media": "unverified", "limit": 500}
    ).json()
    assert str(spot.id) in {i["id"] for i in unverified["items"]}

    spot.image = {**spot.image, "geo_verified": True}
    db.commit()
    still_unverified = client.get(
        "/admin/spots", params={"media": "unverified", "limit": 500}
    ).json()
    assert str(spot.id) not in {i["id"] for i in still_unverified["items"]}


def test_worklist_flags_a_dead_source(db, client, spot):
    spot.image = build_image(
        url="https://img/x.jpg", source="unsplash", license="Unsplash License",
        credit="Jo", source_status="dead",
    )
    db.commit()
    resp = client.get("/admin/spots", params={"media": "dead", "limit": 500})
    assert str(spot.id) in {i["id"] for i in resp.json()["items"]}


def test_worklist_flags_a_duplicate_photo_used_on_two_spots(db, client):
    a, b = db.scalars(select(Spot).limit(2)).all()
    image = build_image(
        url="https://img/dup.jpg", source="unsplash", license="Unsplash License",
        credit="Jo", provider="unsplash", external_id="dup-1", delivery="hotlinked",
    )
    a.image, b.image = image, {**image}
    db.add_all([
        MediaUsage(provider="unsplash", external_id="dup-1", entity_type="spot", entity_id=a.id, role="hero"),
        MediaUsage(provider="unsplash", external_id="dup-1", entity_type="spot", entity_id=b.id, role="hero"),
    ])
    db.commit()

    resp = client.get("/admin/spots", params={"media": "duplicate", "limit": 500})
    ids = {i["id"] for i in resp.json()["items"]}
    assert {str(a.id), str(b.id)} <= ids


def test_placeholder_seed_image_counts_as_no_hero_not_unverified(client, spot):
    """A spot nobody has bebildert yet must appear once, under `no_hero` — not
    also under `unverified`, which would double-count it."""
    from app.media.image_object import placeholder_image
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(Spot, spot.id)
        row.image = placeholder_image(row.slug, kind="spot")
        db.commit()
    finally:
        db.close()

    no_hero = client.get("/admin/spots", params={"media": "no_hero", "limit": 500}).json()
    unverified = client.get(
        "/admin/spots", params={"media": "unverified", "limit": 500}
    ).json()
    assert str(spot.id) in {i["id"] for i in no_hero["items"]}
    assert str(spot.id) not in {i["id"] for i in unverified["items"]}


def test_region_worklist_endpoint(client, region):
    resp = client.get("/admin/media/worklist", params={"media": "no_hero"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "summary" in body
    assert any(r["id"] == str(region.id) for r in body["regions"])
    assert all(r["flags"]["no_hero"] for r in body["regions"])
