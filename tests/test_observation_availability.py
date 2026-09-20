from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.weather.observation_availability import (
    AVAILABILITY_UNPROVEN,
    CAPTURED_OPERATIONALLY,
    HISTORICAL_BACKFILL,
    classify_capture_origin,
    observation_freshness,
)


UTC = timezone.utc
OBSERVED = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


def observation(*, received_at, imported_at=None, origin=CAPTURED_OPERATIONALLY):
    return SimpleNamespace(
        observed_at=OBSERVED,
        received_at=received_at,
        imported_at=imported_at or received_at,
        availability_class=origin,
    )


def operational_origin(row, **patch):
    values = {
        "capture_mode": "operational",
        "capture_started_at": OBSERVED + timedelta(minutes=33),
        "collector_enrolled_at": OBSERVED - timedelta(days=1),
        "collector_previously_attempted": True,
    }
    values.update(patch)
    return classify_capture_origin(row, **values)


def test_operational_receipt_origin_is_independent_of_34_minute_latency():
    row = observation(received_at=OBSERVED + timedelta(minutes=34))

    assert operational_origin(row) == CAPTURED_OPERATIONALLY
    unavailable = observation_freshness(
        row,
        analysis_cutoff_at=OBSERVED + timedelta(minutes=30),
        role="live_analysis",
    )
    late = observation_freshness(
        row,
        analysis_cutoff_at=OBSERVED + timedelta(minutes=40),
        role="live_analysis",
    )

    assert unavailable.eligible is False
    assert "observation_not_available_at_cutoff" in unavailable.reasons
    assert late.eligible is False
    assert "observation_too_old_for_live_gate" in late.reasons
    assert late.receipt_latency_minutes == 34


def test_observation_can_arrive_on_time_then_age_out_at_later_cutoff():
    row = observation(received_at=OBSERVED + timedelta(minutes=15))

    decision = observation_freshness(
        row,
        analysis_cutoff_at=OBSERVED + timedelta(minutes=45),
        role="residual_source",
    )

    assert decision.eligible is False
    assert decision.age_minutes == 45
    assert decision.reasons == ("observation_too_old_for_live_gate",)


def test_first_bootstrap_payload_is_backfill_even_in_operational_job():
    row = observation(received_at=OBSERVED + timedelta(minutes=34))

    assert operational_origin(
        row, collector_previously_attempted=False
    ) == HISTORICAL_BACKFILL


def test_outage_catchup_keeps_real_late_receipt_and_operational_origin():
    row = observation(received_at=OBSERVED + timedelta(hours=2))

    assert operational_origin(
        row, capture_started_at=OBSERVED + timedelta(hours=2) - timedelta(seconds=5)
    ) == CAPTURED_OPERATIONALLY
    decision = observation_freshness(
        row,
        analysis_cutoff_at=OBSERVED + timedelta(hours=2),
        role="holdout_input",
    )
    assert decision.eligible is False
    assert decision.receipt_latency_minutes == 120


def test_missing_capture_proof_is_unproven():
    row = observation(received_at=OBSERVED + timedelta(minutes=5))

    assert operational_origin(row, capture_started_at=None) == AVAILABILITY_UNPROVEN
    assert operational_origin(row, collector_enrolled_at=None) == AVAILABILITY_UNPROVEN


def test_explicit_historical_mode_remains_backfill():
    row = observation(received_at=OBSERVED + timedelta(minutes=5))

    assert classify_capture_origin(
        row,
        capture_mode="historical_backfill",
        capture_started_at=None,
        collector_enrolled_at=None,
        collector_previously_attempted=False,
    ) == HISTORICAL_BACKFILL
