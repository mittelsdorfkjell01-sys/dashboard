"""Adoption: re-resolution, gates, delivery paths, duplicates, demotion.

DB-gated. Provider calls are replaced by fakes returning the frozen fixtures, so
the hotlinked and hosted paths are both exercised without network.
"""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import delete, select

from app.config import get_settings
from app.media import adopt as media_adopt
from app.media.providers import pexels, unsplash, wikimedia
from app.media.providers.base import ProviderError
from app.models import MediaProviderBudget, MediaUsage, Region, Spot, SpotImage
from tests.conftest import require_db

FIXTURES = Path(__file__).parent / "fixtures" / "media"

HERO_ID = "Qw3w0hVjJ2M"        # 6000×4000, passes the hero gate
SMALL_ID = "Kd8Lm2QpXyz"       # 2400×1600, gallery only
PEXELS_HERO_ID = "3560168"     # 5472×3648, hosted delivery


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def unsplash_photo(external_id: str) -> list[dict]:
    photo = next(
        p for p in fixture("unsplash_search.json")["results"] if p["id"] == external_id
    )
    return [{"results": [photo]}]


def pexels_photo(external_id: str) -> list[dict]:
    photo = next(
        p
        for p in fixture("pexels_search.json")["photos"]
        if str(p["id"]) == external_id
    )
    return [{"photos": [photo]}]


def jpeg_bytes(width: int = 4000, height: int = 2200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (20, 90, 140)).save(buffer, "JPEG")
    return buffer.getvalue()


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
def _isolate(db, monkeypatch, tmp_path):
    """Media state is global; storage goes to a tmp dir so the repo stays clean."""
    require_db()
    monkeypatch.setattr(get_settings(), "media_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(get_settings(), "unsplash_access_key", "test-key")
    monkeypatch.setattr(get_settings(), "pexels_api_key", "test-key")
    for model in (MediaUsage, MediaProviderBudget):
        db.execute(delete(model))
    db.execute(delete(SpotImage))
    db.commit()
    yield
    db.execute(delete(MediaUsage))
    db.execute(delete(SpotImage))
    db.commit()


def _blank_image(db, entity):
    """Clear the entity's seeded placeholder for the duration of one test, then
    put it back.

    The test database is shared across the whole session, so leaving a spot
    without its seed image silently breaks the seed assertions in a later
    module — the kind of failure that looks like a regression somewhere else
    entirely.
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
def other_spot(db):
    entity = db.scalars(select(Spot).where(Spot.slug == "tarifa-valdevaqueros")).first()
    yield from _blank_image(db, entity)


@pytest.fixture
def region(db):
    entity = db.scalars(select(Region).where(Region.slug == "tarifa")).first()
    yield from _blank_image(db, entity)


@pytest.fixture
def unsplash_fetch(monkeypatch):
    calls: list[str] = []

    def fake_fetch(external_id):
        calls.append(external_id)
        return unsplash_photo(external_id)

    monkeypatch.setattr(unsplash.ADAPTER, "fetch", fake_fetch)
    monkeypatch.setattr(unsplash.ADAPTER, "ping_download", lambda location: None)
    return calls


# --- happy path: hotlinked -------------------------------------------------

def test_adopting_an_unsplash_hero_hotlinks_and_records_provenance(
    db, spot, unsplash_fetch
):
    outcome = media_adopt.adopt(
        db,
        entity_type="spot",
        entity_id=spot.id,
        role="hero",
        provider="unsplash",
        external_id=HERO_ID,
    )
    db.refresh(spot)

    assert outcome.image["delivery"] == "hotlinked"
    assert spot.image["url"].startswith("https://images.unsplash.com/")
    assert spot.image["provider"] == "unsplash"
    assert spot.image["external_id"] == HERO_ID
    assert spot.image["credit"] == "Sam Rivera"
    assert "utm_source=surfwinddata" in spot.image["credit_url"]
    assert spot.image["license"] == "Unsplash License"
    assert spot.image["retrieved_at"]


def test_the_client_payload_is_never_trusted(db, spot, unsplash_fetch):
    """Only an identity is accepted; everything else comes from the provider."""
    media_adopt.adopt(
        db,
        entity_type="spot",
        entity_id=spot.id,
        role="hero",
        provider="unsplash",
        external_id=HERO_ID,
    )
    assert unsplash_fetch == [HERO_ID]  # re-resolved, not taken from the request


def test_unsplash_download_location_is_pinged_once_on_adopt(db, spot, monkeypatch):
    """An API condition — skipping it costs production access."""
    pings: list[str] = []
    monkeypatch.setattr(unsplash.ADAPTER, "fetch", lambda i: unsplash_photo(i))
    monkeypatch.setattr(unsplash.ADAPTER, "ping_download", lambda loc: pings.append(loc))

    media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    assert len(pings) == 1
    assert pings[0].startswith("https://api.unsplash.com/")


def test_a_failed_ping_does_not_undo_a_valid_adoption(db, spot, monkeypatch):
    monkeypatch.setattr(unsplash.ADAPTER, "fetch", lambda i: unsplash_photo(i))
    monkeypatch.setattr(
        unsplash.ADAPTER,
        "ping_download",
        lambda loc: (_ for _ in ()).throw(ProviderError("ping failed")),
    )
    media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    db.refresh(spot)
    assert spot.image["url"]


# --- happy path: hosted ----------------------------------------------------

def test_adopting_a_pexels_hero_copies_the_file_into_our_storage(
    db, spot, monkeypatch
):
    monkeypatch.setattr(pexels.ADAPTER, "fetch", lambda i: pexels_photo(i))
    monkeypatch.setattr(
        "app.media.providers.base.download_bytes", lambda url: jpeg_bytes()
    )

    outcome = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="pexels", external_id=PEXELS_HERO_ID,
    )
    db.refresh(spot)

    assert outcome.image["delivery"] == "hosted"
    assert not spot.image["url"].startswith("https://images.pexels.com/")
    assert spot.image["credit"] == "Marta Kowalska"
    # Dimensions describe the stored derivative, which is what the crop uses.
    assert spot.image["width"] and spot.image["height"]


# --- gates -----------------------------------------------------------------

def test_a_too_small_photo_is_adopted_for_hero_with_a_warning(db, spot, unsplash_fetch):
    # Size is a soft gate: the operator sees the resolution and can knowingly
    # use a smaller image — only the licence gate hard-rejects adoption.
    outcome = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=SMALL_ID,
    )
    assert any("3840" in w for w in outcome.warnings)


def test_the_same_photo_is_accepted_for_the_gallery(db, spot, unsplash_fetch):
    outcome = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="gallery",
        provider="unsplash", external_id=SMALL_ID,
    )
    assert outcome.gallery_image_id is not None
    row = db.get(SpotImage, outcome.gallery_image_id)
    assert row.spot_id == spot.id and row.kind == "gallery"
    assert row.provider == "unsplash" and row.delivery == "hotlinked"


def test_a_noncommercial_license_is_refused(db, spot, monkeypatch):
    raw = [fixture("wikimedia_search.json")]
    monkeypatch.setattr(wikimedia.ADAPTER, "fetch", lambda i: raw)
    # parse() keeps the NC file, so the license gate is what must stop it.
    monkeypatch.setattr(
        wikimedia.ADAPTER,
        "parse",
        lambda r, **kw: [
            p
            for p in wikimedia.WikimediaAdapter.parse(wikimedia.ADAPTER, r, **kw)
            if p.external_id == "45219877"
        ],
    )
    with pytest.raises(media_adopt.AdoptError, match="Lizenz"):
        media_adopt.adopt(
            db, entity_type="spot", entity_id=spot.id, role="hero",
            provider="wikimedia", external_id="45219877",
        )


def test_a_photo_that_vanished_upstream_is_reported_clearly(db, spot, monkeypatch):
    monkeypatch.setattr(unsplash.ADAPTER, "fetch", lambda i: [{"results": []}])
    with pytest.raises(media_adopt.AdoptError, match="nicht mehr verfügbar"):
        media_adopt.adopt(
            db, entity_type="spot", entity_id=spot.id, role="hero",
            provider="unsplash", external_id=HERO_ID,
        )


# --- duplicates ------------------------------------------------------------

def test_a_photo_already_used_elsewhere_cannot_become_a_hero(
    db, spot, other_spot, unsplash_fetch
):
    media_adopt.adopt(
        db, entity_type="spot", entity_id=other_spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    with pytest.raises(media_adopt.DuplicateHeroError) as exc:
        media_adopt.adopt(
            db, entity_type="spot", entity_id=spot.id, role="hero",
            provider="unsplash", external_id=HERO_ID,
        )
    assert other_spot.name in str(exc.value)
    assert exc.value.usages[0]["entity_id"] == str(other_spot.id)


def test_a_duplicate_gallery_image_only_warns(db, spot, other_spot, unsplash_fetch):
    media_adopt.adopt(
        db, entity_type="spot", entity_id=other_spot.id, role="gallery",
        provider="unsplash", external_id=SMALL_ID,
    )
    outcome = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="gallery",
        provider="unsplash", external_id=SMALL_ID,
    )
    assert outcome.gallery_image_id is not None
    assert any(other_spot.name in warning for warning in outcome.warnings)


def test_re_adopting_the_same_photo_on_the_same_entity_is_allowed(
    db, spot, unsplash_fetch
):
    """Only *other* entities count as duplicates — re-cropping your own hero
    must not be refused."""
    media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    again = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID, focal={"x": 30, "y": 70},
    )
    assert again.image["focal"] == {"x": 30.0, "y": 70.0}


# --- hero replacement ------------------------------------------------------

def test_the_previous_hero_moves_to_the_gallery(db, spot, unsplash_fetch, monkeypatch):
    media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    first_url = spot.image["url"]

    monkeypatch.setattr(pexels.ADAPTER, "fetch", lambda i: pexels_photo(i))
    monkeypatch.setattr(
        "app.media.providers.base.download_bytes", lambda url: jpeg_bytes()
    )
    outcome = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="pexels", external_id=PEXELS_HERO_ID,
    )
    db.refresh(spot)

    assert outcome.demoted_hero is True
    assert spot.image["provider"] == "pexels"
    demoted = db.scalars(
        select(SpotImage).where(SpotImage.spot_id == spot.id, SpotImage.url == first_url)
    ).first()
    assert demoted is not None and demoted.kind == "gallery"

    usage = db.scalars(
        select(MediaUsage).where(MediaUsage.external_id == HERO_ID)
    ).first()
    assert usage.role == "gallery"  # the old hero's usage follows it


# --- geo -------------------------------------------------------------------

def test_unverified_location_warns_but_never_blocks(db, spot, unsplash_fetch):
    outcome = media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    assert outcome.image is not None
    assert "Ortsbezug ungeprüft." in outcome.warnings


# --- regions use the identical path ----------------------------------------

def test_regions_adopt_through_the_same_code_path(db, region, unsplash_fetch):
    outcome = media_adopt.adopt(
        db, entity_type="region", entity_id=region.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    db.refresh(region)
    assert region.image["provider"] == "unsplash"
    assert outcome.entity_type == "region"


def test_a_region_gallery_row_is_stored_against_the_region(db, region, unsplash_fetch):
    """Regions had no gallery at all before Sprint 1 generalised the table."""
    outcome = media_adopt.adopt(
        db, entity_type="region", entity_id=region.id, role="gallery",
        provider="unsplash", external_id=SMALL_ID,
    )
    row = db.get(SpotImage, outcome.gallery_image_id)
    assert row.region_id == region.id and row.spot_id is None


# --- source health ---------------------------------------------------------

def test_verify_sources_marks_dead_and_living_urls(db, spot, unsplash_fetch, monkeypatch):
    media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    monkeypatch.setattr("app.media.adopt.head_status", lambda url: 404)
    report = media_adopt.verify_sources(db, limit=500)
    db.refresh(spot)

    assert spot.image["source_status"] == "dead"
    assert spot.image["source_checked_at"]
    assert any(item["entity_id"] == str(spot.id) for item in report["dead"])


def test_verify_sources_treats_an_unreachable_host_as_dead(db, spot, unsplash_fetch, monkeypatch):
    media_adopt.adopt(
        db, entity_type="spot", entity_id=spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    monkeypatch.setattr("app.media.adopt.head_status", lambda url: None)
    media_adopt.verify_sources(db, limit=500)
    db.refresh(spot)
    assert spot.image["source_status"] == "dead"


# --- HTTP surface ----------------------------------------------------------

def test_adopt_requires_authentication(anon_client, spot):
    resp = anon_client.post(
        "/admin/media/adopt",
        json={
            "entity_type": "spot",
            "entity_id": str(spot.id),
            "role": "hero",
            "provider": "unsplash",
            "external_id": HERO_ID,
        },
    )
    assert resp.status_code in (401, 403)


def test_adopt_endpoint_returns_the_written_image(client, db, spot, unsplash_fetch):
    resp = client.post(
        "/admin/media/adopt",
        json={
            "entity_type": "spot",
            "entity_id": str(spot.id),
            "role": "hero",
            "provider": "unsplash",
            "external_id": HERO_ID,
            "focal": {"x": 40, "y": 55},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["image"]["focal"] == {"x": 40.0, "y": 55.0}
    assert body["image"]["provider"] == "unsplash"


def test_duplicate_hero_is_a_409_so_the_client_can_tell_it_apart(
    client, db, spot, other_spot, unsplash_fetch
):
    media_adopt.adopt(
        db, entity_type="spot", entity_id=other_spot.id, role="hero",
        provider="unsplash", external_id=HERO_ID,
    )
    resp = client.post(
        "/admin/media/adopt",
        json={
            "entity_type": "spot",
            "entity_id": str(spot.id),
            "role": "hero",
            "provider": "unsplash",
            "external_id": HERO_ID,
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["code"] == "duplicate_hero"


def test_adopt_404s_for_an_unknown_entity(client, unsplash_fetch):
    resp = client.post(
        "/admin/media/adopt",
        json={
            "entity_type": "spot",
            "entity_id": str(uuid.uuid4()),
            "role": "hero",
            "provider": "unsplash",
            "external_id": HERO_ID,
        },
    )
    assert resp.status_code == 404
