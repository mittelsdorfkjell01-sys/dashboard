"""Fail-closed station-epoch, time, dossier and manual approval regressions."""

from datetime import datetime, timedelta, timezone
import uuid

from geoalchemy2 import WKTElement
import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.auth.service import create_user
from app.models import (
    Region, Spot, WeatherObservation, WeatherObservationRevision, WeatherStation,
    WeatherStationApprovalAudit, WeatherStationDossier, WeatherStationEpoch,
    WeatherStationGroupDecision,
)
from app.weather.observation_worker import persist_batch
from app.weather.providers.common import normalize_observation
from app.weather.station_approval import approval_reasons, decide_station_scope, scope_valid
from app.weather.station_epochs import configuration_from_station, ensure_epoch
from app.weather.station_qualification import (
    QualificationPolicy, decide_group, persist_dossier, review_epoch,
    propose_group_candidates, temporal_quality,
)


def _station(db):
    suffix = uuid.uuid4().hex[:10]
    region = Region(slug=f"qual-{suffix}", name=f"Qualification {suffix}", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"qual-{suffix}", name=f"Qualification Spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(10 54)", srid=4326), status="published",
                sports=["wind"], water_type=["sea"])
    db.add(spot)
    db.flush()
    station = WeatherStation(
        spot_id=spot.id, provider="dwd", provider_station_id=f"qual-{suffix}",
        latitude=54, longitude=10, elevation_m=5, measurement_height_m=10,
        license="CC BY 4.0", active=True,
        provenance={"typical_interval_minutes": 10, "attribution_required": True},
    )
    db.add(station)
    db.flush()
    ensure_epoch(db, station, configuration_from_station(station),
                 first_seen_at=datetime.now(timezone.utc))
    db.commit()
    return station


def _row(station, observed, received, *, speed=8):
    return normalize_observation(
        provider="dwd", station_id=station.provider_station_id,
        observed_at=observed, received_at=received, imported_at=received,
        wind_speed_ms=speed, wind_direction_deg=270, provider_quality="good",
        latitude=54, longitude=10, measurement_height_m=10,
        license="CC BY 4.0", provenance={"fixture": True},
        measurement_period_seconds=600, averaging_period_seconds=600,
        raw_payload={"speed": speed, "observed": observed.isoformat()},
    )


def test_epoch_change_blocks_old_scope_and_preserves_raw_history(db):
    station = _station(db)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    first_epoch = station.current_epoch_id
    row = _row(station, now - timedelta(minutes=10), now)
    assert persist_batch(db, station, [row], dry_run=False)["persisted"] == 1
    old = db.scalar(select(WeatherObservation).where(WeatherObservation.station_id == station.id))
    assert old.epoch_id == first_epoch
    assert old.availability_class == "captured_operationally"
    changed = {**configuration_from_station(station), "measurement_height_m": 15}
    _, created = ensure_epoch(db, station, changed, first_seen_at=now + timedelta(minutes=1))
    db.commit()
    assert created and station.current_epoch_id != first_epoch
    assert station.blocked and not station.residual_approved
    assert db.get(WeatherStationEpoch, first_epoch).status == "superseded"
    assert db.get(WeatherObservation, old.id).epoch_id == first_epoch
    assert not scope_valid(db, station, old, scope="residual_source", analyzed_at=now + timedelta(hours=1))


def test_operational_backfill_and_first_receipt_are_separate(db):
    station = _station(db)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    observed = now - timedelta(minutes=10)
    fresh = _row(station, observed, now)
    assert persist_batch(db, station, [fresh], dry_run=False)["persisted"] == 1
    assert persist_batch(db, station, [fresh], dry_run=False)["persisted"] == 0
    stored = db.scalar(select(WeatherObservation).where(WeatherObservation.station_id == station.id))
    assert stored.received_at == now and stored.first_seen_at == now
    assert stored.availability_class == "captured_operationally"
    corrected = _row(station, observed, now + timedelta(minutes=2), speed=9)
    assert persist_batch(db, station, [corrected], dry_run=False)["revisions_persisted"] == 1
    db.refresh(stored)
    assert stored.received_at == now and stored.wind_speed_ms == 8
    revisions = db.scalars(select(WeatherObservationRevision).where(
        WeatherObservationRevision.station_id == station.id)).all()
    assert len(revisions) == 2
    assert {item.revision_status for item in revisions} == {"current", "pending_review"}
    backfill = _row(station, observed - timedelta(hours=2), now)
    persist_batch(db, station, [backfill], dry_run=False, capture_mode="historical_backfill")
    historical = db.scalar(select(WeatherObservation).where(
        WeatherObservation.station_id == station.id,
        WeatherObservation.observed_at == observed - timedelta(hours=2)))
    assert historical.availability_class == "historical_backfill"
    assert historical.received_at == now


def test_statistics_dossier_hash_and_missing_policy(db):
    station = _station(db)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    times = [end - timedelta(minutes=value) for value in (30, 20, 10)]
    for minute, observed in enumerate(times):
        received = observed + timedelta(minutes=(2, 4, 6)[minute])
        persist_batch(db, station, [_row(station, observed, received)], dry_run=False)
    historical = _row(station, end - timedelta(hours=2), end)
    persist_batch(db, station, [historical], dry_run=False, capture_mode="historical_backfill")
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id)
    stats = temporal_quality(db, epoch, end=end, window_days=1)
    assert stats["operational"]["received"] == 3
    assert stats["historical"]["received"] == 1
    assert stats["operational"]["latency_minutes"]["p50"] == 4
    assert stats["operational"]["latency_minutes"]["p90"] == pytest.approx(5.6)
    assert stats["operational"]["longest_interior_gap_minutes"] == 10
    assert stats["operational"]["longest_gap_minutes"] > 1000
    assert stats["operational"]["qc_acceptance_share"] is not None
    assert "identity_unreviewed" in stats["operational"]["governance_reasons"]
    assert "identity_unreviewed" not in stats["operational"]["intrinsic_qc_reasons"]
    first, first_hash = persist_dossier(db, station, end=end, window_days=1, dry_run=False)
    second, second_hash = persist_dossier(db, station, end=end, window_days=1, dry_run=False)
    assert first_hash == second_hash and first == second
    assert db.scalar(select(WeatherStationDossier).where(
        WeatherStationDossier.dossier_hash == first_hash)) is not None
    assert db.scalars(select(WeatherStationApprovalAudit).where(
        WeatherStationApprovalAudit.station_id == station.id)).all() == []
    assert "qualification_policy_unconfigured" in approval_reasons(db, station, scope="monitoring")
    changed = {**configuration_from_station(station), "sensor_metadata": {"sensor_instance_id": "replacement"}}
    ensure_epoch(db, station, changed, first_seen_at=end + timedelta(minutes=1))
    db.commit()
    _, changed_hash = persist_dossier(db, station, end=end, window_days=1)
    assert changed_hash != first_hash


def test_manual_epoch_group_scope_and_revocation(db):
    station = _station(db)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    user = create_user(db, email=f"qual-{uuid.uuid4().hex[:8]}@example.test",
                       password="Test-admin-password-123!", role="admin")
    observed = now - timedelta(minutes=10)
    persist_batch(db, station, [_row(station, observed, now)], dry_run=False)
    with pytest.raises(ValueError, match="authenticated_admin_reviewer_required"):
        decide_group(db, station, group_type="physical", group_key="physical-a",
                     status="confirmed", reviewer=None, reason="reviewed", evidence={"source": "fixture"})
    for kind in ("physical", "correlation"):
        decide_group(db, station, group_type=kind, group_key=f"{kind}-a",
                     status="confirmed", reviewer=user, reason="reviewed",
                     evidence={"source": "fixture", "period_end": observed.isoformat()})
    review_epoch(db, station, reviewer=user, reason="configuration checked")
    db.commit()
    payload, dossier_hash = persist_dossier(db, station, end=now, window_days=1, dry_run=False)
    assert payload["decision"]["ready_for_review"]
    with pytest.raises(ValueError, match="qualification_policy_unconfigured"):
        decide_station_scope(db, station, scope="monitoring", approved=True,
                             actor=user.email, reason="reviewed", reviewer=user,
                             expected_dossier_hash=dossier_hash)
    policy = QualificationPolicy(version="fixture-explicit-v1", min_operational_days=0,
                                 min_completeness=0, max_latency_p95_minutes=60,
                                 max_outage_share=1, max_qc_exclusion_share=1,
                                 allow_unknown_measurement_height=False)
    decide_station_scope(db, station, scope="monitoring", approved=True,
                         actor=user.email, reason="reviewed", reviewer=user,
                         policy=policy, expected_dossier_hash=dossier_hash)
    decide_station_scope(db, station, scope="residual_source", approved=True,
                         actor=user.email, reason="reviewed", reviewer=user,
                         policy=policy, expected_dossier_hash=dossier_hash)
    db.commit()
    old = db.scalar(select(WeatherObservation).where(WeatherObservation.station_id == station.id))
    assert not scope_valid(db, station, old, scope="residual_source", analyzed_at=now + timedelta(minutes=1))
    future = WeatherObservation(station_id=station.id, epoch_id=station.current_epoch_id,
                                availability_class="captured_operationally",
                                observed_at=now + timedelta(minutes=2), received_at=now + timedelta(minutes=3),
                                wind_speed_ms=8)
    assert scope_valid(db, station, future, scope="residual_source", analyzed_at=now + timedelta(minutes=4))
    decide_station_scope(db, station, scope="monitoring", approved=False,
                         actor=user.email, reason="sensor concern", reviewer=user)
    db.commit()
    assert not scope_valid(db, station, future, scope="residual_source", analyzed_at=now + timedelta(minutes=5))
    audit = db.scalars(select(WeatherStationApprovalAudit).where(
        WeatherStationApprovalAudit.station_id == station.id)).all()
    assert len(audit) == 4 and sum(not item.approved for item in audit) == 2


def test_spatial_group_proposals_are_idempotent_and_unreviewed(db):
    left, right = _station(db), _station(db)
    preview = propose_group_candidates(db, [left, right])
    assert preview == {"candidate_pairs": 1, "proposal_rows": 1, "dry_run": True}
    first = propose_group_candidates(db, [left, right], dry_run=False)
    second = propose_group_candidates(db, [left, right], dry_run=False)
    assert first["proposal_rows"] == 2
    assert second["proposal_rows"] == 0
    rows = db.scalars(select(WeatherStationGroupDecision).where(
        WeatherStationGroupDecision.epoch_id.in_([left.current_epoch_id, right.current_epoch_id]))).all()
    assert len(rows) == 2 and all(item.status == "proposed" and item.actor is None for item in rows)
    assert not left.residual_approved and not right.holdout_target_approved


def test_persisted_dossier_is_database_immutable(db):
    station = _station(db)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    _, dossier_hash = persist_dossier(
        db, station, end=end, window_days=1, dry_run=False
    )
    with pytest.raises(DBAPIError, match="weather_station_dossiers are immutable"):
        db.execute(
            update(WeatherStationDossier)
            .where(WeatherStationDossier.dossier_hash == dossier_hash)
            .values(ready_for_review=True)
        )
        db.commit()
    db.rollback()
    stored = db.scalar(
        select(WeatherStationDossier).where(
            WeatherStationDossier.dossier_hash == dossier_hash
        )
    )
    assert stored is not None and stored.ready_for_review is False


def test_import_batch_detects_stuck_sensor_over_time(db):
    station = _station(db)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    rows = [_row(station, now - timedelta(minutes=minute), now, speed=8)
            for minute in (40, 30, 20, 10)]
    assert persist_batch(db, station, rows, dry_run=False)["persisted"] == 4
    latest = db.scalar(select(WeatherObservation).where(
        WeatherObservation.station_id == station.id,
        WeatherObservation.observed_at == now - timedelta(minutes=10)))
    assert "sensor_stuck" in latest.qc_flags
