"""Fail-closed gates for forecast-dependent product capabilities.

These gates are intentionally separate from data collection and model-serving
health. A completed workflow, fresh snapshot or campaign alone never proves
forecast accuracy. Only a reviewed, reproducible artefact in the exact product
scope can authorize a capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import uuid

from sqlalchemy import select

from app.models import DecisionSupportGate
from app.weather.europe_campaign import load_campaign

POLICY_VERSION = "decision-support-v1"


@dataclass(frozen=True)
class GatePolicy:
    minimum_observations: int | None = None
    minimum_days: int | None = None
    minimum_coverage: float | None = None
    minimum_quality: float | None = None
    minimum_mae_improvement: float | None = None
    maximum_monitor_age: timedelta | None = None
    approval_reference: str | None = None


# No reviewed product-acceptance policy currently authorises forecast-based
# ranking for wind, wave or tide. Existing LiveWind/sector thresholds validate
# different products and must not be repurposed here. Keeping these policies
# deliberately unapproved means evidence can be collected and inspected, but
# cannot silently unlock a user-facing decision feature.
POLICIES = {kind: GatePolicy() for kind in ("wind", "wave", "tide")}

CAPABILITIES: dict[str, tuple[str, ...]] = {
    "forecast_sorting": ("wind",),
    "weather_alerts": ("wind", "wave"),
    "trip_weather_suggestions": ("wind", "wave", "tide"),
    "automatic_trip_alternative": ("wind", "wave", "tide"),
}


def required_data_kinds(capability: str, sport: str) -> tuple[str, ...]:
    if capability == "forecast_sorting" and sport in {"surf", "all"}:
        return ("wind", "wave")
    return CAPABILITIES[capability]


def evaluate_evidence(row: DecisionSupportGate, *, now: datetime | None = None) -> list[str]:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = POLICIES[row.data_kind]
    blockers: list[str] = []
    if policy.approval_reference is None: blockers.append("acceptance_policy_not_approved")
    if row.status != "accepted": blockers.append("evidence_not_accepted")
    if row.policy_version != POLICY_VERSION: blockers.append("policy_version_mismatch")
    if row.reviewed_at is None or not row.reviewed_by: blockers.append("independent_review_missing")
    if policy.minimum_observations is not None and row.observation_count < policy.minimum_observations: blockers.append("observations_below_minimum")
    if policy.minimum_days is not None and row.distinct_days < policy.minimum_days: blockers.append("distinct_days_below_minimum")
    if policy.minimum_coverage is not None and row.coverage_ratio < policy.minimum_coverage: blockers.append("coverage_below_minimum")
    if policy.minimum_quality is not None and row.quality_ratio < policy.minimum_quality: blockers.append("observation_quality_below_minimum")
    monitor_age = instant - row.monitor_fresh_at
    if monitor_age < -timedelta(minutes=5): blockers.append("monitor_clock_skew_future")
    elif policy.maximum_monitor_age is not None and monitor_age > policy.maximum_monitor_age: blockers.append("monitor_stale")
    metrics = row.metrics or {}
    required = {"baseline_mae", "candidate_mae", "mae_improvement", "calibrated", "acceptance_passed"}
    if not required <= set(metrics):
        blockers.append("required_metrics_missing")
    else:
        if metrics.get("calibrated") is not True: blockers.append("calibration_not_passed")
        if metrics.get("acceptance_passed") is not True: blockers.append("offline_acceptance_failed")
        try:
            improvement = float(metrics.get("mae_improvement") or 0)
            candidate_mae = float(metrics["candidate_mae"])
            baseline_mae = float(metrics["baseline_mae"])
        except (TypeError, ValueError):
            blockers.append("metrics_invalid")
        else:
            if policy.minimum_mae_improvement is not None and improvement < policy.minimum_mae_improvement:
                blockers.append("improvement_below_minimum")
            if candidate_mae >= baseline_mae:
                blockers.append("candidate_not_better_than_baseline")
    if row.dataset_end < row.dataset_start: blockers.append("dataset_period_invalid")
    if not row.artifact_uri or not re.fullmatch(r"[0-9a-f]{64}", row.artifact_sha256 or ""):
        blockers.append("reproducible_artifact_missing")
    if row.data_kind == "wind" and load_campaign().phase(instant) != "ended":
        blockers.append("wind_measurement_campaign_not_ended")
    return blockers


def capability_status(
    db,
    capability: str,
    *,
    sport: str,
    region_id: uuid.UUID | None,
    horizon_bucket: str,
    now: datetime | None = None,
) -> dict:
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown forecast capability: {capability}")
    required = required_data_kinds(capability, sport)
    kinds: dict[str, dict] = {}
    evidence_ids: list[str] = []
    for kind in required:
        row = db.scalar(
            select(DecisionSupportGate)
            .where(
                DecisionSupportGate.data_kind == kind,
                DecisionSupportGate.sport == sport,
                DecisionSupportGate.region_id == region_id,
                DecisionSupportGate.horizon_bucket == horizon_bucket,
            )
            .order_by(DecisionSupportGate.created_at.desc())
            .limit(1)
        )
        blockers = ["scope_evidence_missing"] if row is None else evaluate_evidence(row, now=now)
        kinds[kind] = {"ready": not blockers, "blockers": blockers, "evidence_id": str(row.id) if row else None}
        if row and not blockers: evidence_ids.append(str(row.id))
    return {
        "capability": capability,
        "ready": all(item["ready"] for item in kinds.values()),
        "requires_user_confirmation": capability == "automatic_trip_alternative",
        "policy_version": POLICY_VERSION,
        "evidence_ids": evidence_ids,
        "data_kinds": kinds,
        "fallback": "descriptive_forecast_and_manual_selection",
    }
