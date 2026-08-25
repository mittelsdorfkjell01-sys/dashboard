"""API tests for /spots/{id}/live and /forecast, with Open-Meteo + cache mocked
via FastAPI dependency overrides. DB-gated (skips when the test DB is down)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.live.cache import InMemoryCache
from app.live.client import MAX_FORECAST_DAYS
from app.live.deps import get_cache, get_om_client
from app.main import app
from app.models import Spot
from app.models.forecast_system import ForecastSnapshot
from app.seed.seed import seed
from tests.live_helpers import FakeOpenMeteoClient


def _clear_snapshots(db, *spot_ids) -> None:
    """Deactivate any published forecast snapshot for these spots.

    ``/spots/{id}/forecast`` and ``/live`` serve a published snapshot ahead of
    computing live data (see app.forecast.publisher.active_snapshot) — a real
    production fast path. The shared seeded spot can pick one up from an
    unrelated test elsewhere in the same session (e.g. a cron/publish job),
    which would silently bypass fake_live's mocked client/cache. Tests here
    exercise the live-computation path specifically, so start from no
    active snapshot rather than depending on nothing else in the session
    having published one.
    """
    from sqlalchemy import delete

    db.execute(delete(ForecastSnapshot).where(ForecastSnapshot.spot_id.in_(spot_ids)))
    db.commit()


@pytest.fixture
def seeded_spot_id(db):
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    _clear_snapshots(db, spot.id)
    return spot.id


@pytest.fixture
def fake_live(client):
    fake = FakeOpenMeteoClient(data_days=11)
    cache = InMemoryCache()
    app.dependency_overrides[get_om_client] = lambda: fake
    app.dependency_overrides[get_cache] = lambda: cache
    yield fake
    app.dependency_overrides.pop(get_om_client, None)
    app.dependency_overrides.pop(get_cache, None)


def test_live_endpoint(client, seeded_spot_id, fake_live):
    resp = client.get(f"/spots/{seeded_spot_id}/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"]
    # Public product boundary: the Surfwinddata result never exposes raw model
    # membership. Model diagnostics remain admin-only.
    assert body["models"] == []
    assert set(body["current"]) == {
        "wind", "gust", "dir", "air", "sst", "swell", "period", "swell_dir",
        "wind_spread", "gust_spread", "wind_ms", "gust_ms", "waves",
        "coastal_normal_deg", "coastal_classification", "wave_coastal_classification",
    }
    assert body["current"]["wind_spread"]["n"] >= 3


def test_forecast_endpoint_caps_at_10(client, seeded_spot_id, fake_live):
    resp = client.get(f"/spots/{seeded_spot_id}/forecast")
    assert resp.status_code == 200
    days = resp.json()["days"]
    assert len(days) == MAX_FORECAST_DAYS
    assert days[0]["confidence"] == "hoch"
    assert days[-1]["confidence"] == "niedrig"
    assert all(day["detail"] == "hourly" and day["hours"] for day in days[:5])
    assert all(day["detail"] == "trend" and day["hours"] == [] for day in days[5:])


def test_forecast_endpoint_rejects_over_horizon(client, seeded_spot_id, fake_live):
    resp = client.get(f"/spots/{seeded_spot_id}/forecast?days=11")
    assert resp.status_code == 422


def test_live_endpoint_404_for_unknown_spot(client, fake_live):
    import uuid

    resp = client.get(f"/spots/{uuid.uuid4()}/live")
    assert resp.status_code == 404


# --- batch live endpoint (replaces the per-tile fan-out) --------------------


@pytest.fixture
def seeded_spot_ids(db):
    seed(db)
    spots = db.scalars(select(Spot).order_by(Spot.name).limit(3)).all()
    _clear_snapshots(db, *(s.id for s in spots))
    return [str(s.id) for s in spots]


def test_live_batch_returns_all_requested(client, seeded_spot_ids, fake_live):
    want = seeded_spot_ids[:2]
    resp = client.get("/spots/live", params={"ids": ",".join(want)})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert {item["spot_id"] for item in body} == set(want)
    for item in body:
        assert item["model"]
        assert "wind" in item["current"]


def test_live_batch_precedes_uuid_route(client, seeded_spot_ids, fake_live):
    # /spots/live must win over /spots/{spot_id}; a list (not a single object).
    resp = client.get("/spots/live", params={"ids": seeded_spot_ids[0]})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_live_batch_skips_unknown_and_malformed(client, seeded_spot_ids, fake_live):
    import uuid

    ids = f"{seeded_spot_ids[0]},{uuid.uuid4()},not-a-uuid"
    resp = client.get("/spots/live", params={"ids": ids})
    assert resp.status_code == 200
    assert [i["spot_id"] for i in resp.json()] == [seeded_spot_ids[0]]


def test_live_batch_dedupes_ids(client, seeded_spot_ids, fake_live):
    one = seeded_spot_ids[0]
    resp = client.get("/spots/live", params={"ids": f"{one},{one}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_live_batch_caps_count(client, fake_live):
    import uuid

    ids = ",".join(str(uuid.uuid4()) for _ in range(21))
    resp = client.get("/spots/live", params={"ids": ids})
    assert resp.status_code == 400
