from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.live import LiveConditionsRead, ValueProvenance, WaveComponentsRead
from app.live.weather_contract import age_seconds, is_stale


def provenance(**patch):
    data = {
        "source_type": "forecast", "observation_type": "forecast", "source": "model", "provider": "provider",
        "model": "m1", "issued_at": None, "captured_at": "2026-08-24T10:00:00Z",
        "model_run_quality": "capture-time-only",
        "valid_at": "2026-08-24T11:00:00Z", "spot_timezone": "Europe/Berlin",
        "requested_coordinate": {"latitude": 54.0, "longitude": 10.0},
        "used_coordinate": {"latitude": 54.1, "longitude": 10.1},
        "grid_distance_km": 12.3, "age_seconds": 30, "quality_tier": "provider_point",
    }
    data.update(patch)
    return ValueProvenance.model_validate(data)


def test_total_wave_and_primary_swell_are_distinct():
    waves = WaveComponentsRead.model_validate({
        "total_wave": {"significant_height_m": 2.4, "mean_direction_from_deg": 250},
        "primary_swell": {"significant_height_m": 1.7, "mean_direction_from_deg": 270},
    })
    assert waves.total_wave.significant_height_m == 2.4
    assert waves.primary_swell.significant_height_m == 1.7
    assert waves.phase_speed_ms is None


def test_direction_is_explicitly_from_and_range_checked():
    with pytest.raises(ValidationError):
        WaveComponentsRead.model_validate({"total_wave": {"mean_direction_from_deg": 360}})


def test_canonical_time_requires_timezone_and_preserves_spot_timezone():
    assert provenance().spot_timezone == "Europe/Berlin"
    with pytest.raises(ValidationError):
        provenance(valid_at="2026-10-25T02:30:00")


def test_measurement_and_nowcast_are_not_interchangeable():
    nowcast = provenance(source_type="model_nowcast", observation_type="nowcast")
    measurement = provenance(source_type="measurement", observation_type="measurement", source="station", model=None)
    assert nowcast.observation_type == "nowcast"
    assert measurement.observation_type == "measurement"


def test_live_schema_preserves_metadata_instead_of_dropping_it():
    item = LiveConditionsRead.model_validate({
        "spot_id": "9d3cdfc6-1600-4d69-b018-c890d5d71e88", "model": "surfwinddata",
        "time": datetime.now(timezone.utc).isoformat(), "calculated": True,
        "observation_type": "nowcast", "resolution": "15 min", "trend": "stabil",
        "quality_tier": "coordinates", "availability": {"marine": "unavailable_provider"},
        "provenance": provenance(source_type="model_nowcast", observation_type="nowcast"), "current": {},
    })
    dumped = item.model_dump(mode="json")
    assert dumped["observation_type"] == "nowcast"
    assert dumped["resolution"] == "15 min"
    assert dumped["availability"]["marine"] == "unavailable_provider"
    assert dumped["provenance"]["grid_distance_km"] == 12.3


def test_unknown_model_run_is_not_replaced_by_capture_time():
    item = provenance(model_run=None, model_run_at=None, model_run_quality="capture-time-only")
    assert item.model_run_at is None
    assert item.captured_at is not None


def test_age_and_stale_are_derived_from_real_instants():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    value = datetime(2026, 8, 24, 11, 29, 59, tzinfo=timezone.utc)
    assert age_seconds(value, now=now) == 1801
    assert is_stale(1800, threshold_seconds=1800) is False
    assert is_stale(1801, threshold_seconds=1800) is True
    assert age_seconds(None, now=now) is None
