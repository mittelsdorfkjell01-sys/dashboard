"""Fail-closed non-production station capture control plane.

This worker stores only station catalog/observation evidence. Exact model assets
are captured by ``scripts.exact_run_worker capture`` immediately before the
observation command in the scheduler. It never builds residuals, holdouts,
LiveWind analyses, forecasts, or public activation state.
"""

from __future__ import annotations

import argparse
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
        elif command == "status":
            result = station_report(db)
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
        "command", choices=("catalog", "observations", "status", "pause", "resume")
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


if __name__ == "__main__":
    main()
