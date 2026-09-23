from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api._http_cache import set_recommendation_cache
from app.recommendations.engine import character_fit, condition_fit, forecast_components
from app.recommendations.service import bucket_location
from app.scoring.rider.band import PersonalBand


BAND = PersonalBand(12, 17, 25, 34, 8, "fingerprint")


def _spot(**overrides):
    values = {
        "style": ["freeride"],
        "water_character": ["flach"],
        "bottom_type": ["sand"],
        "facing": 180,
        "editorial": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _hours(count: int, *, wind: float = 21, direction: float = 180):
    start = datetime(2026, 7, 1, 10, tzinfo=timezone.utc)
    return [
        {
            "time": (start + timedelta(hours=index)).isoformat(),
            "wind": wind,
            "gust": wind + 4,
            "dir": direction,
            "is_day": True,
            "sst": 18,
        }
        for index in range(count)
    ]


def test_condition_fit_uses_personal_band_and_big_air_tilts_upward():
    assert condition_fit(12, BAND) == 0
    assert condition_fit(21, BAND) == 1
    assert condition_fit(34, BAND) == 0
    assert condition_fit(27, BAND, 3) > condition_fit(15, BAND, 3)


def test_forecast_requires_a_three_hour_daylight_session():
    profile = {"level": "advanced", "style_weights": {"freeride": 3}}
    windows = [{"min": 150, "max": 220}]
    too_short = forecast_components(
        profile, BAND, _spot(), [{"date": "2026-07-01", "hours": _hours(2), "confidence": 0.9}],
        direction_windows=windows,
    )
    session = forecast_components(
        profile, BAND, _spot(), [{"date": "2026-07-01", "hours": _hours(3), "confidence": 0.9}],
        direction_windows=windows,
    )
    assert too_short.utility == 0
    assert session.utility > 0


def test_character_fit_excludes_selected_bottom_and_changes_style_order():
    freeride = {"style_weights": {"freeride": 3, "big_air": 0}}
    big_air = {"style_weights": {"freeride": 0, "big_air": 3}}
    freeride_spot = _spot(style=["freeride"])
    big_air_spot = _spot(style=["big_air"])
    assert character_fit(freeride, freeride_spot) > character_fit(freeride, big_air_spot)
    assert character_fit(big_air, big_air_spot) > character_fit(big_air, freeride_spot)
    assert character_fit({**freeride, "excluded_bottoms": ["reef"]}, _spot(bottom_type=["reef"])) == 0


def test_location_is_reduced_to_a_stable_bucket():
    first = bucket_location(54.401, 10.201)
    second = bucket_location(54.449, 10.249)
    assert first == second
    assert first is not None
    assert "54.401" not in first.cache_token


def test_recommendation_cache_headers_separate_account_responses():
    from fastapi import Response

    public = Response()
    private = Response()
    set_recommendation_cache(public, private=False)
    set_recommendation_cache(private, private=True)
    assert public.headers["Cache-Control"].startswith("public")
    assert private.headers["Cache-Control"] == "private, no-store"
    assert "Cookie" in public.headers["Vary"]


@pytest.mark.parametrize("lat,lon", [(None, 10.0), (54.0, None), (91.0, 10.0)])
def test_location_bucket_rejects_partial_or_invalid_coordinates(lat, lon):
    with pytest.raises(ValueError):
        bucket_location(lat, lon)
