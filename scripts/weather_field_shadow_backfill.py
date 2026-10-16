"""Enqueue one explicit historical weather-field cycle for shadow evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.spatial_fields.catalog import sync_free_model_catalog
from app.spatial_fields.control_plane import get_or_create_run
from app.spatial_fields.jobs import enqueue_process_run
from app.spatial_fields.providers import EUROPE_COVERAGE


def _utc_cycle(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise argparse.ArgumentTypeError("model run must be timezone-aware UTC")
    if parsed.minute or parsed.second or parsed.microsecond or parsed.hour % 6:
        raise argparse.ArgumentTypeError("model run must be an exact six-hour cycle")
    if parsed > datetime.now(timezone.utc):
        raise argparse.ArgumentTypeError("model run cannot be in the future")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-run", required=True, type=_utc_cycle)
    parser.add_argument("--processing-version", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if not settings.weather_field_pipeline_enabled:
        parser.error("WEATHER_FIELD_PIPELINE_ENABLED must be true")
    if settings.weather_field_auto_activate:
        parser.error("shadow backfill refuses WEATHER_FIELD_AUTO_ACTIVATE=true")

    with SessionLocal() as db:
        model = next(
            row
            for row in sync_free_model_catalog(db)
            if row.model_key == "icon-eu" and row.status == "active"
        )
        valid_times = [
            (args.model_run + timedelta(hours=hour))
            .isoformat()
            .replace("+00:00", "Z")
            for hour in settings.weather_field_forecast_hours
            if hour <= model.max_horizon_hours
        ]
        west, south, east, north = EUROPE_COVERAGE
        run = get_or_create_run(
            db,
            model=model,
            model_run_at=args.model_run,
            processing_version=args.processing_version,
            contract_version="weather-field-v2",
            coverage={"west": west, "south": south, "east": east, "north": north},
            native_grid={"status": "pending_source_inspection"},
            valid_times=valid_times,
            source_metadata={
                "discovered_by": "weather-field-shadow-backfill",
                "backfill": True,
            },
        )
        job, created = enqueue_process_run(db, run)
        db.commit()
        print(
            json.dumps(
                {
                    "run_id": str(run.id),
                    "job_id": str(job.id),
                    "job_created": created,
                    "model_run": args.model_run.isoformat(),
                    "processing_version": run.processing_version,
                    "valid_times": len(run.valid_times),
                    "public_effect": "none",
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
