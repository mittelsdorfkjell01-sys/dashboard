"""Leakage-safe, block-held-out verification for LiveWind candidates.

The target station, its duplicate/dependency set and its correlation groups are
removed before the candidate builder is called.  Results are country-balanced
so dense station networks cannot dominate a European activation decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import random
import uuid
from typing import Callable, Mapping

from sqlalchemy.dialects.postgresql import insert

from app.models import WeatherLiveWindVerificationEvidence
from app.weather.live_wind_analysis import (
    RegionalLiveWindResult,
    StationResidualInput,
    TargetModelState,
    analyze_regional_live_wind,
)
from app.weather.vectors import uv_to_wind

LIVE_WIND_VERIFICATION_VERSION = "live-wind-spatial-loso-v1"


@dataclass(frozen=True)
class LiveWindVerificationPolicy:
    version: str = LIVE_WIND_VERIFICATION_VERSION
    minimum_samples: int = 500
    minimum_days: int = 14
    minimum_stations: int = 10
    minimum_uv_mae_drop_ms: float = 0.15
    minimum_direction_speed_ms: float = 2.0
    strong_wind_threshold_ms: float = 10.0
    holdout_block_hours: int = 24
    training_embargo_hours: int = 24
    bootstrap_iterations: int = 2000
    confidence_level: float = 0.95
    minimum_wind_sectors: int = 1
    maximum_fallback_rate: float = 1.0
    minimum_subgroup_blocks: int = 3
    subgroup_policy_version: str | None = None
    maximum_subgroup_regression_ms: float | None = None

    def __post_init__(self) -> None:
        if self.minimum_samples < 1 or self.minimum_days < 2 or self.minimum_stations < 2:
            raise ValueError("LiveWind verification minimums are invalid")
        if self.minimum_uv_mae_drop_ms <= 0:
            raise ValueError("LiveWind improvement gate must be positive")
        if self.bootstrap_iterations < 200:
            raise ValueError("LiveWind bootstrap needs at least 200 iterations")
        if not 0.5 < self.confidence_level < 1:
            raise ValueError("LiveWind confidence level must be in (0.5, 1)")
        if not 1 <= self.minimum_wind_sectors <= 8 or not 0 <= self.maximum_fallback_rate <= 1:
            raise ValueError("LiveWind coverage limits are invalid")
        if (self.subgroup_policy_version is None) != (self.maximum_subgroup_regression_ms is None):
            raise ValueError("subgroup policy version and threshold must be set together")
        if self.maximum_subgroup_regression_ms is not None and self.maximum_subgroup_regression_ms < 0:
            raise ValueError("subgroup regression threshold must be nonnegative")

    def snapshot(self) -> dict:
        return asdict(self)


DEFAULT_LIVE_WIND_VERIFICATION_POLICY = LiveWindVerificationPolicy()


def candidate_policy_hash(candidate_version: str, policy_version: str | None,
                          subgroup_limit: float | None) -> str:
    """Bind a candidate identity to the reviewed subgroup policy."""
    return hashlib.sha256(json.dumps({
        "candidate_version": candidate_version,
        "subgroup_policy_version": policy_version,
        "maximum_subgroup_regression_ms": subgroup_limit,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class HoldoutPrediction:
    u_ms: float
    v_ms: float
    covariance_uu_ms2: float | None = None
    covariance_uv_ms2: float | None = None
    covariance_vv_ms2: float | None = None


@dataclass(frozen=True)
class LiveWindHoldoutCase:
    case_id: str
    target_station_id: str
    target_observation_id: str
    observed_at: datetime
    observed_u_ms: float
    observed_v_ms: float
    target_model: TargetModelState
    residuals: tuple[StationResidualInput, ...]
    country: str
    terrain_class: str
    coastal_class: str
    season: str
    wind_sector: str
    dependent_station_ids: tuple[str, ...] = ()
    dependent_observation_ids: tuple[str, ...] = ()
    dependent_correlation_groups: tuple[str, ...] = ()
    local_physics_prediction: HoldoutPrediction | None = None
    ablation_predictions: Mapping[str, HoldoutPrediction] = field(default_factory=dict)
    candidate_prediction: HoldoutPrediction | None = None
    station_group: str | None = None
    wind_strength: str = "unknown"
    station_density: str = "unknown"
    fallback: bool = False
    input_hash: str | None = None
    weather_regime: str = "unknown"
    conflict_case: bool = False


@dataclass(frozen=True)
class LiveWindVerificationResult:
    run_id: uuid.UUID
    candidate_version: str
    context_hash: str
    input_hash: str
    training_window_end: datetime
    window_start: datetime
    window_end: datetime
    matched_samples: int
    distinct_stations: int
    distinct_days: int
    status: str
    reason: str
    metrics: dict
    stratified_metrics: dict
    policy: dict

    def evidence_values(self) -> dict:
        return {
            **asdict(self),
            "policy": self.policy,
            "metrics": self.metrics,
            "stratified_metrics": self.stratified_metrics,
        }


CandidateBuilder = Callable[
    [LiveWindHoldoutCase, tuple[StationResidualInput, ...]], HoldoutPrediction
]


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _default_candidate_builder(
    case: LiveWindHoldoutCase,
    residuals: tuple[StationResidualInput, ...],
) -> HoldoutPrediction:
    result: RegionalLiveWindResult = analyze_regional_live_wind(
        case.target_model,
        residuals,
        analyzed_at=case.observed_at,
    )
    if result.regional_u_ms is None or result.regional_v_ms is None:
        raise ValueError("LiveWind candidate unavailable for holdout")
    return HoldoutPrediction(
        u_ms=result.regional_u_ms,
        v_ms=result.regional_v_ms,
        covariance_uu_ms2=result.covariance_uu_ms2,
        covariance_uv_ms2=result.covariance_uv_ms2,
        covariance_vv_ms2=result.covariance_vv_ms2,
    )


def _held_out_residuals(case: LiveWindHoldoutCase) -> tuple[StationResidualInput, ...]:
    station_ids = {case.target_station_id, *case.dependent_station_ids}
    observation_ids = {
        case.target_observation_id,
        *case.dependent_observation_ids,
    }
    groups = set(case.dependent_correlation_groups)
    groups.update(
        residual.correlation_group
        for residual in case.residuals
        if residual.station_id == case.target_station_id
        and residual.correlation_group is not None
    )
    return tuple(
        residual
        for residual in case.residuals
        if residual.station_id not in station_ids
        and residual.observation_id not in observation_ids
        and residual.correlation_group not in groups
    )


def _prediction_error(case: LiveWindHoldoutCase, prediction: HoldoutPrediction) -> dict:
    du = prediction.u_ms - case.observed_u_ms
    dv = prediction.v_ms - case.observed_v_ms
    observed_speed, observed_direction = uv_to_wind(case.observed_u_ms, case.observed_v_ms)
    predicted_speed, predicted_direction = uv_to_wind(prediction.u_ms, prediction.v_ms)
    direction_error = None
    if (
        observed_speed > 0
        and observed_direction is not None
        and predicted_direction is not None
    ):
        direction_error = abs((predicted_direction - observed_direction + 180.0) % 360.0 - 180.0)
    covered = _covariance_contains(du, dv, prediction)
    return {
        "du": du,
        "dv": dv,
        "uv_abs": (abs(du) + abs(dv)) / 2.0,
        "speed_abs": abs(predicted_speed - observed_speed),
        "speed_bias": predicted_speed - observed_speed,
        "direction_abs": direction_error,
        "observed_speed": observed_speed,
        "uncertainty_covered": covered,
    }


def _covariance_contains(
    du: float,
    dv: float,
    prediction: HoldoutPrediction,
) -> bool | None:
    uu, uv, vv = (
        prediction.covariance_uu_ms2,
        prediction.covariance_uv_ms2,
        prediction.covariance_vv_ms2,
    )
    if None in (uu, uv, vv):
        return None
    determinant = uu * vv - uv * uv
    if determinant <= 1e-12:
        return None
    mahalanobis = (vv * du * du - 2.0 * uv * du * dv + uu * dv * dv) / determinant
    return mahalanobis <= 4.605170186  # 90% chi-square threshold, 2 DoF


def _country_weights(records: list[dict]) -> list[float]:
    groups: dict[str, dict[str, int]] = {}
    for record in records:
        country = record["country"]
        group = record.get("station_group") or record["station_id"]
        groups.setdefault(country, {})[group] = groups.setdefault(country, {}).get(group, 0) + 1
    countries = max(1, len(groups))
    return [
        1.0 / countries / len(groups[record["country"]])
        / groups[record["country"]][record.get("station_group") or record["station_id"]]
        for record in records
    ]


def _metrics(records: list[dict], variant: str, policy: LiveWindVerificationPolicy) -> dict:
    available = [record for record in records if variant in record["errors"]]
    if not available:
        return {"samples": 0}
    weights = _country_weights(available)
    errors = [record["errors"][variant] for record in available]
    direction = [
        (error["direction_abs"], weight)
        for error, weight in zip(errors, weights)
        if error["observed_speed"] >= policy.minimum_direction_speed_ms
        and error["direction_abs"] is not None
    ]
    strong = [
        (error, weight)
        for error, weight in zip(errors, weights)
        if error["observed_speed"] >= policy.strong_wind_threshold_ms
    ]
    covered = [
        (error["uncertainty_covered"], weight)
        for error, weight in zip(errors, weights)
        if error["uncertainty_covered"] is not None
    ]
    return {
        "samples": len(available),
        "uv_mae_ms": sum(error["uv_abs"] * weight for error, weight in zip(errors, weights)),
        "u_bias_ms": sum(error["du"] * weight for error, weight in zip(errors, weights)),
        "v_bias_ms": sum(error["dv"] * weight for error, weight in zip(errors, weights)),
        "vector_mae_ms": sum(math.hypot(error["du"], error["dv"]) * weight for error, weight in zip(errors, weights)),
        "speed_mae_ms": sum(error["speed_abs"] * weight for error, weight in zip(errors, weights)),
        "speed_bias_ms": sum(error["speed_bias"] * weight for error, weight in zip(errors, weights)),
        "direction_mae_deg": (
            sum(value * weight for value, weight in direction)
            / sum(weight for _, weight in direction)
            if direction
            else None
        ),
        "strong_wind_uv_mae_ms": (
            sum(error["uv_abs"] * weight for error, weight in strong)
            / sum(weight for _, weight in strong)
            if strong
            else None
        ),
        "uncertainty_90_coverage": (
            sum(float(value) * weight for value, weight in covered)
            / sum(weight for _, weight in covered)
            if covered
            else None
        ),
    }


def _bootstrap_improvement(
    records: list[dict],
    *,
    context_seed: str,
    policy: LiveWindVerificationPolicy,
) -> tuple[float | None, float | None]:
    by_block: dict[str, list[dict]] = {}
    for record in records:
        by_block.setdefault(record["block"], []).append(record)
    blocks = sorted(by_block)
    if len(blocks) < 2:
        return None, None
    seed = int(hashlib.sha256(context_seed.encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    improvements = []
    for _ in range(policy.bootstrap_iterations):
        sampled = [rng.choice(blocks) for _ in blocks]
        sample_records = [item for block in sampled for item in by_block[block]]
        raw = _metrics(sample_records, "raw_consensus", policy).get("uv_mae_ms")
        candidate = _metrics(sample_records, "multi_station_live_wind", policy).get("uv_mae_ms")
        if raw is not None and candidate is not None:
            improvements.append(raw - candidate)
    if not improvements:
        return None, None
    improvements.sort()
    alpha = (1.0 - policy.confidence_level) / 2.0
    low_index = max(0, min(len(improvements) - 1, int(alpha * len(improvements))))
    high_index = max(
        0,
        min(len(improvements) - 1, int((1.0 - alpha) * len(improvements)) - 1),
    )
    return improvements[low_index], improvements[high_index]


def _stratified(records: list[dict], variants: tuple[str, ...], policy) -> dict:
    result = {}
    for dimension in ("country", "terrain_class", "coastal_class", "season", "wind_sector",
                      "wind_strength", "station_density"):
        buckets = {}
        for value in sorted({record[dimension] for record in records}):
            subset = [record for record in records if record[dimension] == value]
            buckets[value] = {
                "status": ("sufficient" if len({row["block"] for row in subset}) >= policy.minimum_subgroup_blocks
                           else "insufficient_evidence"),
                "independent_weather_blocks": len({row["block"] for row in subset}),
                **{variant: _metrics(subset, variant, policy) for variant in variants},
            }
        result[dimension] = buckets
    return result


def evaluate_live_wind_holdouts(
    cases: list[LiveWindHoldoutCase] | tuple[LiveWindHoldoutCase, ...],
    *,
    candidate_version: str,
    training_window_end: datetime,
    candidate_builder: CandidateBuilder | None = None,
    policy: LiveWindVerificationPolicy = DEFAULT_LIVE_WIND_VERIFICATION_POLICY,
    run_id: uuid.UUID | None = None,
    evidence_metadata: dict | None = None,
) -> LiveWindVerificationResult:
    """Evaluate spatial LOSO cases in independent temporal blocks.

    This function never activates serving.  It only returns immutable evidence
    that can later be selected explicitly through deployment configuration.
    """
    if not candidate_version.strip():
        raise ValueError("candidate_version is required")
    training_end = _utc(training_window_end, "training_window_end")
    builder = candidate_builder or _default_candidate_builder
    embargo_end = training_end + timedelta(hours=policy.training_embargo_hours)
    ordered = sorted(cases, key=lambda case: (case.observed_at, case.case_id))
    records = []
    input_rows = []
    for case in ordered:
        observed_at = _utc(case.observed_at, "observed_at")
        if observed_at <= embargo_end:
            continue
        if not all(
            _finite(value)
            for value in (
                case.observed_u_ms,
                case.observed_v_ms,
                case.target_model.u_ms,
                case.target_model.v_ms,
            )
        ):
            continue
        held_out = _held_out_residuals(case)
        if any(
            residual.station_id == case.target_station_id
            or residual.observation_id == case.target_observation_id
            for residual in held_out
        ):
            raise AssertionError("target observation leaked into LiveWind holdout")
        prediction = case.candidate_prediction or builder(case, held_out)
        predictions = {
            "raw_consensus": HoldoutPrediction(
                case.target_model.u_ms, case.target_model.v_ms
            ),
            "multi_station_live_wind": prediction,
            **({"model_local_physics": case.local_physics_prediction}
               if case.local_physics_prediction is not None else {}),
            **{
                f"ablation:{name}": value
                for name, value in sorted(case.ablation_predictions.items())
            },
        }
        block_seconds = policy.holdout_block_hours * 3600
        block_index = int(observed_at.timestamp()) // block_seconds
        record = {
            "case_id": case.case_id,
            "station_id": case.target_station_id,
            "observed_at": observed_at,
            "block": str(block_index),
            "country": case.country or "unknown",
            "terrain_class": case.terrain_class or "unknown",
            "coastal_class": case.coastal_class or "unknown",
            "season": case.season or "unknown",
            "wind_sector": case.wind_sector or "unknown",
            "wind_strength": case.wind_strength,
            "station_density": case.station_density,
            "station_group": case.station_group or case.target_station_id,
            "fallback": case.fallback,
            "weather_regime": case.weather_regime,
            "conflict_case": case.conflict_case,
            "errors": {
                name: _prediction_error(case, value)
                for name, value in predictions.items()
            },
        }
        records.append(record)
        input_rows.append(
            {
                "case_id": case.case_id,
                "target_station_id": case.target_station_id,
                "target_observation_id": case.target_observation_id,
                "observed_at": observed_at.isoformat(),
                "held_out_residual_ids": sorted(item.residual_id for item in held_out),
                "case_input_hash": case.input_hash,
                "target_model": [case.target_model.u_ms, case.target_model.v_ms],
                "observed_vector": [case.observed_u_ms, case.observed_v_ms],
                "residual_vectors": sorted(
                    [item.residual_id, item.residual_u_ms, item.residual_v_ms]
                    for item in held_out
                ),
                "prediction_vectors": {
                    name: [value.u_ms, value.v_ms]
                    for name, value in sorted(predictions.items())
                },
            }
        )

    input_hash = hashlib.sha256(
        json.dumps(input_rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    fingerprint = candidate_policy_hash(
        candidate_version, policy.subgroup_policy_version,
        policy.maximum_subgroup_regression_ms)
    context_payload = {
        "candidate_version": candidate_version,
        "candidate_policy_hash": fingerprint,
        "training_window_end": training_end.isoformat(),
        "input_hash": input_hash,
        "policy": policy.snapshot(),
        "evidence_metadata": evidence_metadata or {},
    }
    context_hash = hashlib.sha256(
        json.dumps(context_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    variants = tuple(
        sorted({variant for record in records for variant in record["errors"]})
    )
    metrics = {variant: _metrics(records, variant, policy) for variant in variants}
    raw_mae = metrics.get("raw_consensus", {}).get("uv_mae_ms")
    candidate_mae = metrics.get("multi_station_live_wind", {}).get("uv_mae_ms")
    improvement = (
        raw_mae - candidate_mae
        if isinstance(raw_mae, (int, float)) and isinstance(candidate_mae, (int, float))
        else None
    )
    ci_lower, ci_upper = _bootstrap_improvement(
        records,
        context_seed=context_hash,
        policy=policy,
    )
    days = {record["observed_at"].date() for record in records}
    stations = {record["station_group"] for record in records}
    metrics["activation"] = {
        "uv_mae_drop_ms": improvement,
        "ci_lower_ms": ci_lower,
        "ci_upper_ms": ci_upper,
        "country_balanced": True,
        "temporal_block_hours": policy.holdout_block_hours,
        "independent_weather_blocks": len({record["block"] for record in records}),
        "fallback_rate": (sum(record["fallback"] for record in records) / len(records) if records else None),
        "wind_sector_count": len({record["wind_sector"] for record in records if record["wind_sector"] != "variable"}),
        "calm_cases": sum(record["wind_strength"] == "calm" for record in records),
        "strong_cases": sum(record["wind_strength"] == "strong" for record in records),
        "rapid_change_cases": sum(record["weather_regime"] == "rapid_change" for record in records),
        "conflict_cases": sum(record["conflict_case"] for record in records),
        "countries": len({record["country"] for record in records if record["country"] != "unknown"}),
        "terrain_classes": len({record["terrain_class"] for record in records if record["terrain_class"] != "unknown"}),
        "coastal_classes": len({record["coastal_class"] for record in records if record["coastal_class"] != "unknown"}),
    }
    reasons = []
    if len(records) < policy.minimum_samples:
        reasons.append("samples_low")
    if len(days) < policy.minimum_days:
        reasons.append("days_low")
    if len(stations) < policy.minimum_stations:
        reasons.append("stations_low")
    if metrics["activation"]["wind_sector_count"] < policy.minimum_wind_sectors:
        reasons.append("wind_sectors_low")
    if (metrics["activation"]["fallback_rate"] is None
            or metrics["activation"]["fallback_rate"] > policy.maximum_fallback_rate):
        reasons.append("fallback_rate_high")
    if (evidence_metadata or {}).get("baseline_source") == "exact-run-bundle-v2":
        coverage = metrics["activation"]
        for key, reason in (
            ("calm_cases", "calm_cases_missing"),
            ("strong_cases", "strong_cases_missing"),
            ("rapid_change_cases", "rapid_change_cases_missing"),
            ("conflict_cases", "conflict_cases_missing"),
        ):
            if not coverage[key]:
                reasons.append(reason)
        for key, reason in (
            ("countries", "country_coverage_low"),
            ("terrain_classes", "terrain_coverage_low"),
            ("coastal_classes", "coastal_coverage_low"),
        ):
            if coverage[key] < 2:
                reasons.append(reason)
    if improvement is None or improvement < policy.minimum_uv_mae_drop_ms:
        reasons.append("improvement_low")
    if ci_lower is None or ci_lower <= 0:
        reasons.append("confidence_interval_nonpositive")
    coverage_reasons = {"samples_low", "days_low", "stations_low", "wind_sectors_low",
                        "calm_cases_missing", "strong_cases_missing", "rapid_change_cases_missing",
                        "conflict_cases_missing", "country_coverage_low", "terrain_coverage_low",
                        "coastal_coverage_low"}
    status = "passed" if not reasons else "collecting" if any(
        reason in coverage_reasons for reason in reasons
    ) else "rejected"
    metrics["activation"]["gate_reasons"] = reasons
    reason = "passed" if not reasons else reasons[0]
    if records:
        window_start = min(record["observed_at"] for record in records)
        window_end = max(record["observed_at"] for record in records)
    else:
        window_start = embargo_end + timedelta(seconds=1)
        window_end = window_start
    return LiveWindVerificationResult(
        run_id=run_id or uuid.uuid4(),
        candidate_version=candidate_version,
        context_hash=context_hash,
        input_hash=input_hash,
        training_window_end=training_end,
        window_start=window_start,
        window_end=window_end,
        matched_samples=len(records),
        distinct_stations=len(stations),
        distinct_days=len(days),
        status=status,
        reason=reason,
        metrics=metrics,
        stratified_metrics=_stratified(records, variants, policy),
        policy={**policy.snapshot(), "candidate_policy_hash": fingerprint,
                **(evidence_metadata or {})},
    )


def persist_live_wind_verification_evidence(db, result: LiveWindVerificationResult) -> bool:
    """Insert evidence once; a repeated context is never updated in place."""
    values = result.evidence_values()
    inserted = db.scalar(
        insert(WeatherLiveWindVerificationEvidence)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_live_wind_verification_context")
        .returning(WeatherLiveWindVerificationEvidence.id)
    )
    return inserted is not None
