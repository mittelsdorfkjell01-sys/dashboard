"""Tests for the featured Top-Spots cache warm-up (DB-gated)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.discovery.warmup import _landing_weeks, warm_once
from app.live.cache import InMemoryCache
from app.models import RecommendationLog
from app.recommendations.multisport import (
    AGGREGATE_SPORTS,
    _cache_key as multisport_cache_key,
    scored_recommendations,
)
from app.recommendations.service import RecommendationSurface, catalog_discovery
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
    # Forecast ranking is intentionally gated off until a product policy and
    # matching evidence have been approved. The warmup must keep that fallback
    # provider-free instead of silently exercising the old scorer.
    assert fake.forecast_calls == 0
    assert seeded.scalar(select(func.count()).select_from(RecommendationLog)) == logs_before


def test_warm_once_keeps_catalog_fallback_provider_free(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    warm_once(limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day)
    warmed_calls = fake.forecast_calls

    # The public path uses the transparent catalogue fallback while the gate is
    # closed. It is a cheap DB read and must not contact the forecast provider.
    ids = [row.id for row in catalog_discovery(
        seeded, sport=None, region_id=None, limit=5
    )]
    assert fake.forecast_calls == warmed_calls
    assert 0 < len(ids) <= 5


def test_warm_once_second_run_is_noop(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    warm_once(limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day)
    after_first = fake.forecast_calls
    warm_once(limits=[5], sports=[None], db=seeded, client=fake, cache=cache, today=day)

    assert fake.forecast_calls == after_first       # cache hit -> no re-fetch


def test_warm_once_covers_exact_anonymous_season_query(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    warm_once(limits=[8], sports=[None], db=seeded, client=fake, cache=cache, today=day)
    warmed_calls = fake.forecast_calls
    surface = RecommendationSurface.SEASON
    rows = scored_recommendations(
        seeded,
        surface=surface,
        sports=AGGREGATE_SPORTS,
        client=fake,
        cache=cache,
        weeks=_landing_weeks(day),
        limit=5,
    )

    key = multisport_cache_key(
        sports=AGGREGATE_SPORTS,
        surface=surface,
        region_id=None,
        month=None,
        weeks=_landing_weeks(day),
        level=None,
        limit=5,
    )
    assert cache.get(key) == [str(row.id) for row in rows]
    assert fake.forecast_calls == warmed_calls


def test_warm_once_warms_multiple_limits(seeded):
    fake, cache = FakeOpenMeteoClient(), InMemoryCache()
    day = date(2026, 7, 18)

    results = warm_once(
        limits=[3, 5], sports=[None], db=seeded, client=fake, cache=cache, today=day
    )

    assert {r[1] for r in results} == {3, 5}
