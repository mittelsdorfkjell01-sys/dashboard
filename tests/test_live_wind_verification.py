from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from app.weather.live_wind_analysis import StationResidualInput, TargetModelState
from app.weather.live_wind_verification import (
    HoldoutPrediction,
    LiveWindHoldoutCase,
    LiveWindVerificationPolicy,
    evaluate_live_wind_holdouts,
    persist_live_wind_verification_evidence,
)

TRAINING_END = datetime(2026, 1, 1, tzinfo=timezone.utc)


def residual(station: str, observation: str, group: str) -> StationResidualInput:
    return StationResidualInput(
        residual_id=f"res-{station}",
        analysis_id=f"analysis-{station}",
        station_id=station,
        observation_id=observation,
        provider="test",
        observed_at=TRAINING_END + timedelta(days=2),
        residual_u_ms=-2.0,
        residual_v_ms=0.0,
        selection_weight=1.0,
        residual_uncertainty_ms=0.5,
        qc_status="accepted",
        correlation_group=group,
        terrain_similarity=1.0,
        coastal_similarity=1.0,
        elevation_similarity=1.0,
        air_mass_similarity=1.0,
    )


def case(index: int, *, country="DE") -> LiveWindHoldoutCase:
    observed_at = TRAINING_END + timedelta(days=2 + index)
    target = TargetModelState(
        u_ms=10.0,
        v_ms=0.0,
        valid_at=observed_at,
        model_version="raw-v1",
        model_ids=("icon_eu", "ncep_gfs_global"),
        model_spread_ms=1.0,
    )
    return LiveWindHoldoutCase(
        case_id=f"case-{index}",
        target_station_id=f"target-{index}",
        target_observation_id=f"target-observation-{index}",
        observed_at=observed_at,
        observed_u_ms=8.0,
        observed_v_ms=0.0,
        target_model=target,
        residuals=(
            residual(f"target-{index}", f"target-observation-{index}", "duplicate-group"),
            residual(f"duplicate-{index}", f"duplicate-observation-{index}", "duplicate-group"),
            residual(f"independent-{index}", f"independent-observation-{index}", f"group-{index}"),
        ),
        dependent_station_ids=(f"duplicate-{index}",),
        dependent_correlation_groups=("duplicate-group",),
        country=country,
        terrain_class="coastal",
        coastal_class="coast",
        season="winter",
        wind_sector="W",
        local_physics_prediction=HoldoutPrediction(9.5, 0.0),
        ablation_predictions={"without_terrain": HoldoutPrediction(9.0, 0.0)},
    )


def test_spatial_loso_removes_target_duplicates_and_dependent_groups():
    seen = []

    def builder(item, residuals):
        seen.append(residuals)
        assert {residual.station_id for residual in residuals} == {
            f"independent-{item.case_id.removeprefix('case-')}"
        }
        return HoldoutPrediction(8.1, 0.0, 1.0, 0.0, 1.0)

    policy = LiveWindVerificationPolicy(
        minimum_samples=3,
        minimum_days=3,
        minimum_stations=3,
        minimum_uv_mae_drop_ms=0.1,
        bootstrap_iterations=200,
    )
    result = evaluate_live_wind_holdouts(
        [case(0), case(1, country="DK"), case(2)],
        candidate_version="candidate-v1",
        training_window_end=TRAINING_END,
        candidate_builder=builder,
        policy=policy,
    )

    assert len(seen) == 3
    assert result.status == "passed"
    assert result.metrics["multi_station_live_wind"]["uv_mae_ms"] < result.metrics["raw_consensus"]["uv_mae_ms"]
    assert result.metrics["activation"]["ci_lower_ms"] > 0
    assert "ablation:without_terrain" in result.metrics
    assert set(result.stratified_metrics) == {
        "country", "terrain_class", "coastal_class", "season", "wind_sector",
        "wind_strength", "station_density",
    }


def test_training_embargo_and_temporal_day_blocks_are_enforced():
    too_early = case(0)
    too_early = LiveWindHoldoutCase(
        **{
            **too_early.__dict__,
            "observed_at": TRAINING_END + timedelta(hours=12),
            "target_model": TargetModelState(
                **{
                    **too_early.target_model.__dict__,
                    "valid_at": TRAINING_END + timedelta(hours=12),
                }
            ),
        }
    )
    policy = LiveWindVerificationPolicy(
        minimum_samples=2,
        minimum_days=2,
        minimum_stations=2,
        bootstrap_iterations=200,
    )
    result = evaluate_live_wind_holdouts(
        [too_early, case(1)],
        candidate_version="candidate-v1",
        training_window_end=TRAINING_END,
        candidate_builder=lambda _case, _residuals: HoldoutPrediction(8.0, 0.0),
        policy=policy,
    )

    assert result.matched_samples == 1
    assert result.status == "collecting"
    assert "samples_low" in result.reason


def test_context_hash_is_deterministic_and_changes_with_candidate_version():
    policy = LiveWindVerificationPolicy(
        minimum_samples=2,
        minimum_days=2,
        minimum_stations=2,
        bootstrap_iterations=200,
    )
    def builder(_case, _residuals):
        return HoldoutPrediction(8.0, 0.0)
    first = evaluate_live_wind_holdouts(
        [case(0), case(1)],
        candidate_version="candidate-v1",
        training_window_end=TRAINING_END,
        candidate_builder=builder,
        policy=policy,
    )
    repeat = evaluate_live_wind_holdouts(
        [case(1), case(0)],
        candidate_version="candidate-v1",
        training_window_end=TRAINING_END,
        candidate_builder=builder,
        policy=policy,
    )
    changed = evaluate_live_wind_holdouts(
        [case(0), case(1)],
        candidate_version="candidate-v2",
        training_window_end=TRAINING_END,
        candidate_builder=builder,
        policy=policy,
    )

    assert first.context_hash == repeat.context_hash
    assert first.input_hash == repeat.input_hash
    assert changed.context_hash != first.context_hash
    reviewed = evaluate_live_wind_holdouts(
        [case(0), case(1)], candidate_version="candidate-v1",
        training_window_end=TRAINING_END, candidate_builder=builder,
        policy=LiveWindVerificationPolicy(
            minimum_samples=2, minimum_days=2, minimum_stations=2,
            bootstrap_iterations=200, subgroup_policy_version="reviewed-v1",
            maximum_subgroup_regression_ms=0.1,
        ),
    )
    assert reviewed.context_hash != first.context_hash
    assert reviewed.policy["subgroup_policy_version"] == "reviewed-v1"


def test_verification_evidence_is_insert_only_for_one_context(db):
    policy = LiveWindVerificationPolicy(
        minimum_samples=3,
        minimum_days=3,
        minimum_stations=3,
        minimum_uv_mae_drop_ms=0.1,
        bootstrap_iterations=200,
    )
    result = evaluate_live_wind_holdouts(
        [case(0), case(1), case(2)],
        candidate_version=f"test-{uuid.uuid4().hex}",
        training_window_end=TRAINING_END,
        candidate_builder=lambda _case, _residuals: HoldoutPrediction(8.0, 0.0),
        policy=policy,
    )

    try:
        assert persist_live_wind_verification_evidence(db, result) is True
        assert persist_live_wind_verification_evidence(db, result) is False
    finally:
        db.rollback()


def test_direction_metric_handles_north_transition():
    speed = 8.0
    radians = __import__("math").radians(359)
    observed_u = -speed * __import__("math").sin(radians)
    observed_v = -speed * __import__("math").cos(radians)
    item = case(0)
    item = LiveWindHoldoutCase(
        **{**item.__dict__, "observed_u_ms": observed_u, "observed_v_ms": observed_v}
    )
    predicted_radians = __import__("math").radians(1)
    prediction = HoldoutPrediction(
        -speed * __import__("math").sin(predicted_radians),
        -speed * __import__("math").cos(predicted_radians),
    )
    policy = LiveWindVerificationPolicy(
        minimum_samples=1,
        minimum_days=2,
        minimum_stations=2,
        bootstrap_iterations=200,
    )
    result = evaluate_live_wind_holdouts(
        [item],
        candidate_version="candidate-v1",
        training_window_end=TRAINING_END,
        candidate_builder=lambda _case, _residuals: prediction,
        policy=policy,
    )
    assert result.metrics["multi_station_live_wind"]["direction_mae_deg"] == pytest.approx(2.0)
