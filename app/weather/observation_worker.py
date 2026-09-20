"""Idempotent normalized public-observation import and quarantine storage."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Iterable
import uuid
import httpx

from sqlalchemy import delete, nullsfirst, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from app.live.cache import Cache
from app.live.public_cache import invalidate_public_measurement
from app.config import get_settings
from app.models import (
    WeatherObservation,
    WeatherObservationImportState,
    WeatherObservationQuarantine,
    WeatherObservationRevision,
    WeatherStation,
    WeatherStationCaptureCycle,
    WeatherStationMetadataRevision,
    WeatherStationProviderCursor,
)
from app.weather.observation_quality import evaluate_observation
from app.weather.station_epochs import configuration_from_candidate, ensure_epoch
from app.weather.providers.common import (
    ObservationStation,
    deduplicate_observations,
    nearest_stations,
    normalized_observation_payload,
    with_station_metadata,
)

DEFAULT_RETENTION_DAYS = 120


def retry_delay_seconds(
    consecutive_failures: int,
    *,
    initial_seconds: int,
    maximum_seconds: int,
) -> int:
    """Bounded exponential delay used between independent import job runs."""
    exponent = max(0, min(int(consecutive_failures) - 1, 20))
    return min(int(maximum_seconds), int(initial_seconds) * (2**exponent))


def catchup_window(station, *, now=None, overlap_minutes: int = 20, max_days: int = 7) -> tuple[datetime, datetime]:
    """Bounded provider interval with overlap; uniqueness makes replay idempotent."""
    end = now or datetime.now(timezone.utc)
    last = getattr(station, "last_observation_at", None)
    start = end - timedelta(days=max_days) if last is None else last - timedelta(minutes=overlap_minutes)
    return max(start, end - timedelta(days=max_days)), end


def catalog_candidates(spots: Iterable, catalog: list[ObservationStation], *, limit=3, max_km=100) -> list[dict]:
    """Pure candidate comparison used by dry-runs and the admin UI."""
    output = []
    for spot in spots:
        latitude = float(getattr(spot, "latitude"))
        longitude = float(getattr(spot, "longitude"))
        elevation = getattr(spot, "elevation_m", None)
        for candidate, distance in nearest_stations(latitude, longitude, catalog, limit=limit, max_km=max_km):
            output.append({
                "spot_id": str(spot.id), "provider": candidate.provider,
                "provider_station_id": candidate.station_id, "name": candidate.name,
                "latitude": candidate.latitude, "longitude": candidate.longitude,
                "distance_km": round(distance, 3), "elevation_m": candidate.elevation_m,
                "wigos_id": candidate.wigos_id, "icao_id": candidate.icao_id,
                "measurement_height_m": candidate.measurement_height_m,
                "license": candidate.license, "provenance": candidate.provenance,
                "country_code": candidate.country_code, "operator": candidate.operator,
                "station_type": candidate.station_type,
                "active": candidate.active,
                "sensor_metadata": candidate.sensor_metadata,
                "active_from": candidate.active_from, "active_to": candidate.active_to,
                "metadata_updated_at": candidate.metadata_updated_at,
                "source_url": candidate.source_url,
                "metadata_payload_hash": hashlib.sha256(json.dumps(candidate.raw_payload, sort_keys=True, default=str).encode()).hexdigest(),
                "metadata_payload": candidate.raw_payload,
                "metadata_received_at": candidate.received_at,
                "elevation_difference_m": (None if elevation is None or candidate.elevation_m is None
                                            else round(candidate.elevation_m - float(elevation), 1)),
                "recommended": True, "approved": False,
                "representativeness_status": "unreviewed",
            })
    return output


def sync_catalog_candidates(db, candidates: list[dict], *, dry_run=True) -> dict:
    """Batch-upsert recommendations without ever granting editorial approval."""
    report = {"received": len(candidates), "persisted": 0, "upserted": 0,
              "metadata_revisions_persisted": 0, "metadata_drift": 0, "dry_run": dry_run}
    if dry_run or not candidates:
        return report
    safe = [{**{key: value for key, value in row.items()
                if key not in {"metadata_payload", "metadata_received_at"}},
             "active": row.get("active", True), "approved": False, "blocked": False}
            for row in candidates]
    previous = db.scalars(select(WeatherStation).where(
        WeatherStation.spot_id.in_([row["spot_id"] for row in safe]),
        WeatherStation.provider.in_([row["provider"] for row in safe]),
    )).all()
    existing = {(str(item.spot_id), item.provider, item.provider_station_id): item for item in previous}
    accepted = []
    for row in safe:
        old = existing.get((row["spot_id"], row["provider"], row["provider_station_id"]))
        if old and any(getattr(old, field) is not None and row.get(field) is not None
                       and abs(float(getattr(old, field)) - float(row[field])) > tolerance
                       for field, tolerance in (("latitude", 0.001), ("longitude", 0.001),
                                                ("elevation_m", 5), ("measurement_height_m", 1))):
            old.blocked = True
            old.decision_reason = "metadata_drift_requires_review"
            old.identity_review_status = "unreviewed"
            if row.get("active") is False:
                old.active = False
            report["metadata_drift"] += 1
            continue
        accepted.append(row)
    safe = accepted
    by_key = dict(existing)
    if safe:
        stmt = insert(WeatherStation).values(safe).on_conflict_do_update(
            constraint="uq_weather_station_spot_provider",
            set_={key: getattr(insert(WeatherStation).excluded, key) for key in (
                "name", "latitude", "longitude", "distance_km", "elevation_m",
                "elevation_difference_m", "wigos_id", "icao_id",
                "measurement_height_m", "license", "provenance", "recommended",
                "country_code", "operator", "station_type", "sensor_metadata",
                "active_from", "active_to", "metadata_updated_at", "source_url",
                "metadata_payload_hash", "active")},
        ).returning(WeatherStation.id)
        report["upserted"] = len(db.execute(stmt).scalars().all())
        report["persisted"] = sum(
            (row["spot_id"], row["provider"], row["provider_station_id"]) not in existing
            for row in safe
        )
        station_rows = db.scalars(select(WeatherStation).where(
            WeatherStation.spot_id.in_([row["spot_id"] for row in safe]),
            WeatherStation.provider.in_([row["provider"] for row in safe]),
        )).all()
        by_key.update({(str(item.spot_id), item.provider, item.provider_station_id): item
                       for item in station_rows})
    revisions = []
    for candidate in candidates:
        station = by_key.get((candidate["spot_id"], candidate["provider"], candidate["provider_station_id"]))
        if station is None:
            continue
        received = candidate.get("metadata_received_at")
        if received is None or received.tzinfo is None:
            # No raw metadata revision can claim an invented receipt time.
            continue
        revisions.append({
            "station_id": station.id,
            "payload_hash": candidate["metadata_payload_hash"],
            "raw_payload": candidate.get("metadata_payload") or {},
            "source_url": candidate.get("source_url"),
            "license": candidate.get("license"),
            "received_at": received,
        })
    if revisions:
        report["metadata_revisions_persisted"] = len(db.execute(
            insert(WeatherStationMetadataRevision).values(revisions)
            .on_conflict_do_nothing(constraint="uq_weather_station_metadata_revision")
            .returning(WeatherStationMetadataRevision.id)
        ).scalars().all())
    report["epochs_proposed"] = 0
    for candidate in candidates:
        station = by_key.get((candidate["spot_id"], candidate["provider"], candidate["provider_station_id"]))
        received = candidate.get("metadata_received_at")
        if station is None or received is None:
            continue
        revision = db.scalar(select(WeatherStationMetadataRevision).where(
            WeatherStationMetadataRevision.station_id == station.id,
            WeatherStationMetadataRevision.payload_hash == candidate["metadata_payload_hash"],
        ))
        _, created = ensure_epoch(
            db, station, configuration_from_candidate(candidate), first_seen_at=received,
            metadata_revision_id=revision.id if revision else None,
        )
        report["epochs_proposed"] += int(created)
    db.commit()
    return report


def retention_plan(db, *, retention_days=DEFAULT_RETENTION_DAYS, now=None) -> dict:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(30, retention_days))
    rows = db.scalars(select(WeatherObservation.id).where(WeatherObservation.observed_at < cutoff)).all()
    return {"cutoff": cutoff.isoformat(), "candidate_rows": len(rows), "deleted": 0, "requires_approval": True}


def apply_retention(db, *, approved=False, retention_days=DEFAULT_RETENTION_DAYS, now=None) -> dict:
    plan = retention_plan(db, retention_days=retention_days, now=now)
    if not approved:
        return plan
    cutoff = datetime.fromisoformat(plan["cutoff"])
    result = db.execute(delete(WeatherObservation).where(WeatherObservation.observed_at < cutoff))
    db.commit()
    plan.update({"deleted": result.rowcount or 0, "requires_approval": False})
    return plan


def persist_batch(db, station, rows, *, cache: Cache | None = None, dry_run=True,
                  capture_mode: str = "operational"):
    if capture_mode not in {"operational", "historical_backfill"}:
        raise ValueError("unsupported_capture_mode")
    source_rows = list(rows)
    if source_rows and not dry_run:
        # Serialise competing imports of one configured station before reading
        # its current revision. The transaction lock is released on commit/rollback.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                   {"key": str(station.id)})
    normalized = deduplicate_observations([
        with_station_metadata(row, station) for row in source_rows
    ])
    accepted = [row for row in normalized if row.import_status == "accepted"]

    existing_by_time = {}
    observed_times = [row.observed_at for row in accepted if row.observed_at is not None]
    if observed_times:
        existing = db.scalars(
            select(WeatherObservation).where(
                WeatherObservation.station_id == station.id,
                WeatherObservation.observed_at.in_(observed_times),
            )
        ).all()
        existing_by_time = {row.observed_at: row for row in existing}

    reconciled = []
    for row in normalized:
        existing = existing_by_time.get(row.observed_at)
        if row.import_status != "accepted" or existing is None:
            reconciled.append(row)
            continue
        same_measurement = (
            existing.wind_speed_ms == row.wind_speed_ms
            and existing.wind_direction_deg == row.wind_direction_deg
            and existing.wind_gust_ms == row.wind_gust_ms
        )
        if same_measurement:
            reconciled.append(row)
            continue
        issue = "duplicate:conflict"
        reconciled.append(replace(
            row,
            import_status="quarantined",
            rejection_reason=";".join(
                dict.fromkeys(filter(None, (row.rejection_reason, issue)))
            ),
            data_issues=tuple(dict.fromkeys((*row.data_issues, issue))),
        ))

    accepted = [row for row in reconciled if row.import_status == "accepted"]
    rejected = [row for row in reconciled if row.import_status == "rejected"]
    quarantined = [
        row for row in reconciled if row.import_status in {"raw", "quarantined"}
    ]
    audit_rows = [row for row in reconciled if row.import_status != "accepted"]
    first_time = min((row.observed_at for row in reconciled if row.observed_at), default=None)
    prior_history = db.scalars(select(WeatherObservation).where(
        WeatherObservation.station_id == station.id,
        WeatherObservation.observed_at >= first_time - timedelta(hours=1),
        WeatherObservation.observed_at < first_time,
    ).order_by(WeatherObservation.observed_at)).all() if first_time else []
    decisions = {}
    for row in sorted(reconciled, key=lambda item: (item.observed_at or datetime.min.replace(tzinfo=timezone.utc),
                                                    item.fingerprint)):
        decisions[row.fingerprint] = evaluate_observation(row, station, prior=prior_history)
        if row.import_status == "accepted" and row.observed_at is not None:
            prior_history.append(row)
            prior_history = [item for item in prior_history
                             if item.observed_at >= row.observed_at - timedelta(hours=1)]
    def availability(row):
        if capture_mode == "historical_backfill":
            return "historical_backfill"
        if (row.observed_at is None or row.received_at is None
                or row.received_at.tzinfo is None or row.observed_at.tzinfo is None):
            return "availability_unproven"
        delay = row.received_at - row.observed_at
        return "captured_operationally" if timedelta(minutes=-2) <= delay <= timedelta(minutes=30) else "historical_backfill"
    epoch_id = getattr(station, "current_epoch_id", None)
    report = {
        "received": len(source_rows),
        "normalized": len(reconciled),
        "deduplicated": len(source_rows) - len(reconciled),
        "accepted": len(accepted),
        "persisted": 0,
        "rejected": len(rejected),
        "quarantined": len(quarantined),
        "quarantine_persisted": 0,
        "revisions_persisted": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return report

    revision_ids = {}
    revision_values = []
    for row in reconciled:
        revision_id = uuid.uuid4()
        revision_ids[row.fingerprint] = revision_id
        raw_json = json.dumps(row.raw_payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        revision_values.append({
            "id": revision_id, "station_id": station.id,
            "observed_at": row.observed_at, "received_at": row.received_at,
            "first_seen_at": row.received_at, "epoch_id": epoch_id,
            "availability_class": availability(row),
            "revised_at": row.received_at if existing_by_time.get(row.observed_at) is not None else None,
            "imported_at": row.imported_at, "published_at": row.published_at,
            "provider": row.provider, "provider_station_id": row.provider_station_id,
            "source_url": row.provenance.get("source_url"), "license": row.license,
            "parser_version": row.parser_version,
            "payload_hash": hashlib.sha256(raw_json).hexdigest(),
            "fingerprint": row.fingerprint, "raw_payload": row.raw_payload,
            "normalized_payload": normalized_observation_payload(row),
            "qc_version": decisions[row.fingerprint].version,
            "qc_stage": decisions[row.fingerprint].stage,
            "qc_flags": list(decisions[row.fingerprint].reasons),
            "revision_status": (
                "current" if row.import_status == "accepted" and existing_by_time.get(row.observed_at) is None
                else "pending_review" if row.import_status == "quarantined" and "duplicate:conflict" in row.data_issues
                else "rejected" if row.import_status == "rejected" else "quarantined"
            ),
        })
    if revision_values:
        inserted = db.execute(
            insert(WeatherObservationRevision).values(revision_values)
            .on_conflict_do_nothing(constraint="uq_weather_revision_station_fingerprint")
            .returning(WeatherObservationRevision.id)
        ).scalars().all()
        report["revisions_persisted"] = len(inserted)
        # An existing replay retains its original first-receipt timestamp.
        revision_rows = db.execute(select(WeatherObservationRevision.fingerprint, WeatherObservationRevision.id)
                                   .where(WeatherObservationRevision.station_id == station.id,
                                          WeatherObservationRevision.fingerprint.in_(revision_ids))).all()
        revision_ids = dict(revision_rows)

    metadata_rows = [
        row
        for row in reconciled
        if row.provider == station.provider
        and row.provider_station_id == station.provider_station_id
    ]
    for attribute in (
        "wigos_id", "icao_id", "measurement_height_m", "license"
    ):
        if getattr(station, attribute, None) is None:
            value = next(
                (
                    getattr(row, attribute)
                    for row in metadata_rows
                    if getattr(row, attribute) is not None
                ),
                None,
            )
            if value is not None:
                setattr(station, attribute, value)
    provider_provenance = {}
    for row in metadata_rows:
        provider_provenance.update(row.provenance)
    provider_provenance.update(getattr(station, "provenance", None) or {})
    if provider_provenance:
        station.provenance = provider_provenance

    accepted_values = [{
        "station_id": station.id, "observed_at": row.observed_at,
        "wind_speed_ms": row.wind_speed_ms, "wind_direction_deg": row.wind_direction_deg,
        "wind_u_ms": row.wind_u_ms, "wind_v_ms": row.wind_v_ms,
        "wind_gust_ms": row.wind_gust_ms, "gust_period_seconds": row.gust_period_seconds,
        "provider_quality": row.provider_quality,
        "fetched_at": row.received_at, "received_at": row.received_at,
        "imported_at": row.imported_at, "import_status": row.import_status,
        "first_seen_at": row.received_at, "epoch_id": epoch_id,
        "availability_class": availability(row),
        "data_issues": list(row.data_issues),
        "published_at": row.published_at,
        "measurement_period_seconds": row.measurement_period_seconds,
        "averaging_period_seconds": row.averaging_period_seconds,
        "qc_version": decisions[row.fingerprint].version,
        "qc_stage": decisions[row.fingerprint].stage,
        "qc_flags": list(decisions[row.fingerprint].reasons),
        "raw_revision_id": revision_ids[row.fingerprint],
    } for row in accepted]
    if accepted_values:
        result = db.execute(
            insert(WeatherObservation)
            .values(accepted_values)
            .on_conflict_do_nothing(constraint="uq_weather_observation_time")
            .returning(WeatherObservation.id)
        )
        report["persisted"] = len(result.scalars().all())

    quarantine_values = [{
        "station_id": station.id,
        "provider": row.provider,
        "provider_station_id": row.provider_station_id,
        "station_identity": row.station_identity,
        "observed_at": row.observed_at,
        "received_at": row.received_at,
        "imported_at": row.imported_at,
        "import_status": row.import_status,
        "rejection_reason": row.rejection_reason or "not_accepted",
        "data_issues": list(row.data_issues),
        "raw_payload": row.raw_payload,
        "normalized_payload": normalized_observation_payload(row),
        "fingerprint": row.fingerprint,
    } for row in audit_rows]
    if quarantine_values:
        result = db.execute(
            insert(WeatherObservationQuarantine)
            .values(quarantine_values)
            .on_conflict_do_nothing(
                constraint="uq_weather_observation_quarantine_fingerprint"
            )
            .returning(WeatherObservationQuarantine.id)
        )
        report["quarantine_persisted"] = len(result.scalars().all())

    if reconciled:
        station.last_import_at = max(row.imported_at for row in reconciled)
    if accepted:
        latest = max(accepted, key=lambda row: row.observed_at)
        if station.last_observation_at is None or latest.observed_at > station.last_observation_at:
            station.last_observation_at = latest.observed_at
    db.commit()
    if cache and report["persisted"]:
        # Invalidate the measurement layer rather than writing a raw row here: the
        # serving path rebuilds the gated, correctly-shaped MeasurementRead payload
        # (eligibility gate, provider_station_id, provenance, wind_direction_from_deg)
        # on the next request. A hand-rolled entry here skipped the gate and used
        # the wrong field names, which broke response validation.
        invalidate_public_measurement(cache, station.spot_id)
    return report


def import_station(station, fetcher, db, *, cache=None, dry_run=True, attempts=2,
                   capture_mode="operational"):
    last_error = None
    for _attempt in range(max(1, attempts)):
        try:
            fetched = list(fetcher(station.provider_station_id))
            if capture_mode == "operational":
                start, end = catchup_window(station)
                fetched = [row for row in fetched if row.observed_at is None
                           or start <= row.observed_at <= end + timedelta(minutes=5)]
            report = persist_batch(
                db,
                station,
                fetched,
                cache=cache,
                dry_run=dry_run,
                capture_mode=capture_mode,
            )
            if not dry_run:
                _record_import_state(db, station, report=report)
            return report
        except Exception as exc:
            last_error = type(exc).__name__
            rollback = getattr(db, "rollback", None)
            if rollback is not None:
                rollback()
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 500, 502, 503, 504}:
                break  # defer to next cron run; never hammer a throttled provider
    report = {
        "received": 0, "normalized": 0, "deduplicated": 0,
        "accepted": 0, "persisted": 0, "rejected": 0,
        "quarantined": 0, "quarantine_persisted": 0,
        "dry_run": dry_run, "error_class": last_error,
    }
    if not dry_run:
        _record_import_state(db, station, report=report)
    return report


def _record_import_state(db, station, *, report: dict) -> None:
    """Persist only sanitized operational state; exception messages never land."""
    attempted_at = datetime.now(timezone.utc)
    failed = bool(report.get("error_class"))
    previous = db.get(WeatherObservationImportState, station.id)
    failure_count = (
        int(getattr(previous, "consecutive_failures", 0) or 0) + 1
        if failed
        else 0
    )
    settings = get_settings()
    next_attempt_at = None
    if failed:
        base_delay = retry_delay_seconds(
            failure_count,
            initial_seconds=settings.weather_observation_retry_initial_seconds,
            maximum_seconds=settings.weather_observation_retry_max_seconds,
        )
        jitter_unit = int(hashlib.sha256(f"{station.id}:{failure_count}".encode()).hexdigest()[:2], 16) / 255
        next_attempt_at = attempted_at + timedelta(
            seconds=min(settings.weather_observation_retry_max_seconds,
                        base_delay + round(base_delay * 0.2 * jitter_unit))
        )
    # Advance the scheduling cursor on both success and failure. Otherwise a
    # down provider with NULL/old last_import_at could monopolize every bounded
    # cron batch and starve healthy providers.
    station.last_import_at = attempted_at
    values = {
        "station_id": station.id,
        "provider": station.provider,
        "status": "error" if failed else "success",
        "last_attempt_at": attempted_at,
        "last_success_at": None if failed else attempted_at,
        "last_error_at": attempted_at if failed else None,
        "next_attempt_at": next_attempt_at,
        "error_class": report.get("error_class") if failed else None,
        "consecutive_failures": failure_count,
        "last_counts": {
            key: int(report.get(key, 0) or 0)
            for key in (
                "received", "normalized", "deduplicated", "accepted", "persisted",
                "rejected", "quarantined", "quarantine_persisted",
            )
        },
    }
    statement = insert(WeatherObservationImportState).values(values)
    excluded = statement.excluded
    if failed:
        updates = {
            "provider": excluded.provider,
            "status": excluded.status,
            "last_attempt_at": excluded.last_attempt_at,
            "last_error_at": excluded.last_error_at,
            "next_attempt_at": excluded.next_attempt_at,
            "error_class": excluded.error_class,
            "consecutive_failures": excluded.consecutive_failures,
            "last_counts": excluded.last_counts,
        }
    else:
        updates = {
            "provider": excluded.provider,
            "status": excluded.status,
            "last_attempt_at": excluded.last_attempt_at,
            "last_success_at": excluded.last_success_at,
            "last_error_at": None,
            "next_attempt_at": None,
            "error_class": None,
            "consecutive_failures": 0,
            "last_counts": excluded.last_counts,
        }
    db.execute(
        statement.on_conflict_do_update(index_elements=["station_id"], set_=updates)
    )
    db.commit()


def provider_fetchers(db=None) -> dict:
    """Provider id -> callable(station_id) -> list[NormalizedObservation].

    Imported lazily so the scheduler entry point pays the provider/httpx import
    cost only when it actually runs. KNMI needs a registered key and stays out
    of the automatic cycle until an operator wires it in.
    """
    from app.weather.providers import awc_metar, dmi, dwd

    return {
        "dwd": (
            (lambda station_id: dwd.fetch_now(station_id, db=db))
            if db is not None else dwd.fetch_now
        ),
        "dmi": dmi.fetch_recent,
        "awc_metar": awc_metar.fetch_recent,
    }


def run_observation_import(db, *, providers=("dwd", "dmi", "awc_metar"), limit: int = 25,
                           dry_run: bool = True, cache: Cache | None = None,
                           capture_mode: str = "operational") -> dict:
    """Import a bounded batch of station observations, oldest imports first.

    Idempotent through ``uq_weather_observation_time``; repeated runs replay the
    overlap window without creating duplicates. Accepted normalized rows and
    rejected/quarantined audit rows stay separate; neither feeds a forecast.
    """
    fetchers = provider_fetchers(None if dry_run else db)
    due_at = datetime.now(timezone.utc)
    cursor_get = getattr(db, "get", None)
    cursors = {provider: cursor_get(WeatherStationProviderCursor, provider) if cursor_get else None
               for provider in providers}
    enabled_providers = [provider for provider in providers
                         if cursors[provider] is None or not cursors[provider].paused]
    # Fetch a bounded queue per provider and interleave it. A single provider
    # with many never-imported stations must not consume the global batch and
    # starve every other source (the old query did exactly that).
    per_provider = {}
    batch_limit = max(1, limit)
    for provider in enabled_providers:
        rows = db.scalars(
            select(WeatherStation)
            .outerjoin(
                WeatherObservationImportState,
                WeatherObservationImportState.station_id == WeatherStation.id,
            )
            .where(
                WeatherStation.active.is_(True),
                WeatherStation.provider == provider,
                or_(
                    WeatherObservationImportState.next_attempt_at.is_(None),
                    WeatherObservationImportState.next_attempt_at <= due_at,
                ),
            )
            .order_by(nullsfirst(WeatherStation.last_import_at.asc()), WeatherStation.id)
            .limit(batch_limit)
        ).all()
        # Defensive filtering also keeps lightweight test doubles honest.
        per_provider[provider] = [row for row in rows if row.provider == provider]
    provider_order = list(enabled_providers)
    if batch_limit < len(provider_order) and provider_order:
        offset = int(due_at.timestamp() // 600) % len(provider_order)
        provider_order = provider_order[offset:] + provider_order[:offset]
    stations = []
    position = 0
    while len(stations) < batch_limit:
        added = False
        for provider in provider_order:
            bucket = per_provider[provider]
            if position < len(bucket):
                stations.append(bucket[position])
                added = True
                if len(stations) == batch_limit:
                    break
        if not added:
            break
        position += 1
    report = {
        "stations": len(stations), "persisted": 0, "accepted": 0,
        "rejected": 0, "quarantined": 0, "quarantine_persisted": 0,
        "errors": 0, "dry_run": dry_run, "providers": list(providers),
        "provider_reports": {}, "station_errors": [],
    }
    for station in stations:
        fetcher = fetchers.get(station.provider)
        if fetcher is None:
            report["errors"] += 1
            missing_result = {
                "received": 0, "normalized": 0, "deduplicated": 0,
                "accepted": 0, "persisted": 0, "rejected": 0,
                "quarantined": 0, "quarantine_persisted": 0,
                "dry_run": dry_run, "error_class": "ProviderNotConfigured",
            }
            if not dry_run:
                _record_import_state(db, station, report=missing_result)
            report["station_errors"].append({
                "station_id": str(station.id), "provider": station.provider,
                "error_class": "ProviderNotConfigured",
            })
            provider_report = report["provider_reports"].setdefault(
                station.provider,
                {
                    "stations": 0, "persisted": 0, "accepted": 0,
                    "rejected": 0, "quarantined": 0, "errors": 0,
                },
            )
            provider_report["stations"] += 1
            provider_report["errors"] += 1
            continue
        result = import_station(station, fetcher, db, cache=cache, dry_run=dry_run,
                                capture_mode=capture_mode)
        report["persisted"] += result.get("persisted", 0)
        report["accepted"] += result.get("accepted", 0)
        report["rejected"] += result.get("rejected", 0)
        report["quarantined"] += result.get("quarantined", 0)
        report["quarantine_persisted"] += result.get("quarantine_persisted", 0)
        if result.get("error_class"):
            report["errors"] += 1
            report["station_errors"].append({
                "station_id": str(station.id), "provider": station.provider,
                "error_class": result["error_class"],
            })
        provider_report = report["provider_reports"].setdefault(station.provider, {
            "stations": 0, "persisted": 0, "accepted": 0,
            "rejected": 0, "quarantined": 0, "errors": 0,
        })
        provider_report["stations"] += 1
        for key in ("persisted", "accepted", "rejected", "quarantined"):
            provider_report[key] += int(result.get(key, 0) or 0)
        provider_report["errors"] += int(bool(result.get("error_class")))
    if not dry_run:
        for provider in enabled_providers:
            cursor = cursors[provider] or WeatherStationProviderCursor(provider=provider, paused=False)
            provider_result = report["provider_reports"].get(provider, {})
            cursor.last_cycle_at = due_at
            cursor.last_error_class = "StationImportError" if provider_result.get("errors") else None
            if provider_result.get("stations") and not provider_result.get("errors"):
                cursor.last_success_at = due_at
                station_watermarks = [item.last_observation_at for item in stations
                                      if item.provider == provider and item.last_observation_at]
                if station_watermarks:
                    new_watermark = max(station_watermarks)
                    if cursor.watermark_at is None or new_watermark > cursor.watermark_at:
                        cursor.watermark_at = new_watermark
            db.add(cursor)
            provider_result = report["provider_reports"].get(provider, {})
            errors = int(provider_result.get("errors", 0) or 0)
            station_count = int(provider_result.get("stations", 0) or 0)
            db.add(WeatherStationCaptureCycle(
                job_type="observations",
                provider=provider,
                started_at=due_at,
                finished_at=datetime.now(timezone.utc),
                status=(
                    "no_work" if station_count == 0
                    else "error" if errors == station_count
                    else "partial" if errors
                    else "success"
                ),
                counts={
                    key: int(provider_result.get(key, 0) or 0)
                    for key in (
                        "stations", "persisted", "accepted", "rejected",
                        "quarantined", "errors",
                    )
                },
            ))
        db.commit()
    report["paused_providers"] = [provider for provider in providers if provider not in enabled_providers]
    return report
