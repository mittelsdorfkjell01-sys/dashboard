from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.weather.observations import public_measurement
from app.weather.observation_worker import import_station
from app.weather.providers.common import normalize_observation

NOW = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)


def station(**patch):
    data = dict(active=True, approved=True, blocked=False, representativeness_status="passed")
    data.update(patch)
    return SimpleNamespace(**data)


def observation(**patch):
    data = dict(observed_at=NOW-timedelta(minutes=10), wind_speed_ms=8.0,
                wind_gust_ms=11.0, wind_direction_deg=240.0,
                provider_quality="good", import_status="accepted")
    data.update(patch)
    return SimpleNamespace(**data)


@pytest.mark.parametrize("patch,reason", [
    ({"observed_at": NOW-timedelta(minutes=31)}, "observation_stale"),
    ({"observed_at": NOW+timedelta(minutes=3)}, "observation_future"),
    ({"wind_direction_deg": 360}, "wind_direction_invalid"),
    ({"wind_gust_ms": 7}, "gust_below_wind"),
])
def test_public_measurement_rejects_invalid_inputs(patch, reason):
    eligible, reasons = public_measurement(station(), observation(**patch), now=NOW)
    assert not eligible and reason in reasons


def test_unapproved_station_never_replaces_model():
    assert public_measurement(station(approved=False), observation(), now=NOW)[0] is False


def test_normalized_contract_keeps_provider_capture_and_problems():
    row = normalize_observation(provider="dmi", station_id="x", observed_at=NOW,
                                wind_speed_ms=8, wind_direction_deg=400,
                                wind_gust_ms=7, provider_quality="suspect", fetched_at=NOW)
    assert row.provider == "dmi" and row.fetched_at == NOW
    assert row.import_status == "rejected"
    assert {"wind_direction:invalid", "wind_gust:invalid"} <= set(row.data_issues)


def test_provider_failure_is_bounded_and_sanitized():
    calls = 0
    def fail(_station_id):
        nonlocal calls; calls += 1
        raise RuntimeError("secret")
    report = import_station(SimpleNamespace(provider_station_id="x"), fail, object(), dry_run=True, attempts=2)
    assert calls == 2 and report["error_class"] == "RuntimeError"
    assert "secret" not in str(report)
