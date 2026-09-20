"""Versioned wind-sensor configuration; import can propose, never approve."""

from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select

from app.models import WeatherStationEpoch, WeatherStationMetadataRevision

EPOCH_VERSION = "station-epoch-v1"
CONFIG_FIELDS = (
    "provider", "provider_station_id", "wigos_id", "icao_id", "latitude",
    "longitude", "elevation_m", "measurement_height_m", "sensor_metadata",
    "active_from", "active_to", "active", "station_type", "typical_interval_minutes",
)


def configuration_from_candidate(candidate: dict) -> dict:
    values = {key: candidate.get(key) for key in CONFIG_FIELDS}
    values["typical_interval_minutes"] = (candidate.get("provenance") or {}).get("typical_interval_minutes")
    return json.loads(json.dumps(values | {"version": EPOCH_VERSION},
                                 default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)))


def configuration_from_station(station) -> dict:
    values = {key: getattr(station, key, None) for key in CONFIG_FIELDS}
    values["typical_interval_minutes"] = (getattr(station, "provenance", None) or {}).get("typical_interval_minutes")
    return json.loads(json.dumps(values | {"version": EPOCH_VERSION},
                                 default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)))


def configuration_hash(configuration: dict) -> str:
    return hashlib.sha256(json.dumps(configuration, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def ensure_epoch(db, station, configuration: dict, *, first_seen_at: datetime,
                 metadata_revision_id=None) -> tuple[WeatherStationEpoch, bool]:
    if first_seen_at.tzinfo is None or first_seen_at.utcoffset() is None:
        raise ValueError("epoch_first_seen_at_utc_required")
    first_seen_at = first_seen_at.astimezone(timezone.utc)
    configuration = json.loads(json.dumps(configuration,
                                default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)))
    hashed = configuration_hash(configuration)
    current = db.get(WeatherStationEpoch, station.current_epoch_id) if station.current_epoch_id else None
    if current is not None and current.configuration_hash == hashed:
        return current, False
    epochs = db.scalars(select(WeatherStationEpoch).where(
        WeatherStationEpoch.station_id == station.id
    ).order_by(WeatherStationEpoch.epoch_number.desc())).all()
    # Never reactivate a prior configuration by hash: it represents a new time period.
    # The unique configuration constraint therefore requires a distinct episode salt.
    if any(item.configuration_hash == hashed for item in epochs):
        configuration = {**configuration, "reintroduced_after_epoch": epochs[0].epoch_number}
        hashed = configuration_hash(configuration)
    if current is not None:
        current.status = "superseded"
        current.superseded_at = first_seen_at
    epoch = WeatherStationEpoch(
        station_id=station.id, epoch_number=(epochs[0].epoch_number + 1 if epochs else 1),
        configuration_hash=hashed, configuration=configuration,
        metadata_revision_id=metadata_revision_id, status="pending_review",
        first_seen_at=first_seen_at,
    )
    db.add(epoch)
    db.flush()
    station.current_epoch_id = epoch.id
    station.blocked = True
    station.decision_reason = "station_epoch_requires_review"
    station.identity_review_status = "unreviewed"
    station.monitoring_approved = False
    station.residual_approved = False
    station.holdout_target_approved = False
    station.holdout_input_approved = False
    return epoch, True


def latest_metadata_revision(db, station_id):
    return db.scalar(select(WeatherStationMetadataRevision).where(
        WeatherStationMetadataRevision.station_id == station_id
    ).order_by(WeatherStationMetadataRevision.created_at.desc(), WeatherStationMetadataRevision.id.desc()))
