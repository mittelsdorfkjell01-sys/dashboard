"""Immutable capture origin and cutoff-relative observation freshness."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone


CAPTURED_OPERATIONALLY = "captured_operationally"
HISTORICAL_BACKFILL = "historical_backfill"
AVAILABILITY_UNPROVEN = "availability_unproven"
LIVE_FRESHNESS_POLICY_VERSION = "live-observation-freshness-v1"
LIVE_FRESHNESS_MAX_AGE_MINUTES = 30
_CLOCK_SKEW = timedelta(minutes=2)


def _utc(value: object) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def classify_capture_origin(
    observation,
    *,
    capture_mode: str,
    capture_started_at: datetime | None,
    collector_enrolled_at: datetime | None,
    collector_previously_attempted: bool,
) -> str:
    """Classify first receipt provenance without using receipt latency as origin."""
    if capture_mode == "historical_backfill":
        return HISTORICAL_BACKFILL
    if capture_mode != "operational":
        raise ValueError("unsupported_capture_mode")

    observed_at = _utc(getattr(observation, "observed_at", None))
    received_at = _utc(getattr(observation, "received_at", None))
    imported_at = _utc(getattr(observation, "imported_at", None))
    capture_started_at = _utc(capture_started_at)
    collector_enrolled_at = _utc(collector_enrolled_at)
    if None in (
        observed_at,
        received_at,
        imported_at,
        capture_started_at,
        collector_enrolled_at,
    ):
        return AVAILABILITY_UNPROVEN
    if received_at < capture_started_at - _CLOCK_SKEW:
        return AVAILABILITY_UNPROVEN
    if imported_at < capture_started_at - _CLOCK_SKEW:
        return AVAILABILITY_UNPROVEN
    # A first poll can contain a provider archive predating our collector. A
    # prior station import plus the immutable epoch enrollment is the minimum
    # proof that this station was already under continuous collection.
    if not collector_previously_attempted or observed_at < collector_enrolled_at:
        return HISTORICAL_BACKFILL
    return CAPTURED_OPERATIONALLY


@dataclass(frozen=True)
class ObservationFreshness:
    policy_version: str
    role: str
    analysis_cutoff_at: datetime
    max_age_minutes: int
    eligible: bool
    reasons: tuple[str, ...]
    age_minutes: float | None
    receipt_latency_minutes: float | None

    def payload(self) -> dict:
        return asdict(self)


def observation_freshness(
    observation,
    *,
    analysis_cutoff_at: datetime,
    role: str,
    max_age_minutes: int = LIVE_FRESHNESS_MAX_AGE_MINUTES,
) -> ObservationFreshness:
    """Evaluate whether an observation could be used at a specific cutoff."""
    cutoff = _utc(analysis_cutoff_at)
    if cutoff is None:
        raise ValueError("analysis_cutoff_at_utc_required")
    if role not in {"live_analysis", "residual_source", "holdout_input"}:
        raise ValueError("unsupported_observation_freshness_role")
    if max_age_minutes < 1:
        raise ValueError("positive_observation_max_age_required")

    reasons: list[str] = []
    if getattr(observation, "availability_class", None) != CAPTURED_OPERATIONALLY:
        reasons.append("capture_origin_not_operational")
    observed_at = _utc(getattr(observation, "observed_at", None))
    received_at = _utc(getattr(observation, "received_at", None))
    imported_at = _utc(getattr(observation, "imported_at", None))
    if observed_at is None:
        reasons.append("observed_at_unproven")
    if received_at is None:
        reasons.append("received_at_unproven")
    if imported_at is None:
        reasons.append("imported_at_unproven")
    if any(value is not None and value > cutoff for value in (observed_at, received_at, imported_at)):
        reasons.append("observation_not_available_at_cutoff")

    age_minutes = None
    if observed_at is not None:
        age_minutes = (cutoff - observed_at).total_seconds() / 60
        if age_minutes < -2:
            reasons.append("observation_after_cutoff")
        elif age_minutes > max_age_minutes:
            reasons.append("observation_too_old_for_live_gate")
    receipt_latency = None
    if observed_at is not None and received_at is not None:
        receipt_latency = (received_at - observed_at).total_seconds() / 60
        if receipt_latency < -2:
            reasons.append("receipt_before_observation")

    return ObservationFreshness(
        policy_version=LIVE_FRESHNESS_POLICY_VERSION,
        role=role,
        analysis_cutoff_at=cutoff,
        max_age_minutes=max_age_minutes,
        eligible=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        age_minutes=round(age_minutes, 3) if age_minutes is not None else None,
        receipt_latency_minutes=(
            round(receipt_latency, 3) if receipt_latency is not None else None
        ),
    )
