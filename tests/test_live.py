"""Mocked Open-Meteo tests for the live + forecast path. No network, no database."""

from __future__ import annotations

import pytest

from app.live.cache import InMemoryCache, cache_key
from app.live.client import MAX_FORECAST_DAYS
from app.live.models import AROME, BEST_MATCH, ICON_D2, ICON_EU, select_model
from app.live.service import (
    confidence_for_day,
    get_forecast_series,
    get_live_conditions,
)
from tests.live_helpers import FakeDB, FakeOpenMeteoClient, make_spot


# --- model selection -------------------------------------------------------

def test_select_model_regional_domains():
    assert select_model(48.8, 2.3) == AROME       # Paris / France
    assert select_model(52.5, 13.4) == ICON_D2    # Berlin / central EU
    assert select_model(36.0128, -5.6035) == ICON_EU  # Tarifa / wider EU
    assert select_model(0.0, -30.0) == BEST_MATCH     # mid-Atlantic


def test_select_model_respects_pref():
    # model_pref always wins, even where a regional model would apply
    assert select_model(48.8, 2.3, pref="gfs") == "gfs"


# --- cache key -------------------------------------------------------------

def test_cache_key_rounds_coordinates():
    assert cache_key("icon_eu", 36.0128, -5.6035, "forecast") == (
        "om:icon_eu:36.0128:-5.6035:forecast"
    )


def test_redis_cache_fails_open_when_redis_is_down():
    """A Redis outage must degrade to a miss / no-op, not raise — the live path
    is meant to fetch fresh, not 500, when the cache is unavailable."""
    import redis

    from app.live.cache import RedisCache

    cache = RedisCache.__new__(RedisCache)  # skip real connection

    class _DeadRedis:
        def get(self, key):
            raise redis.ConnectionError("boom")

        def set(self, key, value, ex=None):
            raise redis.ConnectionError("boom")

    cache._r = _DeadRedis()
    assert cache.get("om:x") is None  # reported as a miss
    cache.set("om:x", {"a": 1}, ttl=10)  # swallowed, no raise


def test_default_weather_cache_is_volatile_process_memory():
    import app.live.cache as cache_module

    cache_module._default_cache = None
    assert isinstance(cache_module.default_cache(), InMemoryCache)


# --- confidence staffing ---------------------------------------------------

def test_confidence_for_day_tiers():
    assert [confidence_for_day(i) for i in range(7)] == [
        "hoch", "hoch", "hoch", "mittel", "mittel", "niedrig", "niedrig",
    ]


# --- cache hit / miss ------------------------------------------------------

def test_second_call_hits_cache_no_http():
    spot = make_spot()
    db = FakeDB(spot)
    client = FakeOpenMeteoClient()
    cache = InMemoryCache()

    get_live_conditions(spot.id, db=db, client=client, cache=cache)
    assert client.forecast_calls == 1
    assert client.marine_calls == 1

    # within TTL -> served from cache, no new HTTP calls
    get_live_conditions(spot.id, db=db, client=client, cache=cache)
    assert client.forecast_calls == 1
    assert client.marine_calls == 1

    # forecast reuses the same cached forecast+marine entries -> still no calls
    get_forecast_series(spot.id, db=db, client=client, cache=cache)
    assert client.forecast_calls == 1
    assert client.marine_calls == 1


def test_live_conditions_shape_and_model():
    spot = make_spot(model_pref="icon_d2")
    out = get_live_conditions(
        spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(), cache=InMemoryCache()
    )
    assert out["model"] == "icon_d2"  # honoured model_pref
    cur = out["current"]
    assert set(cur) == {
        "wind", "gust", "dir", "air", "sst", "swell", "period", "swell_dir",
        "wind_spread", "gust_spread", "wind_ms", "gust_ms",
    }
    assert cur["wind"] == 19.4  # 10 m/s consensus exposed as compatibility knots
    assert cur["sst"] == 20.0


def test_unknown_spot_raises_lookup():
    spot = make_spot()
    other = make_spot()
    with pytest.raises(LookupError):
        get_live_conditions(
            other.id, db=FakeDB(spot), client=FakeOpenMeteoClient(),
            cache=InMemoryCache(),
        )


# --- forecast horizon + confidence -----------------------------------------

def test_forecast_returns_exactly_10_days_with_five_detail_days():
    spot = make_spot()
    client = FakeOpenMeteoClient(data_days=11)
    series = get_forecast_series(
        spot.id, days=10, db=FakeDB(spot), client=client, cache=InMemoryCache()
    )

    assert len(series["days"]) == MAX_FORECAST_DAYS
    confidences = [d["confidence"] for d in series["days"]]
    assert confidences[0] == "hoch"
    for index, day in enumerate(series["days"]):
        assert len(day["hours"]) == (24 if index < 5 else 0)
        assert day["detail"] == ("hourly" if index < 5 else "trend")
        assert "wind_max" in day["summary"]


def test_forecast_horizon_is_capped_even_if_more_requested():
    spot = make_spot()
    client = FakeOpenMeteoClient(data_days=11)
    series = get_forecast_series(
        spot.id, days=20, db=FakeDB(spot), client=client, cache=InMemoryCache()
    )
    assert len(series["days"]) == MAX_FORECAST_DAYS


def test_forecast_fewer_days_when_requested():
    spot = make_spot()
    series = get_forecast_series(
        spot.id, days=3, db=FakeDB(spot), client=FakeOpenMeteoClient(),
        cache=InMemoryCache(),
    )
    assert len(series["days"]) == 3
    assert series["days"][0]["confidence"] == "hoch"


def test_forecast_hours_merge_wind_and_swell():
    spot = make_spot()
    series = get_forecast_series(
        spot.id, days=1, db=FakeDB(spot), client=FakeOpenMeteoClient(),
        cache=InMemoryCache(),
    )
    first_hour = series["days"][0]["hours"][0]
    assert first_hour["wind"] is not None
    assert first_hour["swell"] is not None      # marine merged in
    assert first_hour["period"] is not None


def test_forecast_hours_include_precip_and_sst():
    """Sprint 3: precipitation (atmospheric) and sea-surface temperature
    (marine) round-trip into the hourly series alongside wind/swell."""
    spot = make_spot()
    series = get_forecast_series(
        spot.id, days=1, db=FakeDB(spot), client=FakeOpenMeteoClient(),
        cache=InMemoryCache(),
    )
    first_hour = series["days"][0]["hours"][0]
    assert first_hour["precip"] is not None
    assert first_hour["sst"] is not None


def test_forecast_hour_precip_is_null_not_fabricated_when_missing():
    """A spot whose provider response has no precipitation variable at all
    (coverage gap) gets `None`, never a guessed/rounded-to-0 value."""
    from tests.live_helpers import make_forecast_response, make_marine_response

    class _NoPrecipClient:
        def fetch_forecast(self, lat, lon, models, days=7) -> dict:
            data = make_forecast_response(1, models=None)
            del data["hourly"]["precipitation"]
            return data

        def fetch_marine(self, lat, lon, days=7) -> dict:
            return make_marine_response(1)

    spot = make_spot()
    series = get_forecast_series(
        spot.id, days=1, db=FakeDB(spot), client=_NoPrecipClient(),
        cache=InMemoryCache(),
    )
    assert all(h["precip"] is None for h in series["days"][0]["hours"])


# --- multi-model consensus + spread (Sprint 18) ----------------------------

def test_live_conditions_expose_consensus_band():
    spot = make_spot()
    out = get_live_conditions(
        spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(), cache=InMemoryCache()
    )
    assert len(out["models"]) >= 3            # several models fetched in one request
    cur = out["current"]
    assert cur["wind"] == 19.4                # weighted hourly consensus, exposed in knots
    band = cur["wind_spread"]                 # "now" spread from the current hour
    assert band["n"] == len(out["models"])    # all models present in the band
    assert band["low"] <= band["median"] <= band["high"]


def test_forecast_confidence_is_spread_driven():
    # tight early days -> hoch; disagreement widens toward the horizon -> niedrig
    spot = make_spot()
    series = get_forecast_series(
        spot.id, days=7, db=FakeDB(spot),
        client=FakeOpenMeteoClient(data_days=8), cache=InMemoryCache(),
    )
    confs = [d["confidence"] for d in series["days"]]
    assert confs[0] == "hoch"
    assert confs[-1] == "niedrig"
    # monotone non-improving as the horizon (and model disagreement) grows
    rank = {"hoch": 0, "mittel": 1, "niedrig": 2}
    assert all(rank[a] <= rank[b] for a, b in zip(confs, confs[1:]))
    # the day band widens for the strip
    last = series["days"][-1]["summary"]
    assert last["wind_high"] > last["wind_low"]


def test_forecast_hour_has_wind_spread():
    spot = make_spot()
    series = get_forecast_series(
        spot.id, days=2, db=FakeDB(spot),
        client=FakeOpenMeteoClient(data_days=8), cache=InMemoryCache(),
    )
    band = series["days"][1]["hours"][0]["wind_spread"]  # day 2 -> real spread
    assert band and band["n"] >= 2 and band["high"] > band["low"]


def test_consensus_degrades_gracefully_to_single_model():
    # 3 of 4 models report nothing -> n==1, no error, calendar fallback confidence
    spot = make_spot()
    client = FakeOpenMeteoClient(
        data_days=8,
        null_models=["ncep_gfs_global", "ecmwf_aifs025_single", "icon_global"],
    )
    series = get_forecast_series(
        spot.id, days=7, db=FakeDB(spot), client=client, cache=InMemoryCache()
    )
    for day in series["days"]:
        for h in day["hours"]:
            if h["wind_spread"]:
                assert h["wind_spread"]["n"] == 1   # only the primary survived
    # no spread signal -> falls back to the calendar tiers
    confs = [d["confidence"] for d in series["days"]]
    assert confs == ["hoch", "hoch", "hoch", "mittel", "mittel", "niedrig", "niedrig"]
    # still returns a wind value (the surviving model's) -> no spot falls out
    assert series["days"][0]["hours"][0]["wind"] is not None
