"""Tests for the featured Top-Spots cache warm-up (DB-gated)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.discovery import service as discovery
from app.discovery.warmup import warm_once
from app.live.cache import InMemoryCache
from app.models import RecommendationLog
from app.seed.seed import seed
from tests.live_helpers import FakeOpenMeteoClient


@pytest.fixture
def seeded(db):
    seed(db)
    return db


def test_warm_once_populates_cache(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    results = warm_once(
        limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day
    )

    assert results and results[0][1] == 5          # (sport, limit, n)
    assert 0 < results[0][2] <= 5
    assert fake.forecast_calls > 0                  # first run did the work
    assert seeded.scalar(select(func.count()).select_from(RecommendationLog)) == 0


def test_warm_once_makes_endpoint_read_free(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    warm_once(limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day)
    warmed_calls = fake.forecast_calls

    # A subsequent request for the same (sport, limit, day) is served from the
    # warmed cache — no further forecast fetches.
    ids = discovery.top_spot_ids(
        seeded, limit=5, sport=None, client=fake, cache=cache, today=day
    )
    assert fake.forecast_calls == warmed_calls
    assert 0 < len(ids) <= 5


def test_warm_once_second_run_is_noop(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    warm_once(limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day)
    after_first = fake.forecast_calls
    warm_once(limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day)

    assert fake.forecast_calls == after_first       # cache hit -> no re-fetch


def test_warm_once_warms_multiple_limits(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    results = warm_once(
        limits=[3, 5], sports=[None], db=seeded, client=fake, cache=cache, today=day
    )

    assert {r[1] for r in results} == {3, 5}
