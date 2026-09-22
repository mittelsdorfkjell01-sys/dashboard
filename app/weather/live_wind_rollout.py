"""Fail-closed public rollout policy for station-adjusted LiveWind."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveWindRolloutDecision:
    expose_station_adjustment: bool
    reason: str


def region_key(spot) -> str:
    region = getattr(spot, "region", None)
    slug = getattr(region, "slug", None)
    return str(slug).casefold() if slug else "unassigned"


def rollout_decision(
    spot,
    *,
    settings: Settings | None = None,
) -> LiveWindRolloutDecision:
    """Decide whether public serving may calculate a station adjustment.

    Shadow and internal stages never alter a public response. Pilot/regional
    stages require an explicit region allowlist. The emergency flag dominates
    every stage, including global.
    """
    cfg = settings or get_settings()
    if cfg.live_wind_force_baseline:
        return LiveWindRolloutDecision(False, "force_baseline")
    stage = cfg.live_wind_rollout_stage
    if stage in {"shadow", "internal"}:
        return LiveWindRolloutDecision(False, f"rollout_{stage}")
    if stage == "global":
        return LiveWindRolloutDecision(True, "rollout_global")
    key = region_key(spot)
    if key in set(cfg.live_wind_enabled_region_slugs):
        return LiveWindRolloutDecision(True, f"rollout_{stage}_region")
    return LiveWindRolloutDecision(False, "region_not_enabled")


def quality_gate_reasons(
    payload: dict,
    *,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    """Return stable reasons that force an immediate model-baseline fallback."""
    cfg = settings or get_settings()
    if payload.get("status") != "station_adjusted":
        return ()
    reasons = []
    if int(payload.get("station_count") or 0) < cfg.live_wind_min_station_count:
        reasons.append("station_count_low")
    checks = (
        ("confidence", cfg.live_wind_min_confidence, "minimum", "confidence_low"),
        (
            "conflict_index",
            cfg.live_wind_max_conflict_index,
            "maximum",
            "conflict_high",
        ),
        (
            "uncertainty_ms",
            cfg.live_wind_max_uncertainty_ms,
            "maximum",
            "uncertainty_high",
        ),
    )
    for field, threshold, direction, reason in checks:
        value = payload.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            reasons.append(f"{field}_missing")
        elif direction == "minimum" and float(value) < threshold:
            reasons.append(reason)
        elif direction == "maximum" and float(value) > threshold:
            reasons.append(reason)
    u_ms = payload.get("correction_u_ms")
    v_ms = payload.get("correction_v_ms")
    if not all(
        isinstance(value, (int, float)) and math.isfinite(float(value))
        for value in (u_ms, v_ms)
    ):
        reasons.append("correction_vector_missing")
    elif math.hypot(float(u_ms), float(v_ms)) > cfg.live_wind_max_correction_ms:
        reasons.append("correction_high")
    return tuple(dict.fromkeys(reasons))


def operational_health_reasons(
    db,
    spot,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Automatic circuit breaker based on recent internal shadow evidence."""
    if not hasattr(db, "scalars"):
        return ()
    cfg = settings or get_settings()
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = instant - timedelta(minutes=cfg.live_wind_health_window_minutes)
    try:
        from sqlalchemy import select

        from app.models import WeatherLiveWindJob

        rows = list(
            db.scalars(
                select(WeatherLiveWindJob)
                .where(
                    WeatherLiveWindJob.region_key == region_key(spot),
                    WeatherLiveWindJob.created_at >= cutoff,
                )
                .order_by(WeatherLiveWindJob.created_at.desc())
            ).all()
        )
    except Exception:
        rollback = getattr(db, "rollback", None)
        if rollback is not None:
            rollback()
        return ("health_check_unavailable",)
    succeeded = [row for row in rows if row.status == "succeeded"]
    reasons = []
    if len(succeeded) < cfg.live_wind_health_min_analyses:
        reasons.append("health_evidence_low")
    else:
        latest = max(row.finished_at or row.created_at for row in succeeded)
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        if latest.astimezone(timezone.utc) < instant - timedelta(
            minutes=cfg.live_wind_job_late_minutes
        ):
            reasons.append("shadow_analysis_late")
        fallback_rate = sum(
            row.product_status in {"baseline", "unavailable"}
            for row in succeeded
        ) / len(succeeded)
        if fallback_rate > cfg.live_wind_readiness_max_fallback_rate:
            reasons.append("fallback_rate_high")
    if any(row.status == "failed" for row in rows):
        reasons.append("terminal_jobs_present")
    return tuple(dict.fromkeys(reasons))


def verification_evidence_reasons(
    db,
    *,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    """Fail closed unless the configured immutable holdout evidence passed."""
    cfg = settings or get_settings()
    if not cfg.live_wind_require_verification_evidence:
        return ()
    context_hash = (cfg.live_wind_verification_context_hash or "").strip()
    if not context_hash:
        return ("verification_context_missing",)
    if not hasattr(db, "scalar"):
        return ("verification_evidence_unavailable",)
    try:
        from sqlalchemy import select

        from app.models import WeatherLiveWindVerificationEvidence

        evidence = db.scalar(
            select(WeatherLiveWindVerificationEvidence)
            .where(
                WeatherLiveWindVerificationEvidence.candidate_version
                == cfg.live_wind_candidate_version,
                WeatherLiveWindVerificationEvidence.context_hash == context_hash,
                WeatherLiveWindVerificationEvidence.status == "passed",
            )
            .order_by(WeatherLiveWindVerificationEvidence.computed_at.desc())
            .limit(1)
        )
    except Exception:
        rollback = getattr(db, "rollback", None)
        if rollback is not None:
            rollback()
        return ("verification_evidence_unavailable",)
    if evidence is None:
        return ("verification_evidence_missing",)
    reasons = []
    if (evidence.policy or {}).get("baseline_source") != "exact-run-bundle-v2":
        reasons.append("legacy_capture_time_baseline")
    if (evidence.policy or {}).get("leakage_audit") != "passed" or not (
        evidence.policy or {}
    ).get("persisted_case_count"):
        reasons.append("leakage_audit_unproven")
    if (evidence.policy or {}).get("builder_version") != "live-wind-holdout-builder-v1" or not (
        evidence.policy or {}
    ).get("case_context_hashes"):
        reasons.append("holdout_case_provenance_unproven")
    if evidence.matched_samples < cfg.live_wind_verification_min_samples:
        reasons.append("verification_samples_low")
    if evidence.distinct_days < cfg.live_wind_verification_min_days:
        reasons.append("verification_days_low")
    if evidence.distinct_stations < cfg.live_wind_verification_min_stations:
        reasons.append("verification_stations_low")
    improvement = (
        (evidence.metrics or {}).get("activation", {}).get("uv_mae_drop_ms")
    )
    lower = (evidence.metrics or {}).get("activation", {}).get("ci_lower_ms")
    if not isinstance(improvement, (int, float)) or improvement < cfg.live_wind_verification_min_uv_mae_drop_ms:
        reasons.append("verification_improvement_low")
    if not isinstance(lower, (int, float)) or lower <= 0:
        reasons.append("verification_confidence_interval_nonpositive")
    subgroup_limit = cfg.live_wind_verification_max_subgroup_regression_ms
    subgroup_version = cfg.live_wind_verification_subgroup_policy_version
    if subgroup_limit is None or not subgroup_version:
        reasons.append("subgroup_regression_policy_missing")
    elif ((evidence.policy or {}).get("subgroup_policy_version") != subgroup_version
          or (evidence.policy or {}).get("maximum_subgroup_regression_ms") != subgroup_limit):
        reasons.append("subgroup_regression_policy_mismatch")
    else:
        from app.weather.live_wind_verification import candidate_policy_hash
        if (evidence.policy or {}).get("candidate_policy_hash") != candidate_policy_hash(
            cfg.live_wind_candidate_version, subgroup_version, subgroup_limit):
            reasons.append("subgroup_regression_policy_mismatch")
        for dimension, groups in (evidence.stratified_metrics or {}).items():
            if not isinstance(groups, dict):
                continue
            for label, values in groups.items():
                if not isinstance(values, dict):
                    continue
                if values.get("status") != "sufficient":
                    reasons.append("verification_subgroup_insufficient_evidence")
                    continue
                raw = (values.get("raw_consensus") or {}).get("uv_mae_ms")
                live = (values.get("multi_station_live_wind") or {}).get("uv_mae_ms")
                if isinstance(raw, (int, float)) and isinstance(live, (int, float)) and live - raw > subgroup_limit:
                    reasons.append("verification_subgroup_regression")
                    break
            if "verification_subgroup_regression" in reasons:
                break
    return tuple(dict.fromkeys(reasons))


def _baseline_with_reason(baseline: dict, prefix: str, reasons: tuple[str, ...]) -> dict:
    fallback = dict(baseline)
    fallback["fallback_reason"] = f"{prefix}:" + ",".join(reasons)
    return fallback


def public_live_wind(
    db,
    spot,
    baseline: dict,
    *,
    model_ids: list[str] | tuple[str, ...] = (),
    settings: Settings | None = None,
    cache=None,
    residual_context_id: str | None = None,
    input_generation: str | None = None,
) -> dict:
    """Return baseline or a quality-gated analysis for the public API.

    The shadow job calls the analysis engine directly and therefore remains
    independent from this serving gate.
    """
    cfg = settings or get_settings()
    decision = rollout_decision(spot, settings=cfg)
    if not decision.expose_station_adjustment:
        return baseline

    verification_reasons = verification_evidence_reasons(db, settings=cfg)
    if verification_reasons:
        return _baseline_with_reason(
            baseline,
            "verification_gate",
            verification_reasons,
        )

    health_reasons = (
        operational_health_reasons(db, spot, settings=cfg)
        if cfg.live_wind_require_operational_health
        else ()
    )
    if health_reasons:
        logger.warning(
            "live_wind_public_operational_fallback",
            extra={
                "weather_event": "live_wind_public_operational_fallback",
                "weather_spot_id": str(getattr(spot, "id", "unknown")),
                "weather_region": region_key(spot),
                "weather_reasons": list(health_reasons),
            },
        )
        return _baseline_with_reason(baseline, "operational_gate", health_reasons)

    from app.live.live_wind import analyze_live_wind_for_spot

    candidate = analyze_live_wind_for_spot(
        db,
        spot,
        baseline,
        model_ids=model_ids,
        cache=cache,
        residual_context_id=residual_context_id,
        input_generation=input_generation,
    )
    reasons = quality_gate_reasons(candidate, settings=cfg)
    if not reasons:
        return candidate
    logger.warning(
        "live_wind_public_quality_fallback",
        extra={
            "weather_event": "live_wind_public_quality_fallback",
            "weather_spot_id": str(getattr(spot, "id", "unknown")),
            "weather_region": region_key(spot),
            "weather_reasons": list(reasons),
        },
    )
    return _baseline_with_reason(baseline, "quality_gate", reasons)
