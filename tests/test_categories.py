"""Category axes + facilities: enum validation, GET /spots filters, readiness.

Pure-function tests run without a database; the API tests are DB-gated (skip when
the test database is unavailable, like the rest of the suite).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.admin.constants import (
    validate_facilities,
    validate_bottom_types,
    validate_level,
    validate_levels,
    validate_sports,
    validate_styles,
    synchronize_wavekite_style,
    validate_water_character,
    validate_water_characters,
    validate_water_types,
)
from app.admin.deps import get_cds_client
from app.main import app
from app.seed.seed import seed
from tests.era5_helpers import FakeCdsClient, make_synthetic_series


# --- pure enum validation --------------------------------------------------

def test_validate_level_accepts_known_na_none():
    assert validate_level("expert") == "expert"
    assert validate_level("n/a") == "n/a"
    assert validate_level(None) is None


def test_validate_level_rejects_unknown():
    with pytest.raises(ValueError):
        validate_level("intermediate")


def test_validate_water_character_rejects_unknown():
    assert validate_water_character("welle_gross") == "welle_gross"
    with pytest.raises(ValueError):
        validate_water_character("kabbel")


def test_validate_multi_axes_dedup_and_reject():
    # Multi-select level / water_character / water_type share the same rules.
    assert validate_levels(["beginner", "beginner", "expert"]) == ["beginner", "expert"]
    assert validate_levels(None) == []
    assert validate_levels(["n/a"]) == ["n/a"]
    with pytest.raises(ValueError):
        validate_levels(["intermediate"])
    with pytest.raises(ValueError):
        validate_levels("beginner")  # a bare string is not a list

    assert validate_water_characters(["chop", "flach"]) == ["chop", "flach"]
    with pytest.raises(ValueError):
        validate_water_characters(["kabbel"])

    assert validate_water_types(["sea", "lagoon"]) == ["sea", "lagoon"]
    with pytest.raises(ValueError):
        validate_water_types(["river"])

    assert validate_bottom_types(["sand", "reef", "sand"]) == ["sand", "reef"]
    with pytest.raises(ValueError):
        validate_bottom_types(["mixed", "sand"])
    with pytest.raises(ValueError):
        validate_bottom_types(["mud"])


def test_validate_styles_dedups_and_validates():
    assert validate_styles(["freeride", "freeride", "wave_riding", "wavekite"]) == [
        "freeride",
        "wave_riding",
        "wavekite",
    ]
    assert validate_styles(None) == []
    with pytest.raises(ValueError):
        validate_styles(["freeride", "nope"])
    with pytest.raises(ValueError):
        validate_styles("freeride")  # a bare string is not a list


def test_wavekite_is_derived_from_kitesurf_and_surf():
    sports, styles = synchronize_wavekite_style(
        ["kitesurf", "surf"], ["freeride"]
    )
    assert sports == ["kitesurf", "surf"]
    assert styles == ["freeride", "wavekite"]

    _, styles = synchronize_wavekite_style(["kitesurf"], ["wavekite", "freeride"])
    assert styles == ["freeride"]


def test_wavekite_is_not_a_sport():
    with pytest.raises(ValueError):
        validate_sports(["wavekite"])


def test_validate_facilities_shape_and_cleaning():
    out = validate_facilities(
        {"parking": {"available": True, "note": "  voll  "}, "shower": {"available": False}}
    )
    assert out == {
        "parking": {"available": True, "note": "voll"},
        "shower": {"available": False},
    }
    assert validate_facilities(None) is None
    assert validate_facilities({}) is None  # empty → None


def test_validate_facilities_rejects_bad_kind_and_missing_available():
    with pytest.raises(ValueError):
        validate_facilities({"pool": {"available": True}})
    with pytest.raises(ValueError):
        validate_facilities({"parking": {"note": "x"}})


# --- DB-gated API tests ----------------------------------------------------

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
def admin(client):
    app.dependency_overrides[get_cds_client] = lambda: FakeCdsClient(
        make_synthetic_series()
    )
    yield client
    app.dependency_overrides.pop(get_cds_client, None)


@pytest.fixture(autouse=True)
def _cleanup(db):
    """Spots first, before their region — see the identical teardown in
    test_admin_moderation for the reasoning."""
    from sqlalchemy import delete

    yield
    from app.models import Region, Spot

    regions = db.scalars(
        select(Region).where(Region.slug.like("cat-region-%"))
    ).all()
    if not regions:
        return
    ids = [region.id for region in regions]
    db.execute(delete(Spot).where(Spot.region_id.in_(ids)))
    db.execute(delete(Region).where(Region.id.in_(ids)))
    db.commit()


@pytest.fixture
def region_id(admin):
    suffix = uuid.uuid4().hex[:8]
    resp = admin.post("/admin/regions", json={
        "name": f"Cat Region {suffix}", "slug": f"cat-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _create(admin, region_id, publish=False, **overrides):
    body = {
        "name": f"Cat Spot {uuid.uuid4().hex[:8]}",
        "slug": f"cat-spot-{uuid.uuid4().hex[:8]}",
        "region_id": region_id, "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
    }
    body.update(overrides)
    resp = admin.post("/admin/spots", json=body)
    if publish and resp.status_code == 201:
        admin.post(f"/admin/spots/{resp.json()['id']}/live")
    return resp


def test_create_rejects_invalid_enum_422(admin, region_id):
    assert _create(admin, region_id, level=["intermediate"]).status_code == 422
    assert _create(admin, region_id, bottom_type=["mud"]).status_code == 422
    assert _create(admin, region_id, bottom_type=["mixed", "sand"]).status_code == 422
    assert _create(admin, region_id, water_character=["kabbel"]).status_code == 422
    assert _create(admin, region_id, water_type=["river"]).status_code == 422
    assert _create(admin, region_id, style=["loopy"]).status_code == 422


def test_create_stores_categories_and_facilities(admin, region_id):
    resp = _create(
        admin, region_id,
        level=["advanced", "expert"], water_character=["welle_gross"],
        water_type=["ocean", "sea"],
        bottom_type=["sand", "reef"],
        style=["freeride", "big_air"],
        facilities={"parking": {"available": True}, "camping": {"available": False}},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["level"] == ["advanced", "expert"]
    assert body["water_character"] == ["welle_gross"]
    assert body["water_type"] == ["ocean", "sea"]
    assert body["bottom_type"] == ["sand", "reef"]
    assert body["style"] == ["freeride", "big_air"]
    assert body["facilities"]["parking"] == {"available": True}


def test_get_spots_filters_by_category(admin, region_id):
    # These tests hit the *public* /spots list, which filters to published.
    # Since Sprint A spots start as draft, so publish here.
    _create(admin, region_id, publish=True, level=["advanced", "expert"],
            water_character=["welle_gross"], style=["wave_riding"],
            bottom_type=["sand", "reef"])
    _create(admin, region_id, publish=True, level=["beginner"], water_character=["flach"],
            style=["freeride"], bottom_type=["rock"])

    by_level = admin.get("/spots", params={"region_id": region_id, "level": "advanced"})
    assert by_level.status_code == 200
    assert all("advanced" in s["level"] for s in by_level.json())
    assert len(by_level.json()) == 1

    # The same multi-level spot is also reachable via its other level.
    by_level2 = admin.get(
        "/spots", params={"region_id": region_id, "level": "expert"}
    )
    assert len(by_level2.json()) == 1

    by_water = admin.get(
        "/spots", params={"region_id": region_id, "water_character": "flach"}
    )
    assert [s["water_character"] for s in by_water.json()] == [["flach"]]

    # style is a multi-value overlap filter
    by_style = admin.get(
        "/spots", params={"region_id": region_id, "style": ["wave_riding", "freestyle"]}
    )
    assert len(by_style.json()) == 1
    assert "wave_riding" in by_style.json()[0]["style"]

    by_bottom = admin.get(
        "/spots", params=[("region_id", region_id), ("bottom_type", "reef"), ("bottom_type", "rock")]
    )
    assert len(by_bottom.json()) == 2


def test_summary_carries_new_fields(admin, region_id):
    _create(admin, region_id, publish=True, water_character=["chop"], style=["freeride"])
    row = admin.get("/spots", params={"region_id": region_id}).json()[0]
    assert {"water_character", "style", "facilities"} <= set(row)


def test_readiness_requires_water_character_not_facilities(admin, region_id):
    # No water_character, no facilities → water_character is a gap; facilities is not.
    spot = _create(admin, region_id).json()
    gaps = set(admin.get(f"/admin/spots/{spot['id']}/readiness").json()["gaps"])
    assert "water_character" in gaps
    assert "facilities" not in gaps  # recommended, never required
    assert "style" not in gaps

    # Setting water_character clears that gap even with unknown facilities.
    admin.patch(f"/admin/spots/{spot['id']}", json={"water_character": ["chop"]})
    gaps2 = set(admin.get(f"/admin/spots/{spot['id']}/readiness").json()["gaps"])
    assert "water_character" not in gaps2


def test_patch_rejects_invalid_enum_422(admin, region_id):
    spot = _create(admin, region_id).json()
    resp = admin.patch(f"/admin/spots/{spot['id']}", json={"style": ["nope"]})
    assert resp.status_code == 422
