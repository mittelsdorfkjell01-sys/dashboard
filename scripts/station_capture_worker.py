"""Fail-closed non-production station capture control plane.

This worker stores only station catalog/observation evidence. Exact model assets
are captured by ``scripts.exact_run_worker capture`` immediately before the
observation command in the scheduler. It never builds residuals, holdouts,
LiveWind analyses, forecasts, or public activation state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from urllib.parse import urlsplit

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import WeatherStationProviderCursor
from app.weather.observation_worker import run_observation_import
from app.weather.station_catalog_job import run_station_catalog_refresh
from app.weather.station_report import station_report


PROVIDERS = ("dwd", "dmi")
CATALOG_MAX_AGE_HOURS = 36
OBSERVATION_MAX_AGE_MINUTES = 90
CAPTURE_CYCLE_MAX_AGE_MINUTES = 30


def capture_health(report: dict, *, now: datetime | None = None) -> dict:
    """Evaluate provider-specific capture freshness without hiding gaps."""
    instant = now or datetime.now(timezone.utc)
    alerts = []
    cycles = report.get("continuous_capture", {}).get("cycle_status", {})
    catalogs = report.get("catalogs", {})
    providers = report.get("providers", {})
    cursors = report.get("provider_cursors", {})
    for provider in PROVIDERS:
        catalog = catalogs.get(provider)
        if not catalog or catalog.get("last_success_at") is None:
            alerts.append({"severity": "critical", "code": "catalog_never_succeeded", "provider": provider})
        elif float(catalog.get("age_hours") or 0) > CATALOG_MAX_AGE_HOURS:
            alerts.append({"severity": "critical", "code": "catalog_stale", "provider": provider})

        metrics = providers.get(provider) or {}
        if int(metrics.get("operational_observations_24h") or 0) == 0:
            alerts.append({"severity": "critical", "code": "operational_observation_missing", "provider": provider})
        age = metrics.get("latest_observation_age_minutes")
        if age is None or float(age) > OBSERVATION_MAX_AGE_MINUTES:
            alerts.append({"severity": "critical", "code": "observation_stale", "provider": provider})

        cycle = cycles.get(f"observations:{provider}") or {}
        last_success = cycle.get("last_success_at")
        try:
            cycle_age = (instant - datetime.fromisoformat(last_success)).total_seconds() / 60
        except (TypeError, ValueError):
            cycle_age = None
        if cycle_age is None or cycle_age > CAPTURE_CYCLE_MAX_AGE_MINUTES:
            alerts.append({"severity": "critical", "code": "observation_cycle_late", "provider": provider})
        if int(cycle.get("failures_24h") or 0):
            alerts.append({"severity": "warning", "code": "observation_cycle_failures", "provider": provider,
                           "count": int(cycle["failures_24h"])})
        if (cursors.get(provider) or {}).get("paused"):
            alerts.append({"severity": "critical", "code": "provider_paused", "provider": provider})
    return {
        "status": "healthy" if not any(item["severity"] == "critical" for item in alerts) else "alert",
        "thresholds": {
            "catalog_max_age_hours": CATALOG_MAX_AGE_HOURS,
            "observation_max_age_minutes": OBSERVATION_MAX_AGE_MINUTES,
            "capture_cycle_max_age_minutes": CAPTURE_CYCLE_MAX_AGE_MINUTES,
        },
        "alerts": alerts,
    }


def validate_capture_environment(settings, environ: dict[str, str]) -> dict:
    """Return a sanitized identity or fail before any provider/DB mutation."""
    if settings.app_env == "production":
        raise ValueError("capture_requires_nonproduction_app_env")
    if settings.live_wind_rollout_stage != "shadow":
        raise ValueError("capture_requires_shadow_rollout")
    if not settings.live_wind_force_baseline:
        raise ValueError("capture_requires_forced_public_baseline")
    if settings.live_wind_enabled_region_slugs:
        raise ValueError("capture_requires_empty_public_region_allowlist")
    if environ.get("LIVE_WIND_CAPTURE_AUTHORIZED", "").casefold() != "true":
        raise ValueError("capture_environment_not_authorized")
    if environ.get("LIVE_WIND_CAPTURE_MODE") != "raw_only":
        raise ValueError("capture_mode_must_be_raw_only")
    environment_id = environ.get("LIVE_WIND_CAPTURE_ENVIRONMENT_ID", "").strip()
    database_name = urlsplit(settings.database_url).path.lstrip("/")
    if (
        not environment_id
        or environment_id != database_name
        or not environment_id.startswith(("surfwind_capture_", "surfwind_staging_"))
    ):
        raise ValueError("capture_database_identity_mismatch")
    runner_id = environ.get("LIVE_WIND_RUNNER_ID", "").strip()
    job_id = environ.get("LIVE_WIND_RUNNER_JOB_ID", "").strip()
    if not runner_id or not job_id:
        raise ValueError("capture_runner_identity_missing")
    return {
        "environment_id": environment_id,
        "runner_id": runner_id,
        "runner_job_id": job_id,
        "mode": "raw_only",
        "rollout_stage": "shadow",
        "public_effect": "none",
    }


def _code_head() -> str:
    config = Config("alembic.ini")
    return ScriptDirectory.from_config(config).get_current_head()


def _require_database_head(db) -> str:
    from sqlalchemy import text

    current = db.scalar(text("SELECT version_num FROM alembic_version"))
    expected = _code_head()
    if current != expected:
        raise ValueError(f"capture_migration_head_mismatch:{current}:{expected}")
    return expected


def run(command: str, *, limit: int = 25) -> dict:
    settings = get_settings()
    identity = validate_capture_environment(settings, dict(os.environ))
    with SessionLocal() as db:
        identity["migration_head"] = _require_database_head(db)
        if command == "catalog":
            result = run_station_catalog_refresh(
                db, providers=PROVIDERS, dry_run=False
            )
        elif command == "observations":
            result = run_observation_import(
                db,
                providers=PROVIDERS,
                limit=limit,
                dry_run=False,
                capture_mode="operational",
            )
        elif command in {"status", "doctor"}:
            result = station_report(db)
            if command == "doctor":
                result["capture_health"] = capture_health(result)
        elif command in {"pause", "resume"}:
            paused = command == "pause"
            for provider in PROVIDERS:
                cursor = (
                    db.get(WeatherStationProviderCursor, provider)
                    or WeatherStationProviderCursor(provider=provider)
                )
                cursor.paused = paused
                db.add(cursor)
            db.commit()
            result = {"providers": list(PROVIDERS), "paused": paused}
        else:
            raise ValueError("unsupported_capture_command")
    return {
        "status": "ok",
        "identity": identity,
        "command": command,
        "result": result,
        "residuals_created": 0,
        "holdouts_created": 0,
        "live_wind_analyses_created": 0,
        "public_effect": "none",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("catalog", "observations", "status", "doctor", "pause", "resume")
    )
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("positive limit required")
    try:
        report = run(args.command, limit=args.limit)
    except Exception as exc:
        report = {
            "status": "failed",
            "error_class": type(exc).__name__,
            "error": str(exc) if isinstance(exc, ValueError) else "internal_error",
            "public_effect": "none",
        }
        print(json.dumps(report, sort_keys=True, default=str))
        raise SystemExit(1) from exc
    print(json.dumps(report, sort_keys=True, default=str))
    if (
        args.command == "doctor"
        and report.get("result", {}).get("capture_health", {}).get("status") != "healthy"
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
