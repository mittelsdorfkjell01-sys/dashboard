"""Local no-cost supervisor for the bounded Europe wind shadow campaign."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import argparse
import json
import os
import time

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    WeatherStation,
    WeatherStationCaptureCycle,
    WeatherStationCatalogState,
)
from app.weather.europe_campaign import load_campaign
from app.weather.exact_points import PersistedStationBaselineLoader
from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader
from app.weather.model_error import run_station_model_error_analysis
from app.weather.observation_worker import run_observation_import
from app.weather.station_catalog_job import run_station_catalog_refresh
from scripts.exact_run_worker import capture_exact_cycle


def _catalog_due(
    db,
    provider: str,
    now: datetime,
    *,
    campaign_id: str,
    station_limit: int,
) -> bool:
    state = db.get(WeatherStationCatalogState, provider)
    active = db.scalar(select(func.count()).select_from(WeatherStation).where(
        WeatherStation.campaign_key == campaign_id,
        WeatherStation.active.is_(True),
    )) or 0
    qualified = db.scalar(select(func.count()).select_from(WeatherStation).where(
        WeatherStation.campaign_key == campaign_id,
        WeatherStation.active.is_(True),
        WeatherStation.country_code.is_not(None),
        WeatherStation.wigos_id.is_not(None),
        WeatherStation.physical_station_group.is_not(None),
        WeatherStation.correlation_group.is_not(None),
        WeatherStation.representativeness_status != "unreviewed",
    )) or 0
    return (
        active != station_limit
        or qualified < station_limit
        or state is None
        or state.last_success_at is None
        or state.last_success_at <= now - timedelta(hours=20)
    )


def _observation_import_is_partial(report: dict) -> bool:
    """Treat any station-provider failure as a partial campaign cycle."""
    provider_reports = report.get("provider_reports") or {}
    return bool(report.get("errors")) or any(
        int(item.get("errors", 0) or 0) > 0
        for item in provider_reports.values()
    )


def _compact(report: dict | None) -> dict | None:
    """Keep the three-week worker log bounded while retaining useful counters."""
    if report is None:
        return None
    return {
        key: value
        for key, value in report.items()
        if key not in {"items", "stations", "errors_by_station"}
    }


def validate_hosted_environment(settings, environ: dict[str, str]) -> dict:
    """Fail closed before a hosted job can mutate the wrong database."""
    if environ.get("GITHUB_ACTIONS", "").casefold() != "true":
        return {"runtime": "local", "public_effect": "none"}
    expected_database = environ.get(
        "EUROPE_WIND_MEASUREMENT_DATABASE_ID", ""
    ).strip()
    actual_database = make_url(settings.database_url).database or ""
    if (
        not expected_database
        or expected_database != actual_database
        or not expected_database.startswith("surfwind_measurement_")
    ):
        raise ValueError("hosted_measurement_database_identity_mismatch")
    if settings.app_env == "production":
        raise ValueError("hosted_measurement_requires_nonproduction_app_env")
    if settings.live_wind_rollout_stage != "shadow":
        raise ValueError("hosted_measurement_requires_shadow_rollout")
    if not settings.live_wind_force_baseline:
        raise ValueError("hosted_measurement_requires_forced_public_baseline")
    if settings.live_wind_enabled_region_slugs:
        raise ValueError("hosted_measurement_requires_empty_public_region_allowlist")
    return {
        "runtime": "github_actions",
        "database_id": expected_database,
        "public_effect": "none",
    }


def run_cycle(*, now: datetime | None = None) -> dict:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    campaign = load_campaign()
    if campaign.phase(instant) != "active":
        return {
            "status": "idle", "campaign_phase": campaign.phase(instant),
            "ends_at": campaign.ends_at.isoformat(), "public_effect": "none",
        }
    settings = get_settings()
    if not settings.live_wind_exact_run_cache_dir:
        raise ValueError("LIVE_WIND_EXACT_RUN_CACHE_DIR is required")
    loader = ExactRunLoader(ExactRunAssetCache(
        settings.live_wind_exact_run_cache_dir,
        require_persistent=False,
        expected_id=settings.live_wind_exact_run_cache_id,
        minimum_free_bytes=settings.live_wind_exact_run_min_free_bytes,
    ))
    slot_start = instant.replace(
        minute=(instant.minute // campaign.expected_interval_minutes)
        * campaign.expected_interval_minutes,
        second=0,
        microsecond=0,
    )
    with SessionLocal() as db:
        completed = db.scalar(select(WeatherStationCaptureCycle.id).where(
            WeatherStationCaptureCycle.job_type == "campaign",
            WeatherStationCaptureCycle.started_at >= slot_start,
            WeatherStationCaptureCycle.started_at < (
                slot_start + timedelta(minutes=campaign.expected_interval_minutes)
            ),
            WeatherStationCaptureCycle.status == "success",
        ).limit(1))
        if completed is not None:
            return {
                "status": "duplicate_slot_skipped",
                "campaign_phase": "active",
                "scheduled_slot": slot_start.isoformat(),
                "ends_at": campaign.ends_at.isoformat(),
                "public_effect": "none",
            }
        started_at = datetime.now(timezone.utc)
        try:
            catalog = None
            if _catalog_due(
                db,
                campaign.provider,
                instant,
                campaign_id=campaign.campaign_id,
                station_limit=campaign.station_limit,
            ):
                catalog = run_station_catalog_refresh(
                    db,
                    providers=(campaign.provider,),
                    dry_run=False,
                    force=True,
                    bounds=campaign.bounds,
                )
            exact = capture_exact_cycle(
                db,
                loader,
                now=instant,
                limit=settings.live_wind_exact_capture_tile_limit,
                point_limit=settings.live_wind_exact_point_batch_size,
                campaign_only=True,
            )
            observations = run_observation_import(
                db,
                providers=(campaign.provider,),
                limit=settings.weather_observation_cron_batch_size,
                dry_run=False,
                capture_mode="operational",
            )
            residuals = run_station_model_error_analysis(
                db,
                PersistedStationBaselineLoader(db),
                limit=settings.weather_observation_cron_batch_size,
                recent_hours=48,
                skip_exact_attempted=True,
                require_exact=True,
                campaign_key=campaign.campaign_id,
            )
            partial = (
                exact.get("status") != "available"
                or _observation_import_is_partial(observations)
            )
            db.add(WeatherStationCaptureCycle(
                job_type="campaign",
                provider=campaign.provider,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status="partial" if partial else "success",
                counts={
                    "campaign_id": campaign.campaign_id,
                    "scheduled_slot": slot_start.isoformat(),
                    "exact_targets": (exact.get("point_samples") or {}).get("targets", 0),
                    "exact_bundles_inserted": (
                        exact.get("point_samples") or {}
                    ).get("bundles_inserted", 0),
                },
            ))
            db.commit()
        except Exception as exc:
            db.rollback()
            db.add(WeatherStationCaptureCycle(
                job_type="campaign",
                provider=campaign.provider,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status="error",
                counts={
                    "campaign_id": campaign.campaign_id,
                    "scheduled_slot": slot_start.isoformat(),
                    "error_class": type(exc).__name__,
                },
            ))
            db.commit()
            raise
    return {
        "status": "ok",
        "campaign_phase": "active",
        "scheduled_slot": slot_start.isoformat(),
        "ends_at": campaign.ends_at.isoformat(),
        "catalog": _compact(catalog),
        "exact": _compact(exact),
        "observations": _compact(observations),
        "residuals": _compact(residuals),
        "public_effect": "none",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    campaign = load_campaign()
    settings = get_settings()
    identity = validate_hosted_environment(settings, dict(os.environ))
    if args.validate_only:
        print(json.dumps({"status": "ready", **identity}, sort_keys=True))
        return
    if args.once:
        report = run_cycle()
        report["runtime"] = identity["runtime"]
        print(json.dumps(report, sort_keys=True, default=str), flush=True)
        if report.get("status") == "failed":
            raise SystemExit(1)
        return
    while True:
        started = datetime.now(timezone.utc)
        try:
            report = run_cycle(now=started)
        except Exception as exc:
            report = {
                "status": "failed",
                "error_class": type(exc).__name__,
                "campaign_phase": campaign.phase(started),
                "public_effect": "none",
            }
        print(json.dumps(report, sort_keys=True, default=str), flush=True)
        if report.get("campaign_phase") == "ended":
            # Keep the restart-safe container almost completely idle. The next
            # development session provides the human-facing completion reminder.
            time.sleep(6 * 3600)
            continue
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        time.sleep(max(60, 30 * 60 - elapsed))


if __name__ == "__main__":
    main()
