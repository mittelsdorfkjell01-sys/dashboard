"""Capture exact raw wind assets and persist bounded point evidence.

The hosted ``capture`` schedule may use a job-local raw-asset cache because it
persists compact point bundles in PostgreSQL. Its companion schedule runs
``persisted-residuals`` and reads those bundles without the raw cache. The
legacy direct ``residuals`` path still requires the same read/write cache as the
capture process. This script never changes public API products.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math

from sqlalchemy import func, select, text

from app.config import get_settings
from app.db.schema import EXPECTED_DB_REVISION
from app.db.session import SessionLocal
from app.models import Spot, WeatherStation
from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader, gfs_tile
from app.weather.exact_points import persist_exact_point_bundle
from app.weather.model_error import run_station_model_error_analysis


def capture_exact_cycle(
    db,
    loader: ExactRunLoader,
    *,
    now: datetime,
    limit: int,
    point_limit: int | None = None,
) -> dict:
    instant = now.astimezone(timezone.utc)
    run_at = instant.replace(hour=instant.hour - instant.hour % 6, minute=0, second=0, microsecond=0) - timedelta(hours=6)
    first = max(0, int((instant-run_at).total_seconds() // 3600))
    hours = tuple(range(first, first + 4))
    stations = db.execute(select(
        WeatherStation.id, WeatherStation.latitude, WeatherStation.longitude
    ).where(
        WeatherStation.active.is_(True), WeatherStation.approved.is_(True),
        WeatherStation.residual_approved.is_(True), WeatherStation.blocked.is_(False),
    )).all()
    spots = db.execute(select(
        Spot.id, func.ST_Y(Spot.location), func.ST_X(Spot.location)
    ).where(
        Spot.status == "published", Spot.location.is_not(None),
    )).all()
    targets = []
    for kind, rows in (("station", stations), ("spot", spots)):
        for identifier, lat, lon in rows:
            if lat is None or lon is None or not math.isfinite(lat) or not math.isfinite(lon):
                continue
            targets.append((kind, identifier, float(lat), float(lon)))
    targets.sort(key=lambda item: (item[0], str(item[1])))
    if not targets:
        return {"tiles": 0, "assets": 0, "errors": {}, "status": "no_locations"}
    point_limit = max(1, point_limit or limit)
    cycle = int(instant.timestamp() // 600)
    offset = (cycle * point_limit) % len(targets)
    rotated = targets[offset:] + targets[:offset]
    selected_targets = []
    tiles: dict[tuple[float, float, float, float], tuple[float, float]] = {}
    for target in rotated:
        _kind, _identifier, lat, lon = target
        tile = gfs_tile(lat, lon)
        if tile not in tiles and len(tiles) >= limit:
            continue
        tiles[tile] = ((tile[2]+tile[3])/2, (tile[0]+tile[1])/2)
        selected_targets.append(target)
        if len(selected_targets) >= point_limit:
            break
    reports = [loader.capture(run_at=run_at, forecast_hours=hours,
                              latitude=tiles[tile][0], longitude=tiles[tile][1],
                              verify_existing=instant.minute < 10)
               for tile in sorted(tiles)]
    errors = {}
    provider_duration_ms = {}
    for report in reports:
        for model, failures in report["errors"].items():
            errors[model] = errors.get(model, 0) + len(failures)
        for model, duration in report["provider_duration_ms"].items():
            provider_duration_ms[model] = provider_duration_ms.get(model, 0) + duration
    captured_at = datetime.now(timezone.utc)
    point_report = {
        "targets": len(selected_targets), "bundles_inserted": 0,
        "points_inserted": 0, "ineligible": 0, "errors": 0,
    }
    for kind, identifier, latitude, longitude in selected_targets:
        try:
            bundle = loader.bundle(
                valid_at=instant,
                latitude=latitude,
                longitude=longitude,
                as_of=captured_at,
            )
            baseline = loader.sample(
                bundle, latitude=latitude, longitude=longitude
            )
            with db.begin_nested():
                persisted = persist_exact_point_bundle(
                    db,
                    target_kind=kind,
                    target_id=identifier,
                    latitude=latitude,
                    longitude=longitude,
                    sampled_for_at=instant,
                    captured_at=captured_at,
                    baseline=baseline,
                )
            point_report["bundles_inserted"] += persisted["bundle_inserted"]
            point_report["points_inserted"] += persisted["points_inserted"]
            point_report["ineligible"] += int(persisted["status"] != "persisted")
        except Exception:
            point_report["errors"] += 1
    db.commit()
    return {"tiles": len(tiles), "total_targets": len(targets),
            "assets": sum(report["assets"] for report in reports),
            "cache_hits": sum(report["cache_hits"] for report in reports),
            "cache_misses": sum(report["cache_misses"] for report in reports),
            "provider_duration_ms": provider_duration_ms,
            "errors": errors, "run_at": run_at.isoformat(), "forecast_hours": hours,
            "point_samples": point_report,
            "status": (
                "available"
                if not errors and not point_report["errors"]
                else "provider_unavailable"
            )}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage", choices=("capture", "residuals", "persisted-residuals")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cfg = get_settings()
    if args.stage != "persisted-residuals" and not cfg.live_wind_exact_run_cache_dir:
        raise SystemExit("LIVE_WIND_EXACT_RUN_CACHE_DIR must be a persistent shared mount")
    loader = None
    if args.stage != "persisted-residuals":
        loader = ExactRunLoader(ExactRunAssetCache(
            cfg.live_wind_exact_run_cache_dir,
            require_persistent=cfg.app_env == "production" or cfg.live_wind_canary_mode,
            expected_id=cfg.live_wind_exact_run_cache_id,
            minimum_free_bytes=cfg.live_wind_exact_run_min_free_bytes,
        ))
    with SessionLocal() as db:
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != EXPECTED_DB_REVISION:
            raise SystemExit(
                f"database migration head {revision!r} is not {EXPECTED_DB_REVISION}"
            )
        if args.stage == "capture":
            if args.dry_run:
                result = {"status": "dry_run", "cache_dir_configured": True}
            else:
                result = capture_exact_cycle(db, loader, now=datetime.now(timezone.utc),
                                             limit=cfg.live_wind_exact_capture_tile_limit,
                                             point_limit=cfg.live_wind_exact_point_batch_size)
        elif args.stage == "residuals":
            result = run_station_model_error_analysis(
                db, loader, limit=cfg.weather_observation_cron_batch_size,
                dry_run=args.dry_run,
                recent_hours=48,
                skip_exact_attempted=True,
                require_exact=True,
            )
        else:
            from app.weather.exact_points import PersistedStationBaselineLoader

            result = run_station_model_error_analysis(
                db,
                PersistedStationBaselineLoader(db),
                limit=cfg.weather_observation_cron_batch_size,
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
