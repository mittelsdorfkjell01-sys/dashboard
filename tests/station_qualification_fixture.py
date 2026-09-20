"""Synthetic pre-reviewed epoch evidence for downstream exact-run integration tests.

This is test-only historical setup. Approval workflow itself has separate tests.
"""

from datetime import timedelta
import hashlib
import json

from app.models import (
    WeatherStationApprovalAudit, WeatherStationDossier, WeatherStationEpoch,
    WeatherStationGroupDecision,
)
from app.weather.station_epochs import configuration_from_station, configuration_hash
from app.weather.station_qualification import current_group_decisions, group_version


def persist_operational_fixture(db, station, rows, **kwargs):
    """Persist rows as if a previously running collector received this batch."""
    from app.weather.observation_worker import persist_batch

    values = list(rows)
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id)
    received = [item.received_at for item in values if item.received_at is not None]
    capture_started_at = min(received) - timedelta(seconds=1)
    return persist_batch(
        db,
        station,
        values,
        capture_started_at=capture_started_at,
        collector_enrolled_at=epoch.first_seen_at,
        collector_previously_attempted=True,
        **kwargs,
    )


def seed_reviewed_epoch(db, station, *, before):
    config = configuration_from_station(station)
    epoch = WeatherStationEpoch(
        station_id=station.id, epoch_number=1, configuration_hash=configuration_hash(config),
        configuration=config, status="reviewed", first_seen_at=before - timedelta(days=2),
        reviewed_at=before - timedelta(days=1), reviewer="fixture-admin",
        review_reason="synthetic test evidence",
    )
    db.add(epoch)
    db.flush()
    station.current_epoch_id = epoch.id
    for kind, key in (("physical", station.physical_station_group),
                      ("correlation", station.correlation_group)):
        db.add(WeatherStationGroupDecision(
            epoch_id=epoch.id, group_type=kind, group_key=key, status="confirmed",
            rule_version="fixture-v1", evidence={"fixture": True},
            actor="fixture-admin", reason="synthetic test evidence",
            decided_at=before - timedelta(days=1),
        ))
    db.flush()
    payload = {"fixture": True, "epoch_id": str(epoch.id)}
    dossier_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    db.add(WeatherStationDossier(epoch_id=epoch.id, dossier_hash=dossier_hash,
                                 payload=payload, ready_for_review=True,
                                 generated_at=before - timedelta(days=1)))
    version = group_version(current_group_decisions(db, epoch.id))
    for scope in ("monitoring", "residual_source", "holdout_input", "holdout_target"):
        db.add(WeatherStationApprovalAudit(
            station_id=station.id, epoch_id=epoch.id, scope=scope, approved=True,
            actor="fixture-admin", reason="synthetic test evidence",
            dossier_hash=dossier_hash, policy_version="fixture-v1",
            group_version=version, decided_at=before - timedelta(hours=1),
        ))
    db.commit()
