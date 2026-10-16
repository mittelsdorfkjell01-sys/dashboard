"""Idempotent persistence for normalized tide-gauge provider data."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TideObservation, TideSensor, TideStation, TideStationAlias
from app.tides.stations import ProviderObservation, ProviderStation, TideStationProvider


def evidence_hash(observation: ProviderObservation) -> str:
    payload = {
        "provider": observation.provider,
        "station": observation.provider_station_id,
        "sensor": observation.provider_sensor_id,
        "observed_at": observation.observed_at.astimezone(timezone.utc).isoformat(),
        "value_m": observation.value_m,
        "vertical_datum": observation.vertical_datum,
        "raw": observation.raw,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def upsert_station(db: Session, item: ProviderStation) -> TideStation:
    alias = db.scalar(select(TideStationAlias).where(
        TideStationAlias.provider == item.provider,
        TideStationAlias.provider_station_id == item.provider_station_id,
    ))
    station = db.get(TideStation, alias.station_id) if alias else None
    if station is None:
        station = db.scalar(select(TideStation).where(
            TideStation.canonical_key == f"{item.provider}:{item.provider_station_id}"
        ))
    if station is None:
        station = TideStation(
            canonical_key=f"{item.provider}:{item.provider_station_id}",
            name=item.name,
            country_code=item.country_code,
            operator=item.operator,
            location=WKTElement(f"POINT({item.longitude} {item.latitude})", srid=4326),
            status="active",
            public_enabled=True,
            quality_status="raw",
            station_metadata=item.metadata,
        )
        db.add(station)
        db.flush()
    if alias is None:
        alias = TideStationAlias(
            station_id=station.id,
            provider=item.provider,
            provider_station_id=item.provider_station_id,
            source_url=item.source_url,
            attribution={"provider": item.provider, "source_url": item.source_url},
        )
        db.add(alias)
    if station is not None:
        station.name = item.name
        station.country_code = item.country_code
        station.operator = item.operator
        station.location = WKTElement(f"POINT({item.longitude} {item.latitude})", srid=4326)
        station.status = "active"
        station.station_metadata = item.metadata
        alias.source_url = item.source_url
    return station


def sync_catalog(db: Session, provider: TideStationProvider) -> list[TideStation]:
    stations = [upsert_station(db, item) for item in provider.stations()]
    db.commit()
    return stations


def persist_observations(
    db: Session,
    station: TideStation,
    observations: list[ProviderObservation],
) -> int:
    inserted = 0
    for item in observations:
        sensor = db.scalar(select(TideSensor).where(
            TideSensor.provider == item.provider,
            TideSensor.provider_sensor_id == item.provider_sensor_id,
        ))
        if sensor is None:
            sensor = TideSensor(
                station_id=station.id,
                provider=item.provider,
                provider_sensor_id=item.provider_sensor_id,
                unit=item.unit,
                vertical_datum=item.vertical_datum,
            )
            db.add(sensor)
            db.flush()
        digest = evidence_hash(item)
        exists = db.scalar(select(TideObservation.id).where(
            TideObservation.sensor_id == sensor.id,
            TideObservation.observed_at == item.observed_at,
            TideObservation.payload_sha256 == digest,
        ))
        if exists is not None:
            continue
        db.add(TideObservation(
            sensor_id=sensor.id,
            observed_at=item.observed_at,
            received_at=datetime.now(timezone.utc),
            value_m=item.value_m,
            vertical_datum=item.vertical_datum,
            quality_status=item.quality_status,
            payload_sha256=digest,
            raw_payload=item.raw,
        ))
        if station.latest_observation_at is None or item.observed_at > station.latest_observation_at:
            station.latest_observation_at = item.observed_at
        inserted += 1
    db.commit()
    return inserted
