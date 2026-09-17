"""Contract tests for the separate, optional LiveWind analysis product."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.live import LiveConditionsRead, LiveWindRead
from app.weather.vectors import wind_to_uv


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _model_source() -> dict:
    return {
        "source_type": "model_nowcast",
        "source": "current",
        "provider": "Surfwinddata · Open-Meteo",
        "model_version": "consensus-v1",
        "valid_at": NOW,
        "captured_at": NOW,
    }


def _baseline(**patch) -> dict:
    speed = 12.0
    direction = 225.0
    u_ms, v_ms = wind_to_uv(speed, direction)
    data = {
        "status": "baseline",
        "analyzed_at": NOW,
        "valid_at": NOW,
        "wind_speed_ms": speed,
        "wind_direction_from_deg": direction,
        "wind_u_ms": u_ms,
        "wind_v_ms": v_ms,
        "model_version": "consensus-v1",
        "analysis_version": "live-wind-baseline-v1",
        "station_count": 0,
        "uncertainty_ms": 1.4,
        "confidence": 0.78,
        "sources": [_model_source()],
        "applied_physics_version": "local-physics-v1",
        "fallback_reason": None,
    }
    data.update(patch)
    return data


def test_missing_live_wind_serializes_as_explicit_engine_disabled_product():
    item = LiveConditionsRead.model_validate({
        "spot_id": str(uuid.uuid4()),
        "model": "surfwinddata",
        "current": {"wind_ms": 10.0, "dir": 270.0},
    })

    dumped = item.model_dump(mode="json")
    assert dumped["current"]["wind_ms"] == 10.0
    assert dumped["measurement"] is None
    assert dumped["live_wind"] == {
        "contract_version": "live-wind-v1",
        "product_type": "live_wind",
        "status": "unavailable",
        "fallback_level": None,
        "analyzed_at": None,
        "valid_at": None,
        "expires_at": None,
        "oldest_source_at": None,
        "max_station_age_seconds": None,
        "wind_speed_ms": None,
        "wind_direction_from_deg": None,
        "wind_u_ms": None,
        "wind_v_ms": None,
        "gust": None,
        "model_version": None,
        "analysis_version": None,
        "station_count": 0,
        "uncertainty_ms": None,
        "speed_uncertainty_band_ms": None,
        "direction_uncertainty_deg": None,
        "uncertainty_components": None,
        "confidence": None,
        "sources": [],
        "applied_physics_version": None,
        "fallback_reason": "engine_disabled",
        "model_baseline_u_ms": None,
        "model_baseline_v_ms": None,
        "regional_wind_u_ms": None,
        "regional_wind_v_ms": None,
        "correction_u_ms": None,
        "correction_v_ms": None,
        "model_spread_ms": None,
        "conflict_index": None,
        "covariance": None,
        "evidence_strength": None,
        "effective_station_count": None,
        "station_contributions": [],
        "analysis_configuration": None,
        "local_physics_component": None,
    }


def test_baseline_round_trip_preserves_vector_and_gust_provenance():
    gust_source = _model_source()
    gust_source["source"] = "current_gust"
    item = LiveWindRead.model_validate(_baseline(
        gust={"wind_gust_ms": 16.0, "provenance": gust_source}
    ))

    dumped = item.model_dump(mode="json")
    restored = LiveWindRead.model_validate(dumped)
    assert restored.product_type == "live_wind"
    assert restored.wind_speed_ms == 12.0
    assert restored.gust is not None
    assert restored.gust.provenance.source == "current_gust"


def test_live_wind_rejects_inconsistent_speed_direction_and_vector():
    with pytest.raises(ValidationError, match="speed, direction, and u/v"):
        LiveWindRead.model_validate(_baseline(wind_u_ms=0.0, wind_v_ms=12.0))


def test_unavailable_live_wind_cannot_contain_fabricated_values():
    with pytest.raises(ValidationError, match="must not contain analyzed values"):
        LiveWindRead.model_validate({
            "status": "unavailable",
            "wind_speed_ms": 12.0,
            "fallback_reason": "engine_disabled",
        })

    with pytest.raises(ValidationError, match="requires a fallback reason"):
        LiveWindRead.model_validate({
            "status": "unavailable",
            "fallback_reason": "   ",
        })


def test_station_adjusted_status_requires_station_evidence():
    with pytest.raises(ValidationError, match="requires a station source"):
        LiveWindRead.model_validate(_baseline(status="station_adjusted"))


def test_live_wind_rejects_raw_station_measurement_as_an_analysis_source():
    raw_station = {
        "source_type": "station_measurement",
        "source": "raw_station",
        "provider": "test",
        "observed_at": NOW,
    }
    with pytest.raises(ValidationError, match="station residuals"):
        LiveWindRead.model_validate(
            _baseline(sources=[_model_source(), raw_station])
        )


def test_baseline_status_rejects_station_influence():
    with pytest.raises(ValidationError, match="must not claim station influence"):
        LiveWindRead.model_validate(_baseline(station_count=1))


def test_live_wind_timestamps_must_be_timezone_aware():
    with pytest.raises(ValidationError, match="timestamps must be timezone-aware"):
        LiveWindRead.model_validate(_baseline(analyzed_at="2026-09-13T12:00:00"))
