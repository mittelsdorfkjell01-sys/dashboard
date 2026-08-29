import pytest
from sqlalchemy import func, select

from app.media.image_object import CANONICAL_KEYS, is_placeholder, upgrade_legacy
from app.models import Region, Spot
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


def test_regions_seeded(db):
    slugs = set(db.scalars(select(Region.slug)).all())
    assert {"tarifa", "sardinia"}.issubset(slugs)


def test_spots_seeded(db):
    count = db.scalar(select(func.count()).select_from(Spot))
    assert count >= 6


def test_seed_is_idempotent(db):
    before = db.scalar(select(func.count()).select_from(Spot))
    created = seed(db)
    after = db.scalar(select(func.count()).select_from(Spot))
    assert created == {
        "regions": 0, "spots": 0, "scoring_params": 0, "required_fields": 0
    }
    assert before == after


def test_spot_linked_to_region(db):
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    assert spot is not None
    assert spot.region.slug == "tarifa"


# --- image regression ------------------------------------------------------
# The seed used to write `image` for regions and drop it for spots: the Spot(...)
# constructor had no image= at all, and the spot fixtures carried no such key.

def test_seeded_spot_has_its_image_in_the_database(db):
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    assert isinstance(spot.image, dict)
    assert spot.image["url"]


def test_every_seeded_spot_has_an_image(db):
    """Scoped to the seed's own slugs — the shared test database also holds
    spots that other modules created through the admin API, which legitimately
    have no image yet."""
    from app.seed.data import SPOTS as SEED_SPOTS

    slugs = [s["slug"] for s in SEED_SPOTS]
    missing = db.scalars(
        select(Spot.slug).where(Spot.slug.in_(slugs), Spot.image.is_(None))
    ).all()
    assert missing == []


def test_seeded_images_use_the_canonical_schema(db):
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    region = db.scalar(select(Region).where(Region.slug == "tarifa"))
    assert set(upgrade_legacy(spot.image)) == set(CANONICAL_KEYS)
    assert set(upgrade_legacy(region.image)) == set(CANONICAL_KEYS)
    assert "hero_reel" not in spot.image
    assert "delivery" not in region.image


def test_seeded_images_are_marked_as_placeholders(db):
    """They must not count towards readiness — otherwise the "Spots ohne Hero"
    work list reports images that nobody has actually chosen."""
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    assert is_placeholder(spot.image)
