"""Discover, process and optionally activate one free DWD wave-field run."""

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
from app.spatial_fields.forecast_profile import (
    configured_wave_hours,
    forecast_hours_for_model,
)
from app.spatial_fields.pipeline import process_run, provider_for_model
from app.spatial_fields.storage import configured_field_storage


def _configured_hours(settings, model_key: str) -> list[int]:
    return configured_wave_hours(settings, model_key)


def publish_wave_run(
    *,
    model_key: str,
    activate: bool,
    hours: list[int] | None = None,
    now: datetime | None = None,
) -> dict:
    settings = get_settings()
    settings.weather_field_auto_activate = activate
    forecast_hours = forecast_hours_for_model(
        model_key, hours if hours is not None else _configured_hours(settings, model_key)
    )
    if not forecast_hours:
        raise ValueError("wave publication requires at least one forecast hour")
    provider = provider_for_model(model_key, settings=settings)
    instant = now or datetime.now(timezone.utc)
    model_run_at = provider.discover_latest(
        instant, forecast_hours=forecast_hours
    )
    if model_run_at is None:
        raise RuntimeError(f"no complete {model_key} run was discovered")

    with SessionLocal() as db:
        models = sync_free_model_catalog(db)
        model = next(row for row in models if row.model_key == model_key)
        run = get_or_create_run(
            db,
            model=model,
            model_run_at=model_run_at,
            processing_version=settings.wave_field_processing_version,
            contract_version="weather-field-v2",
            coverage={
                "west": provider.coverage[0],
                "south": provider.coverage[1],
                "east": provider.coverage[2],
                "north": provider.coverage[3],
            },
            native_grid={"status": "pending_source_inspection"},
            valid_times=[
                (model_run_at + timedelta(hours=hour))
                .isoformat()
                .replace("+00:00", "Z")
                for hour in forecast_hours
            ],
            source_metadata={"discovered_by": "wave-field-publish"},
        )
        db.commit()
        if run.status != "discovered":
            return {
                "model": model_key,
                "model_run": model_run_at.isoformat(),
                "run_id": str(run.id),
                "run_status": run.status,
                "reused": True,
            }
        result = process_run(
            db,
            run.id,
            provider=provider,
            storage=configured_field_storage(),
            settings=settings,
        )
        return {
            "model": model_key,
            "model_run": model_run_at.isoformat(),
            "forecast_hours": len(forecast_hours),
            **result,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        choices=("dwd-ewam", "dwd-gwam", "noaa-gfs-wave"),
        default="dwd-ewam",
    )
    parser.add_argument(
        "--hours",
        help="Optional comma-separated forecast hours; defaults to the model profile.",
    )
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    hours = (
        sorted({int(value.strip()) for value in args.hours.split(",") if value.strip()})
        if args.hours
        else None
    )
    result = publish_wave_run(
        model_key=args.model,
        activate=args.activate,
        hours=hours,
    )
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
