"""Read-only status check for the three-week Europe wind campaign."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import distinct, func, select

from app.weather.europe_campaign import load_campaign


def database_status(campaign_id: str) -> dict:
    """Return read-only progress counters without affecting forecast serving."""
    from app.db.session import SessionLocal
    from app.models import (
        WeatherExactModelBundle,
        WeatherObservation,
        WeatherStation,
        WeatherStationModelResidual,
    )

    with SessionLocal() as db:
        station_scope = WeatherStation.campaign_key == campaign_id
        stations = db.scalar(
            select(func.count()).select_from(WeatherStation).where(station_scope)
        ) or 0
        observation_row = db.execute(
            select(
                func.count(WeatherObservation.id),
                func.count(distinct(WeatherObservation.station_id)),
                func.max(WeatherObservation.observed_at),
            )
            .join(WeatherStation, WeatherStation.id == WeatherObservation.station_id)
            .where(station_scope)
        ).one()
        latest_observation = db.execute(
            select(
                WeatherObservation.observed_at,
                WeatherObservation.received_at,
                WeatherObservation.imported_at,
                WeatherObservation.fetched_at,
                WeatherObservation.measurement_period_seconds,
            )
            .join(WeatherStation, WeatherStation.id == WeatherObservation.station_id)
            .where(station_scope)
            .order_by(WeatherObservation.observed_at.desc())
            .limit(1)
        ).one_or_none()
        exact_row = db.execute(
            select(
                func.count(WeatherExactModelBundle.id),
                func.count(distinct(WeatherExactModelBundle.target_id)),
            )
            .join(WeatherStation, WeatherStation.id == WeatherExactModelBundle.target_id)
            .where(
                station_scope,
                WeatherExactModelBundle.target_kind == "station",
            )
        ).one()
        residual_rows = db.execute(
            select(
                WeatherStationModelResidual.qc_status,
                func.count(WeatherStationModelResidual.id),
            )
            .join(WeatherStation, WeatherStation.id == WeatherStationModelResidual.station_id)
            .where(station_scope)
            .group_by(WeatherStationModelResidual.qc_status)
        ).all()
        activation_eligible = db.scalar(
            select(func.count())
            .select_from(WeatherStationModelResidual)
            .join(WeatherStation, WeatherStation.id == WeatherStationModelResidual.station_id)
            .where(station_scope, WeatherStationModelResidual.activation_eligible.is_(True))
        ) or 0
        database_size_bytes = db.scalar(
            select(func.pg_database_size(func.current_database()))
        ) or 0
    return {
        "stations": stations,
        "observations": observation_row[0],
        "stations_with_observations": observation_row[1],
        "latest_observation_at": (
            observation_row[2].isoformat() if observation_row[2] else None
        ),
        "latest_observation_received_at": (
            latest_observation.received_at.isoformat()
            if latest_observation and latest_observation.received_at else None
        ),
        "latest_observation_imported_at": (
            latest_observation.imported_at.isoformat()
            if latest_observation and latest_observation.imported_at else None
        ),
        "latest_observation_fetched_at": (
            latest_observation.fetched_at.isoformat()
            if latest_observation and latest_observation.fetched_at else None
        ),
        "latest_observation_measurement_period_seconds": (
            latest_observation.measurement_period_seconds if latest_observation else None
        ),
        "exact_bundles": exact_row[0],
        "stations_with_exact_bundles": exact_row[1],
        "residuals": {status: count for status, count in residual_rows},
        "activation_eligible_residuals": activation_eligible,
        "database_size_bytes": database_size_bytes,
    }


def health_status(report: dict, *, now: datetime | None = None) -> dict:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    campaign = load_campaign()
    database = report.get("database") or {}
    failures = []
    freshness: dict[str, object] = {
        "limit_minutes": campaign.freshness_limit_minutes,
    }
    if report.get("phase") == "active":
        if database.get("stations", 0) < min(200, campaign.station_limit):
            failures.append("station_coverage_below_200")
        if database.get("observations", 0) < 1:
            failures.append("observations_missing")
        latest = database.get("latest_observation_at")
        if latest is None:
            failures.append("latest_observation_missing")
        else:
            latest_at = datetime.fromisoformat(latest)
            age_seconds = (instant - latest_at).total_seconds()
            freshness["observation_age_seconds"] = int(age_seconds)
            if age_seconds < -300:
                failures.append("latest_observation_clock_skew_future")
            elif age_seconds > campaign.freshness_limit_minutes * 60:
                failures.append("latest_observation_older_than_3h")
            received = database.get("latest_observation_received_at")
            imported = database.get("latest_observation_imported_at")
            if received:
                received_at = datetime.fromisoformat(received)
                freshness["provider_receive_lag_seconds"] = int(
                    (received_at - latest_at).total_seconds()
                )
                if received_at < latest_at:
                    failures.append("latest_observation_received_before_observed")
            if imported:
                imported_at = datetime.fromisoformat(imported)
                freshness["processing_lag_seconds"] = int(
                    (imported_at - datetime.fromisoformat(received or latest)).total_seconds()
                )
                if received and imported_at < datetime.fromisoformat(received):
                    failures.append("latest_observation_imported_before_received")
        if database.get("exact_bundles", 0) < 1:
            failures.append("exact_bundles_missing")
        comparable = (database.get("residuals") or {}).get("degraded", 0)
        if instant >= campaign.starts_at + timedelta(hours=6) and comparable < 1:
            failures.append("comparable_residuals_missing")
    if database.get("activation_eligible_residuals", 0):
        failures.append("public_activation_boundary_violated")
    if database.get("database_size_bytes", 0) >= 900_000_000:
        failures.append("database_storage_above_900mb")
    return {
        "status": "healthy" if not failures else "failed",
        "failures": failures,
        "freshness": freshness,
    }


def status(*, now: datetime | None = None) -> dict:
    campaign = load_campaign()
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    phase = campaign.phase(instant)
    remaining = max(0, int((campaign.ends_at - instant).total_seconds()))
    return {
        "campaign_id": campaign.campaign_id,
        "phase": phase,
        "starts_at": campaign.starts_at.isoformat(),
        "ends_at": campaign.ends_at.isoformat(),
        "remaining_seconds": remaining,
        "provider": campaign.provider,
        "mode": campaign.mode,
        "public_effect": campaign.public_effect,
        "message": (
            "Europa-Windmessung beendet: Auswertung und Coverage-Pruefung ausfuehren."
            if phase == "ended"
            else "Europa-Windmessung laeuft im Shadow-Modus."
            if phase == "active"
            else f"Europa-Windmessung ist {phase}."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-check", action="store_true")
    parser.add_argument("--require-active", action="store_true")
    parser.add_argument("--database", action="store_true")
    parser.add_argument("--require-healthy", action="store_true")
    args = parser.parse_args()
    report = status()
    if args.database or args.require_healthy:
        report["database"] = database_status(report["campaign_id"])
    if args.require_healthy:
        report["health"] = health_status(report)
    if args.session_check:
        print(report["message"])
        print(f"Messungsende: {report['ends_at']}")
    else:
        print(json.dumps(report, sort_keys=True))
    if args.require_active and report["phase"] != "active":
        raise SystemExit(3)
    if args.require_healthy and report["health"]["status"] != "healthy":
        raise SystemExit(4)


if __name__ == "__main__":
    main()
