"""API + service tests for the featured "aktuelle Top Spots" ranking.

Open-Meteo and the cache are mocked via FastAPI dependency overrides / injected
doubles. DB-gated (skips when the test DB is down)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.discovery import service as discovery
from app.live.cache import InMemoryCache
from app.live.deps import get_cache, get_om_client
from app.main import app
from app.models import Spot
from app.seed.seed import seed
from tests.live_helpers import FakeOpenMeteoClient


@pytest.fixture
def seeded(db):
    seed(db)
    return db


@pytest.fixture
def fake_live(client):
    fake = FakeOpenMeteoClient()
    cache = InMemoryCache()
    app.dependency_overrides[get_om_client] = lambda: fake
    app.dependency_overrides[get_cache] = lambda: cache
    yield fake
    app.dependency_overrides.pop(get_om_client, None)
    app.dependency_overrides.pop(get_cache, None)


# --- endpoint --------------------------------------------------------------

def test_top_endpoint_returns_published_spots(client, seeded, fake_live):
    resp = client.get("/spots/top?limit=5")
    assert resp.status_code == 200
    assert "s-maxage=21600" in resp.headers["cache-control"]
    assert "stale-while-revalidate=86400" in resp.headers["cache-control"]
    body = resp.json()
    assert isinstance(body, list)          # path wins over /spots/{spot_id}
    assert 0 < len(body) <= 5
    assert all(item["status"] == "published" for item in body)
    # No duplicates in the ranking.
    assert len({item["id"] for item in body}) == len(body)


def test_top_endpoint_respects_limit(client, seeded, fake_live):
    resp = client.get("/spots/top?limit=3")
    assert resp.status_code == 200
    assert len(resp.json()) <= 3


def test_top_endpoint_rejects_over_cap(client, seeded, fake_live):
    resp = client.get("/spots/top?limit=99")
    assert resp.status_code == 422


def test_top_endpoint_precedes_uuid_route(client, seeded, fake_live):
    # "top" must not be parsed as a spot id.
    resp = client.get("/spots/top")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# --- service determinism / caching -----------------------------------------

def _published_ids(db) -> set:
    return set(db.scalars(select(Spot.id).where(Spot.status == "published")))


def test_service_returns_valid_published_subset(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    ids = discovery.top_spot_ids(
        seeded, limit=5, client=fake, cache=cache, today=date(2026, 7, 18)
    )
    assert 0 < len(ids) <= 5
    assert set(ids) <= _published_ids(seeded)
    assert len(set(ids)) == len(ids)


def test_service_is_stable_within_a_day(seeded):
    fake = FakeOpenMeteoClient()
    day = date(2026, 7, 18)
    # Fresh cache each call, same day -> deterministic identical ordering.
    a = discovery.top_spot_ids(seeded, client=fake, cache=InMemoryCache(), today=day)
    b = discovery.top_spot_ids(seeded, client=fake, cache=InMemoryCache(), today=day)
    assert a == b


def test_service_uses_cache_on_second_call(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)
    discovery.top_spot_ids(seeded, client=fake, cache=cache, today=day)
    calls_after_first = fake.forecast_calls
    discovery.top_spot_ids(seeded, client=fake, cache=cache, today=day)
    # Second call served from cache — no further forecast fetches.
    assert fake.forecast_calls == calls_after_first


# --- resilience: the widget must never 500 ---------------------------------

class _ThrowingClient:
    """Open-Meteo double that always fails — simulates the provider being down /
    rate-limiting / timing out (the likely production 500 trigger)."""

    def fetch_forecast(self, *a, **k):
        raise RuntimeError("open-meteo unreachable")

    def fetch_marine(self, *a, **k):
        raise RuntimeError("open-meteo unreachable")


def test_endpoint_survives_forecast_provider_down(client, seeded, fake_live):
    # Provider down -> per-spot fallback to climatology; must NOT 500.
    app.dependency_overrides[get_om_client] = lambda: _ThrowingClient()
    resp = client.get("/spots/top?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert 0 < len(body) <= 5
    assert all(item["status"] == "published" for item in body)


def test_service_does_not_raise_when_provider_down(seeded):
    ids = discovery.top_spot_ids(
        seeded, limit=5, client=_ThrowingClient(), cache=InMemoryCache(),
        today=date(2026, 7, 18),
    )
    assert 0 < len(ids) <= 5


def test_service_survives_unknown_sport(seeded):
    # A spot whose sport has no scoring params used to KeyError in the (unguarded)
    # climatology fallback and 500 the whole endpoint. Mutate in-memory only.
    spot = seeded.scalars(select(Spot).where(Spot.status == "published")).first()
    spot.sports = ["foil"]  # not in SCORING_PARAMS_V1
    ids = discovery.top_spot_ids(
        seeded, limit=5, client=FakeOpenMeteoClient(), cache=InMemoryCache(),
        today=date(2026, 7, 18),
    )
    assert 0 < len(ids) <= 5


def test_endpoint_degrades_to_published_list_on_error(
    client, seeded, fake_live, monkeypatch
):
    # Even an unexpected failure inside the ranking degrades to a published list.
    import app.api.spots as spots_api

    def _boom(*a, **k):
        raise RuntimeError("ranking blew up")

    monkeypatch.setattr(spots_api.discovery, "top_spot_ids", _boom)
    resp = client.get("/spots/top?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert 0 < len(body) <= 5
    assert all(item["status"] == "published" for item in body)
