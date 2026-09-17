"""Robust regional LiveWind analysis from quality-checked station residuals.

The engine is deliberately pure: it never reads observations, mutates model
values, or applies local spot physics.  Its output is the regional background
that the serving layer may pass through local spot physics exactly once.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Literal

REGIONAL_LIVE_WIND_VERSION = "regional-live-wind-uv-v2"


@dataclass(frozen=True)
class RegionalAnalysisPolicy:
    version: str = REGIONAL_LIVE_WIND_VERSION
    max_residual_age_minutes: int = 60
    max_future_minutes: int = 2
    minimum_selection_weight: float = 1e-6
    minimum_air_mass_similarity: float = 0.35
    minimum_coastal_similarity: float = 0.25
    maximum_residual_ms: float = 30.0
    robust_scale_floor_ms: float = 0.75
    tukey_tuning_constant: float = 4.685
    uncertainty_reference_ms: float = 2.0
    correlated_group_share_cap: float = 0.55
    full_evidence_weight: float = 0.75
    full_effective_station_count: float = 2.0
    minimum_evidence_strength: float = 0.08
    minimum_applied_correction_ms: float = 0.05
    maximum_correction_ms: float = 6.0
    maximum_baseline_fraction: float = 0.60
    minimum_correction_limit_ms: float = 2.0
    model_uncertainty_floor_ms: float = 0.75
    station_age_uncertainty_ms: float = 0.8
    missing_geometry_uncertainty_ms: float = 0.6
    distance_uncertainty_per_100km_ms: float = 1.0
    single_group_uncertainty_ms: float = 0.75
    missing_profile_uncertainty_ms: float = 0.8
    terrain_uncertainty_ms: float = 1.2
    correction_uncertainty_fraction: float = 0.15

    def __post_init__(self) -> None:
        fractions = (
            self.minimum_selection_weight,
            self.minimum_air_mass_similarity,
            self.minimum_coastal_similarity,
            self.correlated_group_share_cap,
            self.minimum_evidence_strength,
            self.maximum_baseline_fraction,
        )
        if any(not 0 < value <= 1 for value in fractions):
            raise ValueError("regional analysis fractions must be in (0, 1]")
        if self.correlated_group_share_cap < 0.5:
            raise ValueError("correlation cap cannot allocate two independent groups")
        positives = (
            self.max_residual_age_minutes,
            self.max_future_minutes,
            self.maximum_residual_ms,
            self.robust_scale_floor_ms,
            self.tukey_tuning_constant,
            self.uncertainty_reference_ms,
            self.full_evidence_weight,
            self.full_effective_station_count,
            self.minimum_applied_correction_ms,
            self.maximum_correction_ms,
            self.minimum_correction_limit_ms,
            self.model_uncertainty_floor_ms,
            self.station_age_uncertainty_ms,
            self.missing_geometry_uncertainty_ms,
            self.distance_uncertainty_per_100km_ms,
            self.single_group_uncertainty_ms,
            self.missing_profile_uncertainty_ms,
            self.terrain_uncertainty_ms,
            self.correction_uncertainty_fraction,
        )
        if any(value <= 0 for value in positives):
            raise ValueError("regional analysis limits must be positive")

    def snapshot(self) -> dict:
        return asdict(self)


DEFAULT_REGIONAL_ANALYSIS_POLICY = RegionalAnalysisPolicy()


@dataclass(frozen=True)
class TargetModelState:
    u_ms: float
    v_ms: float
    valid_at: datetime
    model_version: str
    model_ids: tuple[str, ...]
    model_spread_ms: float
    air_mass_id: str | None = None
    terrain_complexity: float = 0.0
    profile_available: bool = True


@dataclass(frozen=True)
class StationResidualInput:
    residual_id: str
    analysis_id: str
    station_id: str
    observation_id: str
    provider: str
    observed_at: datetime
    residual_u_ms: float
    residual_v_ms: float
    selection_weight: float
    residual_uncertainty_ms: float
    qc_status: Literal["accepted", "degraded", "rejected", "unavailable"]
    correlation_group: str | None = None
    terrain_similarity: float = 0.5
    coastal_similarity: float = 0.5
    elevation_similarity: float = 0.5
    air_mass_similarity: float = 0.5
    station_air_mass_id: str | None = None
    mountain_barrier: bool = False
    model_compatible: bool = True
    distance_km: float | None = None


@dataclass(frozen=True)
class StationContribution:
    residual_id: str
    analysis_id: str
    station_id: str
    observation_id: str
    provider: str
    observed_at: datetime
    residual_u_ms: float
    residual_v_ms: float
    correlation_group: str
    base_weight: float
    robust_weight: float
    normalized_weight: float
    applied_weight: float
    contribution_u_ms: float
    contribution_v_ms: float
    residual_uncertainty_ms: float
    included: bool
    exclusion_reasons: tuple[str, ...]

    def payload(self) -> dict:
        result = asdict(self)
        result["observed_at"] = self.observed_at.isoformat()
        return result


@dataclass(frozen=True)
class RegionalLiveWindResult:
    analysis_version: str
    analyzed_at: datetime
    valid_at: datetime | None
    status: Literal["baseline", "station_adjusted", "unavailable"]
    model_version: str | None
    model_u_ms: float | None
    model_v_ms: float | None
    regional_u_ms: float | None
    regional_v_ms: float | None
    correction_u_ms: float
    correction_v_ms: float
    station_contributions: tuple[StationContribution, ...]
    conflict_index: float
    covariance_uu_ms2: float | None
    covariance_uv_ms2: float | None
    covariance_vv_ms2: float | None
    uncertainty_ms: float | None
    confidence: float | None
    evidence_strength: float
    effective_station_count: float
    fallback_reason: str | None
    configuration: dict
    uncertainty_components: dict[str, float]


def _finite(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _utc(value) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _continuous_gate(value: float, minimum: float) -> float:
    """Taper a relationship continuously from zero at its compatibility gate."""
    if value <= minimum:
        return 0.0
    if minimum >= 1.0:
        return 1.0
    return _clamp01((value - minimum) / (1.0 - minimum))


def _weighted_median(values: list[tuple[float, float]]) -> float:
    ordered = sorted(values, key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= total / 2.0:
            return value
    return ordered[-1][0]


def _geometric_median(
    points: list[tuple[float, float]], weights: list[float]
) -> tuple[float, float]:
    total = sum(weights)
    x = sum(point[0] * weight for point, weight in zip(points, weights)) / total
    y = sum(point[1] * weight for point, weight in zip(points, weights)) / total
    for _ in range(80):
        terms = []
        coincident = None
        for point, weight in zip(points, weights):
            distance = math.hypot(point[0] - x, point[1] - y)
            if distance < 1e-10:
                coincident = point
                continue
            terms.append((point, weight / distance))
        if not terms:
            return coincident or (x, y)
        denominator = sum(weight for _, weight in terms)
        new_x = sum(point[0] * weight for point, weight in terms) / denominator
        new_y = sum(point[1] * weight for point, weight in terms) / denominator
        if math.hypot(new_x - x, new_y - y) < 1e-9:
            return new_x, new_y
        x, y = new_x, new_y
    return x, y


def _group_capped_weights(
    raw_weights: list[float], groups: list[str], cap: float
) -> list[float]:
    """Normalize weights while limiting any correlated group when possible."""
    totals: dict[str, float] = {}
    members: dict[str, list[int]] = {}
    for index, (weight, group) in enumerate(zip(raw_weights, groups)):
        totals[group] = totals.get(group, 0.0) + max(0.0, weight)
        members.setdefault(group, []).append(index)
    active = [group for group, total in totals.items() if total > 0]
    if not active:
        return [0.0] * len(raw_weights)
    if len(active) == 1:
        total = totals[active[0]]
        return [max(0.0, weight) / total for weight in raw_weights]

    allocation: dict[str, float] = {}
    remaining = set(active)
    remaining_mass = 1.0
    while remaining:
        raw_total = sum(totals[group] for group in remaining)
        if raw_total <= 0:
            equal = remaining_mass / len(remaining)
            allocation.update({group: equal for group in remaining})
            break
        over = [
            group
            for group in remaining
            if remaining_mass * totals[group] / raw_total > cap
        ]
        if not over:
            allocation.update(
                {
                    group: remaining_mass * totals[group] / raw_total
                    for group in remaining
                }
            )
            break
        for group in sorted(over):
            allocation[group] = cap
            remaining.remove(group)
            remaining_mass -= cap

    normalized = [0.0] * len(raw_weights)
    for group, indices in members.items():
        group_total = totals[group]
        share = allocation.get(group, 0.0)
        if group_total > 0:
            for index in indices:
                normalized[index] = share * max(0.0, raw_weights[index]) / group_total
    return normalized


def _input_reasons(
    residual: StationResidualInput,
    target: TargetModelState,
    analyzed_at: datetime,
    policy: RegionalAnalysisPolicy,
) -> list[str]:
    reasons = []
    if residual.qc_status not in {"accepted", "degraded"}:
        reasons.append("residual_qc_rejected")
    observed_at = _utc(residual.observed_at)
    if observed_at is None:
        reasons.append("residual_time_invalid")
    else:
        age = analyzed_at - observed_at
        if age > timedelta(minutes=policy.max_residual_age_minutes):
            reasons.append("residual_stale")
        if age < -timedelta(minutes=policy.max_future_minutes):
            reasons.append("residual_future")
    u_ms = _finite(residual.residual_u_ms)
    v_ms = _finite(residual.residual_v_ms)
    if u_ms is None or v_ms is None or math.hypot(u_ms, v_ms) > policy.maximum_residual_ms:
        reasons.append("residual_vector_invalid")
    selection_weight = _finite(residual.selection_weight)
    if selection_weight is None or selection_weight < policy.minimum_selection_weight:
        reasons.append("station_weight_invalid")
    uncertainty = _finite(residual.residual_uncertainty_ms)
    if uncertainty is None or uncertainty <= 0:
        reasons.append("residual_uncertainty_invalid")
    if not residual.model_compatible:
        reasons.append("model_baseline_incompatible")
    if residual.mountain_barrier:
        reasons.append("mountain_barrier")
    if _finite(residual.terrain_similarity) is None:
        reasons.append("terrain_relationship_invalid")
    if _finite(residual.elevation_similarity) is None:
        reasons.append("elevation_relationship_invalid")
    if _finite(residual.coastal_similarity) is None or (
        residual.coastal_similarity < policy.minimum_coastal_similarity
    ):
        reasons.append("coastal_regime_mismatch")
    if _finite(residual.air_mass_similarity) is None or (
        residual.air_mass_similarity < policy.minimum_air_mass_similarity
    ):
        reasons.append("air_mass_mismatch")
    if (
        target.air_mass_id
        and residual.station_air_mass_id
        and target.air_mass_id != residual.station_air_mass_id
    ):
        reasons.append("air_mass_mismatch")
    return list(dict.fromkeys(reasons))


def _base_weight(
    residual: StationResidualInput,
    analyzed_at: datetime,
    policy: RegionalAnalysisPolicy,
) -> float:
    age_minutes = max(
        0.0,
        (analyzed_at - residual.observed_at.astimezone(timezone.utc)).total_seconds()
        / 60.0,
    )
    age_factor = math.exp(
        -math.log(2.0) * age_minutes / (policy.max_residual_age_minutes / 2.0)
    )
    relationship = (
        _clamp01(residual.terrain_similarity) ** 0.20
        * _continuous_gate(
            residual.coastal_similarity, policy.minimum_coastal_similarity
        )
        * _clamp01(residual.elevation_similarity) ** 0.20
        * _continuous_gate(
            residual.air_mass_similarity, policy.minimum_air_mass_similarity
        )
    )
    uncertainty_ratio = (
        residual.residual_uncertainty_ms / policy.uncertainty_reference_ms
    )
    uncertainty_factor = 1.0 / (1.0 + uncertainty_ratio * uncertainty_ratio)
    qc_factor = 1.0 if residual.qc_status == "accepted" else 0.70
    return (
        residual.selection_weight
        * age_factor
        * relationship
        * uncertainty_factor
        * qc_factor
    )


def _baseline_result(
    target: TargetModelState,
    analyzed_at: datetime,
    policy: RegionalAnalysisPolicy,
    *,
    contributions: tuple[StationContribution, ...] = (),
    conflict_index: float = 0.0,
    covariance: tuple[float, float, float] | None = None,
    uncertainty_ms: float | None = None,
    effective_station_count: float = 0.0,
    uncertainty_components: dict[str, float] | None = None,
    fallback_reason: str,
) -> RegionalLiveWindResult:
    spread = max(target.model_spread_ms, policy.model_uncertainty_floor_ms)
    variance = spread * spread / 2.0
    covariance_uu, covariance_uv, covariance_vv = covariance or (
        variance,
        0.0,
        variance,
    )
    missing_information = (
        policy.missing_profile_uncertainty_ms if not target.profile_available else 0.0
    )
    terrain = policy.terrain_uncertainty_ms * _clamp01(target.terrain_complexity)
    if covariance is None:
        extra_variance = (missing_information**2 + terrain**2) / 2.0
        covariance_uu += extra_variance
        covariance_vv += extra_variance
    uncertainty = (
        uncertainty_ms
        if uncertainty_ms is not None
        else math.sqrt(max(0.0, covariance_uu + covariance_vv))
    )
    return RegionalLiveWindResult(
        analysis_version=policy.version,
        analyzed_at=analyzed_at,
        valid_at=target.valid_at.astimezone(timezone.utc),
        status="baseline",
        model_version=target.model_version,
        model_u_ms=target.u_ms,
        model_v_ms=target.v_ms,
        regional_u_ms=target.u_ms,
        regional_v_ms=target.v_ms,
        correction_u_ms=0.0,
        correction_v_ms=0.0,
        station_contributions=contributions,
        conflict_index=conflict_index,
        covariance_uu_ms2=covariance_uu,
        covariance_uv_ms2=covariance_uv,
        covariance_vv_ms2=covariance_vv,
        uncertainty_ms=uncertainty,
        confidence=max(
            0.0,
            min(
                1.0,
                0.40
                * (1.0 - conflict_index)
                / (1.0 + target.model_spread_ms / 3.0),
            ),
        ),
        evidence_strength=0.0,
        effective_station_count=effective_station_count,
        fallback_reason=fallback_reason,
        configuration=policy.snapshot(),
        uncertainty_components=uncertainty_components or {
            "model_spread": spread,
            "measurement": 0.0,
            "station_age": 0.0,
            "station_geometry": 0.0,
            "representativeness": 0.0,
            "residual_scatter": 0.0,
            "terrain": terrain,
            "missing_information": missing_information,
            "correction_strength": 0.0,
        },
    )


def analyze_regional_live_wind(
    target: TargetModelState,
    residuals: list[StationResidualInput] | tuple[StationResidualInput, ...],
    *,
    analyzed_at: datetime,
    policy: RegionalAnalysisPolicy = DEFAULT_REGIONAL_ANALYSIS_POLICY,
) -> RegionalLiveWindResult:
    """Analyze a regional correction without touching model or observation rows."""
    analysis_time = _utc(analyzed_at)
    valid_at = _utc(target.valid_at)
    target_u = _finite(target.u_ms)
    target_v = _finite(target.v_ms)
    spread = _finite(target.model_spread_ms)
    if analysis_time is None:
        raise ValueError("analyzed_at must be timezone-aware")
    if (
        valid_at is None
        or target_u is None
        or target_v is None
        or math.hypot(target_u, target_v) > 75
        or spread is None
        or spread < 0
        or not target.model_version
    ):
        return RegionalLiveWindResult(
            analysis_version=policy.version,
            analyzed_at=analysis_time,
            valid_at=valid_at,
            status="unavailable",
            model_version=None,
            model_u_ms=None,
            model_v_ms=None,
            regional_u_ms=None,
            regional_v_ms=None,
            correction_u_ms=0.0,
            correction_v_ms=0.0,
            station_contributions=(),
            conflict_index=0.0,
            covariance_uu_ms2=None,
            covariance_uv_ms2=None,
            covariance_vv_ms2=None,
            uncertainty_ms=None,
            confidence=None,
            evidence_strength=0.0,
            effective_station_count=0.0,
            fallback_reason="model_baseline_unavailable",
            configuration=policy.snapshot(),
            uncertainty_components={},
        )

    canonical = sorted(residuals, key=_canonical_residual_key)
    states = []
    eligible = []
    seen_residuals: set[str] = set()
    seen_observations: set[tuple[str, str]] = set()
    for residual in canonical:
        reasons = _input_reasons(residual, target, analysis_time, policy)
        observation_key = (residual.station_id, residual.observation_id)
        if (
            residual.residual_id in seen_residuals
            or observation_key in seen_observations
        ):
            reasons.append("duplicate_residual_input")
        seen_residuals.add(residual.residual_id)
        seen_observations.add(observation_key)
        group = residual.correlation_group or f"station:{residual.station_id}"
        state = {
            "residual": residual,
            "group": group,
            "reasons": reasons,
            "base": 0.0,
            "robust": 0.0,
            "normalized": 0.0,
        }
        if not reasons:
            state["base"] = _base_weight(residual, analysis_time, policy)
            if state["base"] > 0:
                eligible.append(state)
            else:
                state["reasons"].append("station_relationship_weight_zero")
        states.append(state)

    if not eligible:
        contributions = tuple(_contribution(state, 0.0) for state in states)
        return _baseline_result(
            target,
            analysis_time,
            policy,
            contributions=contributions,
            fallback_reason="station_residuals_unavailable",
        )

    base_normalized = _group_capped_weights(
        [state["base"] for state in eligible],
        [state["group"] for state in eligible],
        policy.correlated_group_share_cap,
    )
    points = [
        (state["residual"].residual_u_ms, state["residual"].residual_v_ms)
        for state in eligible
    ]
    if len(points) < 3:
        # A spatial median of exactly two points can jump from one endpoint to
        # the other when their weights cross. The weighted vector mean is smooth
        # at that boundary; robust rejection becomes meaningful from n=3.
        center_u = sum(
            point[0] * weight for point, weight in zip(points, base_normalized)
        )
        center_v = sum(
            point[1] * weight for point, weight in zip(points, base_normalized)
        )
    else:
        center_u, center_v = _geometric_median(points, base_normalized)
    distances = [
        math.hypot(point[0] - center_u, point[1] - center_v) for point in points
    ]
    median_distance = _weighted_median(list(zip(distances, base_normalized)))
    robust_scale = max(
        policy.robust_scale_floor_ms,
        1.4826 * median_distance,
        target.model_spread_ms / 2.0,
    )
    cutoff = policy.tukey_tuning_constant * robust_scale
    robust_raw = []
    for state, base_weight, distance in zip(eligible, base_normalized, distances):
        ratio = distance / cutoff if cutoff else math.inf
        factor = (1.0 - ratio * ratio) ** 2 if ratio < 1.0 else 0.0
        state["robust"] = factor
        robust_raw.append(base_weight * factor)
        if factor == 0.0:
            state["reasons"].append("robust_outlier")

    normalized = _group_capped_weights(
        robust_raw,
        [state["group"] for state in eligible],
        policy.correlated_group_share_cap,
    )
    for state, weight in zip(eligible, normalized):
        state["normalized"] = weight
    used = [state for state in eligible if state["normalized"] > 0]
    if not used:
        contributions = tuple(_contribution(state, 0.0) for state in states)
        return _baseline_result(
            target,
            analysis_time,
            policy,
            contributions=contributions,
            fallback_reason="station_residual_evidence_insufficient",
        )

    correction_center_u = sum(
        state["residual"].residual_u_ms * state["normalized"] for state in used
    )
    correction_center_v = sum(
        state["residual"].residual_v_ms * state["normalized"] for state in used
    )
    effective_count = 1.0 / sum(
        state["normalized"] ** 2 for state in used
    )
    independent_groups = len({state["group"] for state in used})
    robust_rms = math.sqrt(
        sum(
            state["normalized"]
            * (
                (state["residual"].residual_u_ms - correction_center_u) ** 2
                + (state["residual"].residual_v_ms - correction_center_v) ** 2
            )
            for state in used
        )
    )
    outlier_mass = sum(
        base_normalized[index]
        for index, state in enumerate(eligible)
        if state["robust"] == 0.0
    )
    conflict_scale = max(1.0, target.model_spread_ms)
    conflict = _clamp01(
        max(outlier_mass, robust_rms / (robust_rms + conflict_scale))
    )
    quality_strength = min(
        1.0, sum(state["base"] for state in eligible) / policy.full_evidence_weight
    )
    count_strength = min(
        1.0, effective_count / policy.full_effective_station_count
    )
    group_strength = 0.75 if independent_groups == 1 else 1.0
    evidence_strength = _clamp01(
        quality_strength
        * count_strength
        * group_strength
        * (1.0 - 0.20 * conflict)
    )

    raw_correction_u = correction_center_u * evidence_strength
    raw_correction_v = correction_center_v * evidence_strength
    raw_magnitude = math.hypot(raw_correction_u, raw_correction_v)
    baseline_speed = math.hypot(target.u_ms, target.v_ms)
    correction_limit = min(
        policy.maximum_correction_ms,
        max(
            policy.minimum_correction_limit_ms,
            baseline_speed * policy.maximum_baseline_fraction,
        ),
    )
    limit_scale = (
        correction_limit * math.tanh(raw_magnitude / correction_limit) / raw_magnitude
        if raw_magnitude > 0
        else 0.0
    )
    correction_u = raw_correction_u * limit_scale
    correction_v = raw_correction_v * limit_scale
    applied_magnitude = math.hypot(correction_u, correction_v)
    applied_scale = (
        applied_magnitude / math.hypot(correction_center_u, correction_center_v)
        if math.hypot(correction_center_u, correction_center_v) > 0
        else 0.0
    )

    scatter_uu = sum(
        state["normalized"]
        * (state["residual"].residual_u_ms - correction_center_u) ** 2
        for state in used
    )
    scatter_uv = sum(
        state["normalized"]
        * (state["residual"].residual_u_ms - correction_center_u)
        * (state["residual"].residual_v_ms - correction_center_v)
        for state in used
    )
    scatter_vv = sum(
        state["normalized"]
        * (state["residual"].residual_v_ms - correction_center_v) ** 2
        for state in used
    )
    input_variance = sum(
        state["normalized"] ** 2
        * state["residual"].residual_uncertainty_ms**2
        for state in used
    )
    model_variance = max(
        target.model_spread_ms, policy.model_uncertainty_floor_ms
    ) ** 2 / 2.0
    weighted_age_ratio = sum(
        state["normalized"]
        * min(
            1.0,
            max(
                0.0,
                (analysis_time - state["residual"].observed_at.astimezone(timezone.utc)).total_seconds()
                / (policy.max_residual_age_minutes * 60.0),
            ),
        )
        for state in used
    )
    station_age_uncertainty = policy.station_age_uncertainty_ms * weighted_age_ratio
    known_distances = [
        (state["normalized"], state["residual"].distance_km)
        for state in used
        if _finite(state["residual"].distance_km) is not None
        and float(state["residual"].distance_km) >= 0
    ]
    known_distance_weight = sum(weight for weight, _ in known_distances)
    if known_distance_weight > 0:
        weighted_distance = sum(
            weight * float(distance) for weight, distance in known_distances
        ) / known_distance_weight
        distance_uncertainty = min(
            2.5,
            weighted_distance / 100.0 * policy.distance_uncertainty_per_100km_ms,
        )
    else:
        distance_uncertainty = policy.missing_geometry_uncertainty_ms
    geometry_uncertainty = math.hypot(
        distance_uncertainty,
        policy.single_group_uncertainty_ms if independent_groups < 2 else 0.0,
    )
    terrain_uncertainty = (
        policy.terrain_uncertainty_ms * _clamp01(target.terrain_complexity)
    )
    missing_information_uncertainty = (
        policy.missing_profile_uncertainty_ms if not target.profile_available else 0.0
    )
    correction_uncertainty = applied_magnitude * policy.correction_uncertainty_fraction
    supplemental_variance = (
        station_age_uncertainty**2
        + geometry_uncertainty**2
        + terrain_uncertainty**2
        + missing_information_uncertainty**2
        + correction_uncertainty**2
    ) / 2.0
    covariance_uu = (
        model_variance + input_variance + scatter_uu / effective_count + supplemental_variance
    )
    covariance_uv = scatter_uv / effective_count
    covariance_vv = (
        model_variance + input_variance + scatter_vv / effective_count + supplemental_variance
    )
    uncertainty = math.sqrt(max(0.0, covariance_uu + covariance_vv))
    uncertainty_components = {
        "model_spread": max(target.model_spread_ms, policy.model_uncertainty_floor_ms),
        "measurement": math.sqrt(max(0.0, input_variance)),
        "station_age": station_age_uncertainty,
        "station_geometry": geometry_uncertainty,
        "representativeness": math.sqrt(max(0.0, input_variance)),
        "residual_scatter": math.sqrt(max(0.0, scatter_uu + scatter_vv)),
        "terrain": terrain_uncertainty,
        "missing_information": missing_information_uncertainty,
        "correction_strength": correction_uncertainty,
    }

    if (
        evidence_strength < policy.minimum_evidence_strength
        or applied_magnitude < policy.minimum_applied_correction_ms
    ):
        contributions = tuple(_contribution(state, 0.0) for state in states)
        return _baseline_result(
            target,
            analysis_time,
            policy,
            contributions=contributions,
            conflict_index=conflict,
            covariance=(covariance_uu, covariance_uv, covariance_vv),
            uncertainty_ms=uncertainty,
            effective_station_count=effective_count,
            uncertainty_components=uncertainty_components,
            fallback_reason=(
                "station_residual_conflict"
                if conflict >= 0.5
                else "station_residual_evidence_insufficient"
            ),
        )

    contributions = tuple(
        _contribution(state, applied_scale) for state in states
    )
    confidence = _clamp01(
        evidence_strength / (1.0 + uncertainty / (3.0 + target.model_spread_ms))
    )
    return RegionalLiveWindResult(
        analysis_version=policy.version,
        analyzed_at=analysis_time,
        valid_at=valid_at,
        status="station_adjusted",
        model_version=target.model_version,
        model_u_ms=target.u_ms,
        model_v_ms=target.v_ms,
        regional_u_ms=target.u_ms + correction_u,
        regional_v_ms=target.v_ms + correction_v,
        correction_u_ms=correction_u,
        correction_v_ms=correction_v,
        station_contributions=contributions,
        conflict_index=conflict,
        covariance_uu_ms2=covariance_uu,
        covariance_uv_ms2=covariance_uv,
        covariance_vv_ms2=covariance_vv,
        uncertainty_ms=uncertainty,
        confidence=confidence,
        evidence_strength=evidence_strength,
        effective_station_count=effective_count,
        fallback_reason=None,
        configuration=policy.snapshot(),
        uncertainty_components=uncertainty_components,
    )


def _contribution(state: dict, applied_scale: float) -> StationContribution:
    residual = state["residual"]
    normalized = float(state["normalized"])
    included = normalized > 0 and applied_scale > 0 and not state["reasons"]
    applied_weight = normalized * applied_scale if included else 0.0
    return StationContribution(
        residual_id=residual.residual_id,
        analysis_id=residual.analysis_id,
        station_id=residual.station_id,
        observation_id=residual.observation_id,
        provider=residual.provider,
        observed_at=residual.observed_at.astimezone(timezone.utc),
        residual_u_ms=residual.residual_u_ms,
        residual_v_ms=residual.residual_v_ms,
        correlation_group=state["group"],
        base_weight=float(state["base"]),
        robust_weight=float(state["robust"]),
        normalized_weight=normalized,
        applied_weight=applied_weight,
        contribution_u_ms=residual.residual_u_ms * applied_weight,
        contribution_v_ms=residual.residual_v_ms * applied_weight,
        residual_uncertainty_ms=residual.residual_uncertainty_ms,
        included=included,
        exclusion_reasons=tuple(dict.fromkeys(state["reasons"])),
    )


def _canonical_residual_key(residual: StationResidualInput) -> tuple:
    """Total ordering also resolves malformed duplicate identifiers deterministically."""
    observed = _utc(residual.observed_at)
    return (
        residual.station_id,
        residual.observation_id,
        residual.analysis_id,
        residual.residual_id,
        observed.isoformat() if observed else repr(residual.observed_at),
        repr(residual.residual_u_ms),
        repr(residual.residual_v_ms),
        residual.provider,
    )
