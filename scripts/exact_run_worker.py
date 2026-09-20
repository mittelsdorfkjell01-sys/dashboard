"""Pre-capture exact raw wind assets, then drain station residual evidence.

Run `capture` before importing observations and `residuals` afterwards. The
cache directory must be a persistent read/write mount shared with the LiveWind
shadow worker. This script never changes public API products.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math

from geoalchemy2 import Geometry
from sqlalchemy import func, select

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Spot, WeatherStation
from app.weather.exact_run import (
    EXPECTED_MODELS,
    ExactRunAssetCache,
    ExactRunLoader,
    gfs_tile,
)
from app.weather.model_error import run_station_model_error_analysis


def capture_exact_cycle(db, loader: ExactRunLoader, *, now: datetime, limit: int) -> dict:
    instant = now.astimezone(timezone.utc)
    run_at = instant.replace(hour=instant.hour - instant.hour % 6, minute=0, second=0, microsecond=0) - timedelta(hours=6)
    first = max(0, int((instant-run_at).total_seconds() // 3600))
    hours = tuple(range(first, first + 4))
    stations = db.execute(select(WeatherStation.latitude, WeatherStation.longitude).where(
        WeatherStation.active.is_(True), WeatherStation.approved.is_(True),
        WeatherStation.blocked.is_(False),
    )).all()
    point = Spot.location.cast(Geometry(geometry_type="POINT", srid=4326))
    spots = db.execute(select(func.ST_Y(point), func.ST_X(point)).where(
        Spot.status == "published", Spot.location.is_not(None),
    )).all()
    tiles = {}
    for lat, lon in [*stations, *spots]:
        if lat is None or lon is None or not math.isfinite(lat) or not math.isfinite(lon):
            continue
        tile = gfs_tile(float(lat), float(lon))
        tiles[tile] = ((tile[2]+tile[3])/2, (tile[0]+tile[1])/2)
    ordered = sorted(tiles)
    if not ordered:
        return {"tiles": 0, "assets": 0, "errors": {}, "status": "no_locations"}
    # Rotate deterministically by cycle, so a bounded run cannot permanently
    # starve the same tail of the catalogue.
    cycle = int(instant.timestamp() // 600)
    offset = (cycle * limit) % len(ordered)
    selected = (ordered[offset:] + ordered[:offset])[:limit]
    reports = [loader.capture(run_at=run_at, forecast_hours=hours,
                              latitude=tiles[tile][0], longitude=tiles[tile][1],
                              verify_existing=instant.minute < 10)
               for tile in selected]
    errors = {}
    provider_duration_ms = {}
    for report in reports:
        for model, failures in report["errors"].items():
            errors[model] = errors.get(model, 0) + len(failures)
        for model, duration in report["provider_duration_ms"].items():
            provider_duration_ms[model] = provider_duration_ms.get(model, 0) + duration
    return {"tiles": len(selected), "total_tiles": len(ordered),
            "assets": sum(report["assets"] for report in reports),
            "cache_hits": sum(report["cache_hits"] for report in reports),
            "cache_misses": sum(report["cache_misses"] for report in reports),
            "provider_duration_ms": provider_duration_ms,
            "errors": errors, "run_at": run_at.isoformat(), "forecast_hours": hours,
            "status": "available" if not errors else "provider_unavailable"}


def exact_capture_status(loader: ExactRunLoader, *, now: datetime | None = None) -> dict:
    """Report model-specific asset freshness from immutable cache manifests."""
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    inventory = loader.cache.inventory()
    models = {}
    alerts = []
    for model in EXPECTED_MODELS:
        assets = [item for item in inventory if item.model == model]
        first_seen = max(
            (item.first_seen_at for item in assets if item.first_seen_at), default=None
        )
        age_hours = (
            round((instant - first_seen).total_seconds() / 3600, 2)
            if first_seen else None
        )
        models[model] = {
            "assets": len(assets),
            "latest_run_at": max((item.run_at for item in assets), default=None),
            "latest_first_seen_at": first_seen,
            "age_hours": age_hours,
        }
        if not assets:
            alerts.append({"severity": "critical", "code": "model_assets_missing", "model": model})
        elif first_seen is None:
            alerts.append({"severity": "critical", "code": "model_first_seen_missing", "model": model})
        elif age_hours is not None and age_hours > 10:
            alerts.append({"severity": "critical", "code": "model_capture_stale", "model": model})
    return {
        "status": "healthy" if not alerts else "alert",
        "generated_at": instant,
        "freshness_threshold_hours": 10,
        "models": models,
        "alerts": alerts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("capture", "residuals", "status"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cfg = get_settings()
    if not cfg.live_wind_exact_run_cache_dir:
        raise SystemExit("LIVE_WIND_EXACT_RUN_CACHE_DIR must be a persistent shared mount")
    loader = ExactRunLoader(ExactRunAssetCache(
        cfg.live_wind_exact_run_cache_dir,
        require_persistent=cfg.app_env == "production" or cfg.live_wind_canary_mode,
        expected_id=cfg.live_wind_exact_run_cache_id,
        minimum_free_bytes=cfg.live_wind_exact_run_min_free_bytes,
    ))
    with SessionLocal() as db:
        if args.stage == "capture":
            if args.dry_run:
                result = {"status": "dry_run", "cache_dir_configured": True}
            else:
                result = capture_exact_cycle(db, loader, now=datetime.now(timezone.utc),
                                             limit=cfg.live_wind_exact_capture_tile_limit)
        elif args.stage == "residuals":
            result = run_station_model_error_analysis(
                db, loader, limit=cfg.weather_observation_cron_batch_size,
                dry_run=args.dry_run,
                recent_hours=48,
                skip_exact_attempted=True,
                require_exact=True,
            )
        else:
            result = exact_capture_status(loader)
    print(json.dumps(result, sort_keys=True, default=str))
    if result.get("errors") or result.get("status") in {"provider_unavailable", "alert"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
