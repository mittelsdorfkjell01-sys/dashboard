"""Idempotent normalized public-observation import and quarantine storage."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, nullsfirst, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.live.cache import Cache
from app.live.public_cache import invalidate_public_measurement
from app.config import get_settings
from app.models import (
    WeatherObservation,
    WeatherObservationImportState,
    WeatherObservationQuarantine,
    WeatherStation,
)
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
                "elevation_difference_m": (None if elevation is None or candidate.elevation_m is None
                                            else round(candidate.elevation_m - float(elevation), 1)),
                "recommended": True, "approved": False,
                "representativeness_status": "unreviewed",
            })
    return output


def sync_catalog_candidates(db, candidates: list[dict], *, dry_run=True) -> dict:
    """Batch-upsert recommendations without ever granting editorial approval."""
    report = {"received": len(candidates), "persisted": 0, "dry_run": dry_run}
    if dry_run or not candidates:
        return report
    safe = [{**row, "active": True, "approved": False, "blocked": False} for row in candidates]
    stmt = insert(WeatherStation).values(safe).on_conflict_do_update(
        constraint="uq_weather_station_spot_provider",
        set_={key: getattr(insert(WeatherStation).excluded, key) for key in (
            "name", "latitude", "longitude", "distance_km", "elevation_m",
            "elevation_difference_m", "wigos_id", "icao_id",
            "measurement_height_m", "license", "provenance", "recommended")},
    ).returning(WeatherStation.id)
    report["persisted"] = len(db.execute(stmt).scalars().all())
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


def persist_batch(db, station, rows, *, cache: Cache | None = None, dry_run=True):
    source_rows = list(rows)
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
    report = {
        "received": len(source_rows),
        "normalized": len(reconciled),
        "deduplicated": len(source_rows) - len(reconciled),
        "accepted": len(accepted),
        "persisted": 0,
        "rejected": len(rejected),
        "quarantined": len(quarantined),
        "quarantine_persisted": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return report

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
        "data_issues": list(row.data_issues),
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


def import_station(station, fetcher, db, *, cache=None, dry_run=True, attempts=2):
    last_error = None
    for _attempt in range(max(1, attempts)):
        try:
            report = persist_batch(
                db,
                station,
                fetcher(station.provider_station_id),
                cache=cache,
                dry_run=dry_run,
            )
            if not dry_run:
                _record_import_state(db, station, report=report)
            return report
        except Exception as exc:
            last_error = type(exc).__name__
            rollback = getattr(db, "rollback", None)
            if rollback is not None:
                rollback()
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
        next_attempt_at = attempted_at + timedelta(
            seconds=retry_delay_seconds(
                failure_count,
                initial_seconds=settings.weather_observation_retry_initial_seconds,
                maximum_seconds=settings.weather_observation_retry_max_seconds,
            )
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


def provider_fetchers() -> dict:
    """Provider id -> callable(station_id) -> list[NormalizedObservation].

    Imported lazily so the scheduler entry point pays the provider/httpx import
    cost only when it actually runs. KNMI needs a registered key and stays out
    of the automatic cycle until an operator wires it in.
    """
    from app.weather.providers import awc_metar, dmi, dwd

    return {
        "dwd": dwd.fetch_now,
        "dmi": dmi.fetch_recent,
        "awc_metar": awc_metar.fetch_recent,
    }


def run_observation_import(db, *, providers=("dwd", "dmi", "awc_metar"), limit: int = 25,
                           dry_run: bool = True, cache: Cache | None = None) -> dict:
    """Import a bounded batch of station observations, oldest imports first.

    Idempotent through ``uq_weather_observation_time``; repeated runs replay the
    overlap window without creating duplicates. Accepted normalized rows and
    rejected/quarantined audit rows stay separate; neither feeds a forecast.
    """
    fetchers = provider_fetchers()
    due_at = datetime.now(timezone.utc)
    stations = db.scalars(
        select(WeatherStation)
        .outerjoin(
            WeatherObservationImportState,
            WeatherObservationImportState.station_id == WeatherStation.id,
        )
        .where(
            WeatherStation.active.is_(True),
            WeatherStation.provider.in_(list(providers)),
            or_(
                WeatherObservationImportState.next_attempt_at.is_(None),
                WeatherObservationImportState.next_attempt_at <= due_at,
            ),
        )
        .order_by(nullsfirst(WeatherStation.last_import_at.asc()))
        .limit(max(1, limit))
    ).all()
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
        result = import_station(station, fetcher, db, cache=cache, dry_run=dry_run)
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
    return report
