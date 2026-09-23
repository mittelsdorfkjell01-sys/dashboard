"""Public JSON responses expose ordering, never internal scoring components."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.live.cache import InMemoryCache
from app.live.deps import get_cache, get_om_client
from app.main import app
from app.models import Region, Spot
from app.search.deps import get_geocoder, get_scorer
from app.seed.seed import seed
from tests.live_helpers import FakeOpenMeteoClient
from tests.search_helpers import FakeGeocoder, FakeScorer


FORBIDDEN_SCORE_KEYS = {
    "score",
    "rank_score",
    "rating",
    "reasons",
    "pct_usable",
    "gut_anteil",
    "good_weeks",
    "coverage",
    "intensity",
    "character",
}


def _forbidden_paths(value, *, allowed: set[str] | None = None, path: str = "$") -> list[str]:
    allowed = allowed or set()
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in FORBIDDEN_SCORE_KEYS and child not in allowed:
                found.append(child)
            found.extend(_forbidden_paths(item, allowed=allowed, path=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden_paths(item, allowed=allowed, path=f"{path}[{index}]"))
    return found


@pytest.fixture(scope="module")
def seeded_public_catalog(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@pytest.fixture
def public_contract_deps():
    app.dependency_overrides[get_geocoder] = lambda: FakeGeocoder()
    app.dependency_overrides[get_scorer] = lambda: FakeScorer({}, default=0.6)
    app.dependency_overrides[get_om_client] = lambda: FakeOpenMeteoClient()
    app.dependency_overrides[get_cache] = lambda: InMemoryCache()
    yield
    for dependency in (get_geocoder, get_scorer, get_om_client, get_cache):
        app.dependency_overrides.pop(dependency, None)


def test_public_serializer_helpers_hide_internal_scores():
    from app.search.service import _ranked_brief, _timewindow_brief
    from app.similarity.service import _alt_brief, _similar_brief
    from tests.search_helpers import make_spot

    spot = make_spot("Contract", 54.4, 10.2, ["kitesurf"])
    ranked = {
        "spot": spot,
        "distance_m": 1200.0,
        "score": 0.8,
        "rank_score": 0.7,
        "coverage": 0.6,
        "intensity": 0.5,
        "distance": 0.2,
        "character": 0.1,
        "season": 0.3,
    }
    for payload in (
        _ranked_brief(ranked),
        _timewindow_brief(ranked),
        _similar_brief(ranked),
        _alt_brief(ranked),
    ):
        assert _forbidden_paths(payload) == []


def test_private_account_rider_serializers_do_not_expose_personal_band():
    from app.account.rider import gear_payload, profile_payload, sport_profile_payload
    from app.models import GearItem, RiderProfile, RiderSportProfile
    import uuid

    profile = RiderProfile(weight_kg=78, travel_mode="day_trip", profile_version=3)
    sport = RiderSportProfile(
        sport="kitesurf", level="advanced", style_weights={"freeride": 2},
        preferred_water_character=["flach"],
    )
    gear = GearItem(
        id=uuid.uuid4(), sport="kitesurf", kind="kite", size=9,
        board_type=None, active=True, sort_order=0,
    )
    payloads = (
        profile_payload(profile),
        sport_profile_payload(sport, "kitesurf", 3),
        gear_payload(gear, 3),
    )
    for payload in payloads:
        assert _forbidden_paths(payload) == []
        assert "band" not in str(payload).lower()


def test_all_public_catalog_and_discovery_json_hides_scoring(
    seeded_public_catalog, anon_client, db, public_contract_deps
):
    spot = db.scalar(select(Spot).where(Spot.slug == "laboe"))
    region = db.get(Region, spot.region_id)
    bounds = {"min_lon": 10.0, "min_lat": 54.2, "max_lon": 11.3, "max_lat": 54.6}
    geometry = {
        "type": "circle",
        "center_lat": 54.4097,
        "center_lon": 10.2206,
        "radius_km": 6,
    }
    calls = [
        ("get", "/spots", {}),
        ("get", "/spots/version", {}),
        ("get", "/spots/top", {"params": {"sport": "kitesurf"}}),
        ("get", "/recommendations", {"params": {"surface": "now"}}),
        ("get", "/recommendations", {"params": {"surface": "next_week"}}),
        ("get", "/recommendations", {"params": {"surface": "season", "month": 7}}),
        ("get", "/recommendations", {"params": {"surface": "region", "region_id": str(region.id)}}),
        ("get", f"/spots/{spot.id}", {}),
        ("get", f"/spots/{spot.id}/tides", {}),
        ("get", f"/spots/{spot.id}/wind-climatology", {}),
        ("get", f"/spots/{spot.id}/live", {}),
        ("get", f"/spots/{spot.id}/forecast", {"params": {"days": 2}}),
        ("get", "/spots/live", {"params": {"ids": str(spot.id)}}),
        ("get", f"/spots/{spot.id}/similar", {"params": {"sport": "kitesurf"}}),
        ("get", f"/spots/{spot.id}/alternatives", {"params": {"sport": "kitesurf"}}),
        ("get", "/regions", {}),
        ("get", f"/regions/{region.id}", {}),
        ("get", f"/regions/by-slug/{region.slug}", {}),
        ("get", f"/regions/{region.id}/season", {"params": {"sport": "kitesurf"}}),
        ("get", "/search", {"params": {"q": "Laboe", "sport": "kitesurf"}}),
        ("post", "/search/geometry", {"json": geometry}),
        ("get", "/map", {"params": bounds}),
        ("get", "/portfolio", {"params": {"sport": "kitesurf"}}),
        ("get", "/search/best-spots", {"params": {"sport": "kitesurf"}}),
        ("get", "/search/best-regions", {"params": {"sport": "kitesurf"}}),
        ("get", "/areas/best-weeks", {"params": {"spot_id": str(spot.id), "sport": "kitesurf"}}),
        ("get", "/weather-fields/wind", {}),
        ("get", "/weather-fields/waves", {}),
        ("get", "/weather-fields/nearshore", {}),
        ("get", "/community/license", {}),
        ("get", f"/spots/{spot.id}/tips", {}),
        ("get", f"/spots/{spot.id}/images", {}),
    ]

    for method, url, kwargs in calls:
        response = getattr(anon_client, method)(url, **kwargs)
        assert response.status_code == 200, f"{method.upper()} {url}: {response.text}"
        assert _forbidden_paths(response.json()) == [], url

    # Public spot records must not expose the legacy confidence stage either.
    spot_payload = anon_client.get(f"/spots/{spot.id}").json()
    assert "confidence" not in spot_payload
    assert "confidence_override" not in (spot_payload.get("editorial") or {})


def test_community_rating_score_is_the_only_score_allowlist(
    seeded_public_catalog, anon_client, db, public_contract_deps
):
    spot_id = db.scalar(select(Spot.id).where(Spot.slug == "laboe"))
    response = anon_client.get(f"/spots/{spot_id}/ratings")
    assert response.status_code == 200
    body = response.json()
    assert _forbidden_paths(body, allowed={"$.aggregate.score"}) == []


def test_legacy_public_scoring_routes_do_not_exist(
    seeded_public_catalog, anon_client, db
):
    spot_id = db.scalar(select(Spot.id).where(Spot.slug == "laboe"))
    assert anon_client.get(f"/spots/{spot_id}/badge").status_code == 404
    assert anon_client.get(f"/spots/{spot_id}/season").status_code == 404
