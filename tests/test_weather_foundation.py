"""Unit tests for the provider-neutral weather foundation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.weather.contracts import ForecastPoint, ForecastRequest, ModelFamily
from app.weather.units import WindSpeedUnit, convert_wind_speed
from app.weather.vectors import uv_to_wind, weighted_vector_mean, wind_to_uv
from app.live.cache import InMemoryCache
from app.weather.budget import ProviderBudgetExceeded, RequestBudget


def test_wind_unit_round_trip_does_not_recalculate_or_round():
    knots = 17.3
    metres = convert_wind_speed(knots, WindSpeedUnit.KNOTS, WindSpeedUnit.METRES_PER_SECOND)
    assert convert_wind_speed(metres, WindSpeedUnit.METRES_PER_SECOND, WindSpeedUnit.KNOTS) == pytest.approx(knots)
    assert convert_wind_speed(10.0, WindSpeedUnit.METRES_PER_SECOND, WindSpeedUnit.KILOMETRES_PER_HOUR) == pytest.approx(36.0)


@pytest.mark.parametrize("direction", [0.0, 45.0, 180.0, 270.0, 359.999])
def test_wind_vector_round_trip(direction: float):
    u, v = wind_to_uv(12.0, direction)
    speed, restored = uv_to_wind(u, v)
    assert speed == pytest.approx(12.0)
    assert restored == pytest.approx(direction)


def test_vector_consensus_handles_zero_degree_boundary():
    speed, direction = weighted_vector_mean([(10.0, 350.0, 1.0), (10.0, 10.0, 1.0)])
    assert speed == pytest.approx(9.8480775)
    assert direction == pytest.approx(0.0, abs=1e-10)


def test_opposing_winds_result_in_calm_without_invented_direction():
    speed, direction = weighted_vector_mean([(10.0, 0.0, 1.0), (10.0, 180.0, 1.0)])
    assert speed == pytest.approx(0.0, abs=1e-12)
    assert direction is None


def test_negative_and_empty_weights_are_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        weighted_vector_mean([(10.0, 0.0, -1.0)])
    with pytest.raises(ValueError, match="positive"):
        weighted_vector_mean([(10.0, 0.0, 0.0)])


def test_forecast_contract_requires_utc_and_ordered_window():
    now = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
    request = ForecastRequest(
        latitude=54.5,
        longitude=10.2,
        start=now,
        end=now + timedelta(days=10),
        model_ids=("icon_d2", "ecmwf_ifs"),
    )
    assert request.start.tzinfo is timezone.utc

    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        ForecastRequest(
            latitude=54.5,
            longitude=10.2,
            start=now.replace(tzinfo=None),
            end=now + timedelta(days=1),
            model_ids=("icon_d2",),
        )


def test_forecast_point_rejects_gust_below_mean_wind():
    with pytest.raises(ValidationError, match="gust speed"):
        ForecastPoint(
            valid_at=datetime(2026, 8, 9, 12, tzinfo=timezone.utc),
            model_id="icon_d2",
            family=ModelFamily.REGIONAL,
            wind_speed_ms=10.0,
            wind_direction_deg=270.0,
            gust_speed_ms=9.0,
        )


def test_process_cache_expires_and_does_not_restore_data():
    now = [10.0]
    cache = InMemoryCache(clock=lambda: now[0])
    cache.set("forecast", {"ok": True}, ttl=15)
    assert cache.get("forecast") == {"ok": True}
    now[0] = 25.0
    assert cache.get("forecast") is None


def test_provider_budget_rejects_excess_requests():
    now = [0.0]
    budget = RequestBudget(per_minute=2, per_hour=10, clock=lambda: now[0])
    budget.consume()
    budget.consume()
    with pytest.raises(ProviderBudgetExceeded):
        budget.consume()
    now[0] = 61.0
    budget.consume()
