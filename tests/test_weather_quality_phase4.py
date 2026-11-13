from datetime import datetime, timedelta, timezone

import pytest

from app.weather.consensus import WindMember, calculate_wind_consensus
from app.weather.monitoring import IncidentDeduplicator, evaluate
from app.weather.verification import MIN_CALIBRATION_SAMPLES, circular_error_deg, evaluate_calibration_holdout, verification_metrics


def test_invalid_member_never_reaches_consensus_math():
    result = calculate_wind_consensus([
        WindMember("icon", 8, 270, 11),
        WindMember("gfs", float("nan"), 20, 30),
        WindMember("ecmwf", 5, 400, 6),
    ], 3)
    assert result is not None
    assert result.member_count == 1
    assert result.weights == {"icon": 1.0}


def _holdout_rows(*, calibrated_delta: float):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [{
        "valid_at": start + timedelta(hours=index), "wind_pred": 12.0, "wind_obs": 10.0,
        "wind_calibrated": 10.0 + calibrated_delta,
        "direction_pred": 350.0, "direction_obs": 10.0,
        "gust_pred": 15.0, "gust_obs": 14.0,
    } for index in range(MIN_CALIBRATION_SAMPLES + 30)]


def test_verification_metrics_include_circular_direction_and_gust():
    metrics = verification_metrics(_holdout_rows(calibrated_delta=0)[:2])
    assert metrics.wind_mae_ms == 2
    assert metrics.wind_bias_ms == 2
    assert metrics.direction_mae_deg == 20
    assert metrics.gust_mae_ms == 1
    assert circular_error_deg(1, 359) == 2


def test_holdout_requires_samples_and_rejects_degradation():
    small = evaluate_calibration_holdout(_holdout_rows(calibrated_delta=0)[:MIN_CALIBRATION_SAMPLES])
    assert small.approved is False
    assert small.reason == "insufficient_samples"
    worse = evaluate_calibration_holdout(_holdout_rows(calibrated_delta=4))
    assert worse.approved is False
    assert worse.reason == "holdout_not_improved"
    improved = evaluate_calibration_holdout(_holdout_rows(calibrated_delta=0))
    assert improved.approved is True
    assert improved.version == "holdout-v1"


def test_monitoring_is_structured_pending_and_redacts_secrets():
    result = evaluate({"liveness": "ok", "readiness": "down", "schema": "unknown",
                       "catalog_version": "ok", "canary_contract": "error",
                       "providers": {"error": "token=super-secret connection failed"},
                       "budget": {"api_key": "do-not-print"}})
    encoded = str(result)
    assert result["status"] == "error"
    assert len(result["incidents"]) == 3
    assert set(result["slo"].values()) == {"pending_evidence"}
    assert "super-secret" not in encoded and "do-not-print" not in encoded


def test_incident_deduplication_calls_writer_once():
    class Store:
        def __init__(self): self.items = []
        def exists(self, fingerprint): return any(item["fingerprint"] == fingerprint for item in self.items)
        def create(self, item): self.items.append(item)

    store = Store()
    dedupe = IncidentDeduplicator(store)
    incident = evaluate({})["incidents"][0]
    assert dedupe.publish_once(incident) is True
    assert dedupe.publish_once(incident) is False
    assert len(store.items) == 1

