"""Tests for the featured Top-Spots cache warm-up (DB-gated)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.discovery import service as discovery
from app.discovery.warmup import _landing_weeks, warm_once
from app.live.cache import InMemoryCache
from app.models import RecommendationLog
from app.recommendations.multisport import (
    AGGREGATE_SPORTS,
    _cache_key as multisport_cache_key,
    scored_recommendations,
)
from app.recommendations.service import RecommendationSurface
from app.seed.seed import seed
from tests.live_helpers import FakeOpenMeteoClient


@pytest.fixture
def seeded(db):
    seed(db)
    return db


def test_warm_once_populates_cache(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)
    logs_before = seeded.scalar(select(func.count()).select_from(RecommendationLog))

    results = warm_once(
        limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day
    )

    assert results and results[0][1] == 5          # (sport, limit, n)
    assert 0 < results[0][2] <= 5
    assert fake.forecast_calls > 0                  # first run did the work
    assert seeded.scalar(select(func.count()).select_from(RecommendationLog)) == logs_before


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


@pytest.mark.parametrize(
    "surface",
    [
        RecommendationSurface.NOW,
        RecommendationSurface.NEXT_WEEK,
        RecommendationSurface.SEASON,
    ],
)
def test_warm_once_covers_exact_anonymous_landing_queries(seeded, surface):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    warm_once(limits=[8], sports=[None], db=seeded, client=fake, cache=cache, today=day)
    warmed_calls = fake.forecast_calls
    rows = scored_recommendations(
        seeded,
        surface=surface,
        sports=AGGREGATE_SPORTS,
        client=fake,
        cache=cache,
        weeks=_landing_weeks(day) if surface == RecommendationSurface.SEASON else None,
        limit=5,
    )

    key = multisport_cache_key(
        sports=AGGREGATE_SPORTS,
        surface=surface,
        region_id=None,
        month=None,
        weeks=_landing_weeks(day) if surface == RecommendationSurface.SEASON else None,
        level=None,
        limit=5,
    )
    assert cache.get(key) == [str(row.id) for row in rows]
    if surface != RecommendationSurface.SEASON:
        assert rows
    assert fake.forecast_calls == warmed_calls


def test_warm_once_warms_multiple_limits(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    results = warm_once(
        limits=[3, 5], sports=[None], db=seeded, client=fake, cache=cache, today=day
    )

    assert {r[1] for r in results} == {3, 5}
