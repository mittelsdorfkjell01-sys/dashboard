"""Phase-D public surfaces, cache policy, and score-private profile variants."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.account.security import create_app_session_token, hash_password
from app.config import get_settings
from app.csrf import new_csrf_token
from app.live.cache import InMemoryCache
from app.live.deps import get_cache, get_om_client
from app.main import app
from app.models import (
    AppUser,
    GearItem,
    Region,
    RecommendationLog,
    RiderProfile,
    RiderSportProfile,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
    UserEvent,
)


def _forecast(*_args, **_kwargs):
    start = datetime(2026, 7, 1, 9, tzinfo=timezone.utc)
    return {
        "days": [
            {
                "date": (start + timedelta(days=day)).date().isoformat(),
                "local_date": (start + timedelta(days=day)).date().isoformat(),
                "confidence": 0.9,
                "hours": [
                    {
                        "time": (start + timedelta(days=day, hours=hour)).isoformat(),
                        "wind": 21,
                        "gust": 25,
                        "dir": 180,
                        "is_day": True,
                        "sst": 19,
                    }
                    for hour in range(4)
                ],
            }
            for day in range(10)
        ]
    }


def _account(db, style_weights: dict[str, int]) -> AppUser:
    user = AppUser(
        email=f"recommend-{uuid.uuid4().hex[:10]}@example.com",
        password_hash=hash_password("recommend-password"),
        display_name="Recommendation Rider",
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    profile = RiderProfile(app_user_id=user.id, weight_kg=78, travel_mode="trip")
    db.add(profile)
    db.flush()
    db.add(RiderSportProfile(
        rider_profile_id=profile.id,
        sport="kitesurf",
        level="advanced",
        style_weights=style_weights,
        preferred_water_character=[],
    ))
    db.add_all([
        GearItem(rider_profile_id=profile.id, sport="kitesurf", kind="kite", size=9, active=True),
        GearItem(rider_profile_id=profile.id, sport="kitesurf", kind="kite", size=12, active=True),
        GearItem(rider_profile_id=profile.id, sport="kitesurf", kind="board", board_type="twintip", active=True),
    ])
    db.commit()
    return user


def _client(user: AppUser | None = None) -> TestClient:
    client = TestClient(app)
    if user is not None:
        client.cookies.set(
            get_settings().app_auth_cookie_name,
            create_app_session_token(user.id),
        )
    return client


@pytest.fixture
def recommendation_catalog(db, monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"recommendation-{suffix}",
        name=f"Recommendation {suffix}",
        center=from_shape(Point(10.0, 54.0), srid=4326),
    )
    db.add(region)
    db.flush()
    spots = []
    for index, style in enumerate(("freeride", "big_air")):
        spot = Spot(
            slug=f"recommend-{style}-{suffix}",
            name=f"{index}-{style}",
            region_id=region.id,
            location=from_shape(Point(10.0 + index / 10, 54.0), srid=4326),
            sports=["kitesurf"],
            water_type=["sea"],
            bottom_type=["sand"],
            level=["advanced"],
            water_character=["flach"],
            style=[style],
            status="published",
            facing=180,
        )
        db.add(spot)
        db.flush()
        weather = SpotWeatherProfile(
            spot_id=spot.id,
            active=True,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(weather)
        db.flush()
        db.add(SpotWeatherSector(profile_id=weather.id, start_deg=120, end_deg=240, enabled=True))
        spots.append(spot)
    freeride_user = _account(db, {"freeride": 3, "big_air": 0})
    big_air_user = _account(db, {"freeride": 0, "big_air": 3})
    cache = InMemoryCache()
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_om_client] = lambda: object()
    monkeypatch.setattr("app.live.service.get_forecast_series", _forecast)
    yield region, spots, freeride_user, big_air_user
    app.dependency_overrides.pop(get_cache, None)
    app.dependency_overrides.pop(get_om_client, None)


def test_all_surfaces_and_cache_headers(recommendation_catalog):
    region, _spots, freeride_user, _big_air_user = recommendation_catalog
    anon = _client()
    calls = [
        {"surface": "now"},
        {"surface": "next_week"},
        {"surface": "season", "month": 7},
        {"surface": "region", "region_id": str(region.id)},
    ]
    for params in calls:
        response = anon.get("/recommendations", params=params)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"].startswith("public")
        assert "Cookie" not in response.headers.get("vary", "")
        assert "recommendations;dur=" in response.headers["server-timing"]
        assert all("score" not in item and "rating" not in item for item in response.json())

    signed = _client(freeride_user).get("/recommendations", params={"surface": "now"})
    assert signed.status_code == 200
    assert signed.headers["cache-control"] == "private, no-store"


def test_personalized_false_ranks_signed_in_visitor_as_anonymous(recommendation_catalog):
    _region, _spots, freeride_user, _big_air_user = recommendation_catalog
    params = {"surface": "now"}

    anonymous = _client().get("/recommendations", params=params)
    ignored = _client(freeride_user).get(
        "/recommendations", params={**params, "personalized": "false"}
    )
    personalized = _client(freeride_user).get("/recommendations", params=params)

    assert anonymous.status_code == ignored.status_code == personalized.status_code == 200
    # Ignoring personalization drops back to the shared, edge-cacheable variant.
    assert ignored.headers["cache-control"].startswith("public")
    assert "Cookie" not in ignored.headers.get("vary", "")
    assert personalized.headers["cache-control"] == "private, no-store"
    # ...and returns the exact anonymous ordering, not the rider's.
    assert [row["id"] for row in ignored.json()] == [row["id"] for row in anonymous.json()]


def test_profiles_change_only_selection_or_order(recommendation_catalog):
    region, _spots, freeride_user, big_air_user = recommendation_catalog
    params = {"surface": "region", "region_id": str(region.id)}
    first = _client(freeride_user).get("/recommendations", params=params)
    second = _client(big_air_user).get("/recommendations", params=params)
    assert first.status_code == second.status_code == 200
    first_rows, second_rows = first.json(), second.json()
    assert [row["name"] for row in first_rows] != [row["name"] for row in second_rows]
    assert {frozenset(row) for row in first_rows} == {frozenset(row) for row in second_rows}
    assert all("score" not in row and "reasons" not in row for row in first_rows + second_rows)


def test_region_list_keeps_server_order_and_top_route_contract(recommendation_catalog):
    region, _spots, freeride_user, big_air_user = recommendation_catalog
    query = {"region_id": str(region.id), "sport": "kitesurf"}
    freeride = _client(freeride_user).get("/spots", params=query)
    big_air = _client(big_air_user).get("/spots", params=query)
    assert freeride.status_code == big_air.status_code == 200
    assert [row["name"] for row in freeride.json()] != [row["name"] for row in big_air.json()]
    assert freeride.headers["cache-control"] == "private, no-store"

    top = _client(freeride_user).get("/spots/top", params={"sport": "kitesurf", "limit": 2})
    assert top.status_code == 200
    assert set(top.json()[0]) == set(freeride.json()[0])


def test_recommendation_query_validation():
    client = _client()
    assert client.get("/recommendations", params={"surface": "region"}).status_code == 422
    assert client.get("/recommendations", params={"surface": "now", "limit": 25}).status_code == 422
    assert client.get("/recommendations", params={"surface": "season", "month": 7, "weeks": "1-2"}).status_code == 422
    assert client.get("/recommendations", params={"lat": 54.0}).status_code == 422
    # A sport the surfaces do not serve is rejected; the served ones are not.
    assert client.get("/recommendations", params={"sport": "bogus"}).status_code == 422


@pytest.fixture
def windsurf_catalog(db, monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"windsurf-{suffix}",
        name=f"Windsurf {suffix}",
        center=from_shape(Point(10.0, 54.0), srid=4326),
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"windsurf-spot-{suffix}",
        name=f"Windsurf Spot {suffix}",
        region_id=region.id,
        location=from_shape(Point(10.0, 54.0), srid=4326),
        sports=["windsurf"],
        water_type=["sea"],
        bottom_type=["sand"],
        level=["advanced"],
        status="published",
        facing=180,
        editorial={"usable_wind_directions": [{"min": 120, "max": 240}]},
    )
    db.add(spot)
    db.commit()
    cache = InMemoryCache()
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_om_client] = lambda: object()
    monkeypatch.setattr("app.live.service.get_forecast_series", _forecast)
    yield region, spot
    app.dependency_overrides.pop(get_cache, None)
    app.dependency_overrides.pop(get_om_client, None)


def test_non_kite_and_aggregate_are_forecast_ranked(windsurf_catalog):
    _region, spot = windsurf_catalog
    client = _client()

    # The mocked forecast blows 21 kt from 180° — squarely in the windsurf band
    # and the spot's usable window, so the categorical engine rates it "gut".
    windsurf = client.get("/recommendations", params={"sport": "windsurf", "surface": "now"})
    assert windsurf.status_code == 200, windsurf.text
    assert windsurf.headers["cache-control"].startswith("public")
    assert [row["id"] for row in windsurf.json()] == [str(spot.id)]
    assert all("score" not in row and "rating" not in row for row in windsurf.json())

    # The "all" aggregate spans every sport and ranks the same windsurf spot in
    # via its best sport.
    aggregate = client.get("/recommendations", params={"sport": "all", "surface": "now"})
    assert aggregate.status_code == 200, aggregate.text
    assert str(spot.id) in [row["id"] for row in aggregate.json()]


def test_checkin_is_attributed_to_recent_recommendation(db, recommendation_catalog):
    _region, spots, user, _other = recommendation_catalog
    client = _client(user)
    csrf = new_csrf_token()
    client.cookies.set(get_settings().csrf_cookie_name, csrf)
    client.headers["X-CSRF-Token"] = csrf
    response = client.get("/recommendations", params={"surface": "now"})
    assert response.status_code == 200, response.text
    spot_id = response.json()[0]["id"]

    impression = client.post("/events", json={"events": [{
        "type": "impression", "spotId": spot_id, "surface": "now", "context": {},
    }]})
    assert impression.status_code == 202, impression.text
    checkin = client.post("/events", json={"events": [{
        "type": "session_checkin", "spotId": spot_id, "surface": "spot",
        "context": {"outcome": "worthwhile"},
    }]})
    assert checkin.status_code == 202, checkin.text

    db.expire_all()
    event = db.scalar(
        select(UserEvent)
        .where(UserEvent.app_user_id == user.id, UserEvent.type == "session_checkin")
        .order_by(UserEvent.created_at.desc())
    )
    assert event is not None
    assert event.recommendation_log_id is not None
    assert event.spot_id == uuid.UUID(spot_id)

    invalid = client.post("/events", json={"events": [{
        "type": "session_checkin", "spotId": str(spots[0].id),
        "context": {"outcome": "maybe"},
    }]})
    assert invalid.status_code == 422


def test_region_and_search_personal_scores_are_audited(db, recommendation_catalog):
    region, _spots, user, _other = recommendation_catalog
    client = _client(user)
    region_response = client.get("/spots", params={
        "region_id": str(region.id), "sport": "kitesurf",
    })
    search_response = client.get("/search", params={
        "q": region.name, "sport": "kitesurf",
    })
    assert region_response.status_code == search_response.status_code == 200
    db.expire_all()
    surfaces = set(db.scalars(select(RecommendationLog.surface).where(
        RecommendationLog.app_user_id == user.id,
        RecommendationLog.surface.in_(("region", "search")),
    )))
    assert surfaces == {"region", "search"}


def test_recommendations_api_local_p95_budget(recommendation_catalog):
    _region, _spots, user, _other = recommendation_catalog
    client = _client(user)
    durations_ms = []
    for _ in range(20):
        started = time.perf_counter()
        response = client.get("/recommendations", params={"surface": "now", "limit": 5})
        durations_ms.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200, response.text
    p95 = sorted(durations_ms)[math.ceil(len(durations_ms) * 0.95) - 1]
    print(f"recommendations_api_local_p95_ms={p95:.1f}")
    assert p95 < 750, f"local mocked-provider recommendations p95 was {p95:.1f} ms"
