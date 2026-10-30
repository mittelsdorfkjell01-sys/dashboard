from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.weather.decision_gates import evaluate_evidence, required_data_kinds


def _evidence(**overrides):
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    values = {
        "data_kind": "wind", "status": "accepted", "policy_version": "decision-support-v1",
        "reviewed_at": now, "reviewed_by": "reviewer@example.test",
        "observation_count": 700, "distinct_days": 21, "coverage_ratio": 0.92,
        "quality_ratio": 0.96, "monitor_fresh_at": now,
        "metrics": {"baseline_mae": 1.8, "candidate_mae": 1.5, "mae_improvement": 0.3, "calibrated": True, "acceptance_passed": True},
        "dataset_start": date(2026, 10, 12), "dataset_end": date(2026, 11, 2),
        "artifact_uri": "artifact://forecast/wind/run-1.json", "artifact_sha256": "a" * 64,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_wind_gate_stays_closed_without_approved_product_policy():
    after = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    assert "acceptance_policy_not_approved" in evaluate_evidence(_evidence(), now=after)
    during = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    blockers = evaluate_evidence(_evidence(monitor_fresh_at=during), now=during)
    assert "wind_measurement_campaign_not_ended" in blockers


def test_gate_records_weak_result_but_does_not_invent_unapproved_thresholds():
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    blockers = evaluate_evidence(_evidence(
        monitor_fresh_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        coverage_ratio=0.4,
        metrics={"baseline_mae": 1.8, "candidate_mae": 1.75, "mae_improvement": 0.05, "calibrated": True, "acceptance_passed": True},
    ), now=now)
    assert "acceptance_policy_not_approved" in blockers
    assert "candidate_not_better_than_baseline" not in blockers


def test_surf_sorting_requires_wave_and_wind_but_kite_does_not_claim_wave():
    assert required_data_kinds("forecast_sorting", "surf") == ("wind", "wave")
    assert required_data_kinds("forecast_sorting", "kitesurf") == ("wind",)


def test_gate_fails_closed_for_malformed_metrics_and_hash():
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    blockers = evaluate_evidence(_evidence(
        metrics={"baseline_mae": "bad", "candidate_mae": None, "mae_improvement": {}, "calibrated": True, "acceptance_passed": True},
        artifact_sha256="z" * 64,
    ), now=now)
    assert {"metrics_invalid", "reproducible_artifact_missing"} <= set(blockers)
