"""Sport variants (Windfoil / Kitefoil): vocabulary, scoring honesty, filter.

Pure-function tests run without a database; the API/filter tests are DB-gated
(they publish spots and hit ``/map``), like the rest of the suite.
"""

from __future__ import annotations

import uuid

import pytest

from app.admin.constants import (
    offered_variants,
    validate_variant_conditions,
    variant_consistency_warnings,
    variant_suitability,
)
from app.scoring.context import scoring_sport, variant_editorial, variant_is_offered
from app.scoring.engine import SeasonalRuleScorer


# --- pure vocabulary / validation ------------------------------------------

def test_validate_variant_conditions_accepts_known_and_cleans():
    out = validate_variant_conditions(
        {
            "kitesurf:foil": {
                "suitability": "eingeschraenkt",
                "wind_directions": [[200, 260]],
                "usable_depth_m": 1.5,
                "notes": "  Foil ab Halbtide  ",
                "level": ["advanced", "advanced"],
            }
        }
    )
    block = out["kitesurf:foil"]
    assert block["suitability"] == "eingeschraenkt"
    assert block["wind_directions"] == [[200.0, 260.0]]
    assert block["usable_depth_m"] == 1.5
    assert block["notes"] == "Foil ab Halbtide"
    assert block["level"] == ["advanced"]


def test_validate_variant_conditions_rejects_unknown_key_and_suitability():
    with pytest.raises(ValueError):
        validate_variant_conditions({"surf:foil": {"suitability": "geeignet"}})
    with pytest.raises(ValueError):
        validate_variant_conditions({"windsurf:foil": {"suitability": "maybe"}})


def test_validate_variant_conditions_drops_empty_blocks():
    assert validate_variant_conditions({}) is None
    assert validate_variant_conditions({"windsurf:fin": {}}) is None
    assert validate_variant_conditions(None) is None


def test_variant_suitability_defaults_to_unbekannt():
    assert variant_suitability(None, "windsurf:foil") == "unbekannt"
    assert variant_suitability({"windsurf:foil": {}}, "windsurf:foil") == "unbekannt"
    assert (
        variant_suitability({"windsurf:foil": {"suitability": "geeignet"}}, "windsurf:foil")
        == "geeignet"
    )


def test_offered_variants_only_lists_geeignet_and_eingeschraenkt():
    conditions = {
        "windsurf:fin": {"suitability": "geeignet"},
        "windsurf:foil": {"suitability": "unbekannt"},
        "kitesurf:foil": {"suitability": "eingeschraenkt"},
    }
    assert offered_variants(conditions) == ["windsurf:fin", "kitesurf:foil"]


# --- consistency warnings --------------------------------------------------

def test_warns_when_foil_usable_on_flat_water_without_depth():
    warnings = variant_consistency_warnings(
        ["windsurf"],
        {"windsurf:foil": {"suitability": "geeignet"}},
        water_character=["flach"],
    )
    assert any("Flachwasser" in w for w in warnings)

    # A recorded usable depth resolves the contradiction.
    ok = variant_consistency_warnings(
        ["windsurf"],
        {"windsurf:foil": {"suitability": "geeignet", "usable_depth_m": 2.0}},
        water_character=["flach"],
    )
    assert not any("Flachwasser" in w for w in ok)


def test_warns_when_competition_level_on_unproven_variant():
    warnings = variant_consistency_warnings(
        ["kitesurf"],
        {"kitesurf:foil": {"suitability": "eingeschraenkt", "level": ["competition"]}},
    )
    assert any("Wettkampf" in w for w in warnings)


# --- scoring honesty (pure) ------------------------------------------------

class _Spot:
    def __init__(self, sports, variant_conditions=None, climatology=None):
        self.sports = sports
        self.variant_conditions = variant_conditions or {}
        self.climatology = climatology
        self.editorial = None
        self.facing = None
        self.confidence = 0.5


def test_scoring_sport_maps_base_variant_and_drops_foil():
    assert scoring_sport("windsurf:fin") == "windsurf"
    assert scoring_sport("kitesurf:classic") == "kitesurf"
    assert scoring_sport("windsurf:foil") is None
    assert scoring_sport("kitesurf:foil") is None
    assert scoring_sport("wing") == "wing"


def test_variant_is_offered_reflects_suitability():
    spot = _Spot(["windsurf"], {"windsurf:foil": {"suitability": "geeignet"}})
    assert variant_is_offered(spot, "windsurf:foil") is True
    assert variant_is_offered(spot, "windsurf:fin") is False  # unbekannt


def test_foil_variant_never_scores_positive_even_when_offered():
    # Offered foil variant, but no proven parameters → 0.0 ("nicht ausreichend
    # bewertet"), never a green forecast off invented thresholds.
    spot = _Spot(
        ["windsurf"],
        {"windsurf:foil": {"suitability": "geeignet", "wind_directions": [[200, 260]]}},
        climatology={"weeks": [{"week": 1, "wind": {"p50_kt": 22}}]},
    )
    scorer = SeasonalRuleScorer()
    assert scorer.score(spot, {"week": 1}, {"variant": "windsurf:foil"}) == 0.0


def test_unknown_variant_is_not_positive():
    spot = _Spot(
        ["windsurf"],
        {"windsurf:fin": {"suitability": "unbekannt"}},
        climatology={"weeks": [{"week": 1, "wind": {"p50_kt": 22}}]},
    )
    scorer = SeasonalRuleScorer()
    assert scorer.score(spot, {"week": 1}, {"variant": "windsurf:fin"}) == 0.0


def test_variant_editorial_overlays_variant_wind_window():
    spot = _Spot(
        ["kitesurf"],
        {"kitesurf:foil": {"wind_directions": [[200, 260]], "usable_depth_m": 1.5}},
    )
    ed = variant_editorial(spot, "kitesurf:foil")
    assert ed["usable_wind_directions"] == [[200, 260]]
    assert ed["usable_depth_m"] == 1.5


# --- DB-gated API + filter -------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        from app.seed.seed import seed

        seed(db)
    finally:
        db.close()


@pytest.fixture
def admin(client):
    from app.admin.deps import get_cds_client
    from app.main import app
    from tests.era5_helpers import FakeCdsClient, make_synthetic_series

    app.dependency_overrides[get_cds_client] = lambda: FakeCdsClient(
        make_synthetic_series()
    )
    yield client
    app.dependency_overrides.pop(get_cds_client, None)


@pytest.fixture(autouse=True)
def _cleanup(db):
    from sqlalchemy import delete, select

    yield
    from app.models import Region, Spot

    regions = db.scalars(select(Region).where(Region.slug.like("var-region-%"))).all()
    if not regions:
        return
    ids = [r.id for r in regions]
    db.execute(delete(Spot).where(Spot.region_id.in_(ids)))
    db.execute(delete(Region).where(Region.id.in_(ids)))
    db.commit()


@pytest.fixture
def region_id(admin):
    suffix = uuid.uuid4().hex[:8]
    resp = admin.post("/admin/regions", json={
        "name": f"Var Region {suffix}", "slug": f"var-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _create(admin, region_id, publish=False, **overrides):
    body = {
        "name": f"Var Spot {uuid.uuid4().hex[:8]}",
        "slug": f"var-spot-{uuid.uuid4().hex[:8]}",
        "region_id": region_id, "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
    }
    if publish:
        body.setdefault("bottom_type", ["sand"])
        body.setdefault("level", ["beginner"])
        body.setdefault("water_character", ["chop"])
        body.setdefault("water_type", ["sea"])
        body.setdefault("editorial", {"description": "Variant test spot."})
    body.update(overrides)
    resp = admin.post("/admin/spots", json=body)
    if publish and resp.status_code == 201:
        sid = resp.json()["id"]
        admin.post(f"/admin/spots/{sid}/image", json={
            "url": "https://images.example.com/hero.jpg", "source": "unsplash",
            "license": "Unsplash License", "credit": "Test",
        })
        live = admin.post(f"/admin/spots/{sid}/live")
        assert live.status_code == 200, live.text
    return resp


_BBOX = {"min_lon": 10.0, "min_lat": 54.0, "max_lon": 10.6, "max_lat": 54.8}


def test_create_stores_and_returns_variant_conditions(admin, region_id):
    resp = _create(
        admin, region_id, sports=["windsurf"],
        variant_conditions={
            "windsurf:fin": {"suitability": "geeignet"},
            "windsurf:foil": {"suitability": "ungeeignet"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["variant_conditions"]["windsurf:fin"]["suitability"] == "geeignet"
    # Offered = geeignet/eingeschraenkt only; the ungeeignet foil is excluded.
    assert body["variants"] == ["windsurf:fin"]


def test_deselecting_sport_prunes_its_variants(admin, region_id):
    spot = _create(
        admin, region_id, sports=["windsurf", "kitesurf"],
        variant_conditions={"windsurf:foil": {"suitability": "geeignet"}},
    ).json()
    patched = admin.patch(f"/admin/spots/{spot['id']}", json={"sports": ["kitesurf"]})
    assert patched.status_code == 200, patched.text
    # windsurf dropped → its variant block must be gone.
    assert not (patched.json().get("variant_conditions") or {})


def test_kitefoil_filter_excludes_classic_only_spot(admin, region_id):
    # A spot that only lists kitesurf (no Kitefoil suitability) …
    classic = _create(admin, region_id, publish=True).json()
    # … and one that actually offers Kitefoil.
    foil = _create(
        admin, region_id, publish=True,
        variant_conditions={
            "kitesurf:foil": {"suitability": "geeignet", "wind_directions": [[200, 260]]}
        },
    ).json()

    both = admin.get("/map", params={**_BBOX, "sport": "kitesurf"}).json()
    both_ids = {p["id"] for p in both["pins"]}
    assert {classic["id"], foil["id"]} <= both_ids

    only_foil = admin.get(
        "/map", params={**_BBOX, "variant": "kitesurf:foil"}
    ).json()
    foil_ids = {p["id"] for p in only_foil["pins"]}
    assert foil["id"] in foil_ids
    assert classic["id"] not in foil_ids  # kitesurf alone is NOT kitefoil


def test_migration_backfill_seeds_base_variant_not_foil(admin, region_id, db):
    """The 0063 backfill logic: an existing windsurf listing implies the Finne
    variant is geeignet, while Windfoil stays absent (=> unbekannt). Runs the
    migration's own UPDATE expression, scoped to a freshly inserted legacy-style
    row (no variant_conditions)."""
    from sqlalchemy import text

    spot = _create(admin, region_id, sports=["windsurf"]).json()
    assert spot.get("variant_conditions") in (None, {})  # legacy row: nothing yet

    db.execute(
        text(
            """
            UPDATE spots
            SET variant_conditions =
                COALESCE(NULLIF(variant_conditions, 'null'::jsonb), '{}'::jsonb)
                || jsonb_build_object(
                     'windsurf:fin', jsonb_build_object('suitability', 'geeignet')
                   )
            WHERE 'windsurf' = ANY(sports) AND id = :id
            """
        ),
        {"id": spot["id"]},
    )
    db.commit()

    row = admin.get(f"/admin/spots/{spot['id']}/record").json()
    assert row["variant_conditions"]["windsurf:fin"]["suitability"] == "geeignet"
    assert "windsurf:foil" not in row["variant_conditions"]  # never invented
    assert row["variants"] == ["windsurf:fin"]


def test_readiness_reports_variant_gaps_and_warnings(admin, region_id):
    spot = _create(
        admin, region_id, sports=["kitesurf"], water_character=["flach"],
        variant_conditions={"kitesurf:foil": {"suitability": "geeignet"}},
    ).json()
    readiness = admin.get(f"/admin/spots/{spot['id']}/readiness").json()
    fields = {i["field"] for i in readiness["checklist"]}
    assert "variant.kitesurf:foil.wind_directions" in fields
    assert "variant.kitesurf:foil.usable_depth_m" in fields
    # Flat-water place + usable foil + no depth → a consistency warning.
    assert any("Flachwasser" in w for w in readiness["warnings"])
    # …but none of it blocks (recommended only).
    assert "variant.kitesurf:foil.wind_directions" not in readiness["gaps"]
