"""Versioned, conservative station-observation quality decisions."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import math

QC_VERSION = "station-observation-qc-v1"
GOOD_PROVIDER_FLAGS = {None, "0", "1", "2", "3", "good", "accepted"}
GOVERNANCE_REASONS = {
    "identity_unreviewed", "dependency_group_unreviewed",
    "station_inactive_or_blocked", "representativeness_unreviewed",
    "measurement_height_unknown", "station_elevation_unknown",
    "license_unverified",
}


@dataclass(frozen=True)
class QualityDecision:
    stage: str
    reasons: tuple[str, ...]
    version: str = QC_VERSION


def evaluate_observation(row, station, *, prior=(), now: datetime | None = None) -> QualityDecision:
    """Never edits raw values; eligibility requires explicit scoped approval."""
    reasons = list(row.data_issues)
    if row.import_status != "accepted":
        return QualityDecision("rejected", tuple(dict.fromkeys((*reasons, row.rejection_reason or "import_rejected"))))
    if row.wind_speed_ms is None or row.wind_u_ms is None or row.wind_v_ms is None:
        reasons.append("vector_missing")
    if row.wind_speed_ms and row.wind_direction_deg is None:
        reasons.append("direction_missing")
    if row.provider_quality not in GOOD_PROVIDER_FLAGS:
        reasons.append("provider_quality_untrusted")
    if row.received_at is None:
        reasons.append("received_at_unproven")
    if row.averaging_period_seconds is None:
        reasons.append("averaging_period_unknown")
    if row.measurement_period_seconds is None:
        reasons.append("measurement_period_unknown")
    if getattr(station, "elevation_m", None) is None:
        reasons.append("station_elevation_unknown")
    if getattr(station, "measurement_height_m", None) is None:
        reasons.append("measurement_height_unknown")
    if getattr(station, "license", None) not in {"CC BY 4.0"}:
        reasons.append("license_unverified")
    if getattr(station, "identity_review_status", "unreviewed") != "passed":
        reasons.append("identity_unreviewed")
    if not getattr(station, "physical_station_group", None) or not getattr(station, "correlation_group", None):
        reasons.append("dependency_group_unreviewed")
    if not getattr(station, "active", False) or getattr(station, "blocked", False):
        reasons.append("station_inactive_or_blocked")
    if getattr(station, "representativeness_status", "unreviewed") != "passed":
        reasons.append("representativeness_unreviewed")
    previous = [item for item in prior if item.wind_u_ms is not None and item.wind_v_ms is not None]
    if previous and row.wind_u_ms is not None and row.wind_v_ms is not None:
        latest = max(previous, key=lambda item: item.observed_at)
        if row.observed_at and row.observed_at - latest.observed_at <= timedelta(minutes=15):
            if math.hypot(row.wind_u_ms - latest.wind_u_ms, row.wind_v_ms - latest.wind_v_ms) > 30:
                reasons.append("wind_jump")
        if len(previous) >= 3:
            recent = sorted(previous, key=lambda item: item.observed_at)[-3:]
            if (row.observed_at and row.observed_at - recent[0].observed_at >= timedelta(minutes=30)
                    and all(math.hypot(item.wind_u_ms - row.wind_u_ms, item.wind_v_ms - row.wind_v_ms) < 0.05 for item in recent)):
                reasons.append("sensor_stuck")
    reasons = tuple(dict.fromkeys(reasons))
    critical = {"vector_missing", "direction_missing", "provider_quality_untrusted", "received_at_unproven", "wind_jump", "sensor_stuck"}
    if any(reason in critical for reason in reasons):
        return QualityDecision("accepted_for_storage", reasons)
    if not getattr(station, "monitoring_approved", False):
        return QualityDecision("accepted_for_storage", reasons)
    if reasons or not getattr(station, "residual_approved", False):
        return QualityDecision("accepted_for_monitoring", reasons)
    if not getattr(station, "holdout_target_approved", False) or not getattr(station, "holdout_input_approved", False):
        return QualityDecision("eligible_for_residuals", reasons)
    return QualityDecision("eligible_for_holdout", reasons)
