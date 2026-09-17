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

from sqlalchemy import func, select

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Spot, WeatherStation
from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader, gfs_tile
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
    spots = db.execute(select(func.ST_Y(Spot.location), func.ST_X(Spot.location)).where(
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("capture", "residuals"))
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
        else:
            result = run_station_model_error_analysis(
                db, loader, limit=cfg.weather_observation_cron_batch_size,
                dry_run=args.dry_run,
                recent_hours=48,
                skip_exact_attempted=True,
                require_exact=True,
            )
    print(json.dumps(result, sort_keys=True, default=str))
    if result.get("errors") or result.get("status") == "provider_unavailable":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
