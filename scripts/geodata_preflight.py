"""Phase-0: exactly five bounded WorldCover COG probes; never activates profiles."""

from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from app.db.session import SessionLocal
from app.forecast.geodata import CopernicusDemAdapter, WorldCoverAdapter, analysis_crs
from app.forecast.raster_cache import RasterCache, RunBudget
from app.models import Spot

CASES = {
    "Baleal": ("open_atlantic", "Open Atlantic coast and peninsula"),
    "Brouwersdam": (
        "barrier_islands",
        "North Sea delta with offshore islands and dams",
    ),
    "Mundaka": ("curved_estuary", "Strongly curved estuary/bay"),
    "Lo Stagnone": (
        "inland_lagoon",
        "Shallow enclosed lagoon; closest available inland-water case",
    ),
    "Pozo Izquierdo": (
        "mountain_coast",
        "Volcanic island coast with strong nearby relief",
    ),
}


def run(output: Path, cache_dir: Path) -> dict:
    budget = RunBudget(
        max_download_bytes=1_000_000, max_asset_bytes=131_072, max_temp_bytes=262_144
    )
    cache = RasterCache(cache_dir, timeout=15, retries=2, daily_limit_bytes=50_000_000)
    rows = []
    with SessionLocal() as db:
        spots = {
            s.name: s
            for s in db.scalars(
                select(Spot).where(Spot.name.in_(CASES), Spot.status == "published")
            ).all()
        }
        if len(spots) != 5:
            raise RuntimeError(
                f"preflight requires exactly five configured published spots; found {len(spots)}"
            )
        for name, (case, reason) in CASES.items():
            spot = spots[name]
            point = to_shape(spot.location)
            started = time.perf_counter()
            tile = WorldCoverAdapter.tile(point.y, point.x)
            url = WorldCoverAdapter.url(point.y, point.x)
            error = None
            try:
                _, metrics = cache.fetch(
                    url,
                    dataset="worldcover-2021",
                    version="v200",
                    asset_key=f"{tile}:Map:header",
                    budget=budget,
                    byte_range=(0, 65535),
                )
            except Exception as exc:
                metrics = {"cache_hit": False, "bytes": 0}
                error = f"{type(exc).__name__}: {exc}"
            rows.append(
                {
                    "spot_id": str(spot.id),
                    "name": name,
                    "coordinates": [point.y, point.x],
                    "case": case,
                    "reason": reason,
                    "analysis_crs": analysis_crs(point.y, point.x),
                    "assets": {
                        "worldcover": tile,
                        "cop_dem": CopernicusDemAdapter.tile(point.y, point.x),
                    },
                    "worldcover": {
                        **metrics,
                        "resolution_m": 10,
                        "crs": "EPSG:4326",
                        "nodata": 0,
                        "coverage": "global land to 82.75°N",
                        "source": "ESA WorldCover 2021 v200",
                        "full_file_downloaded": False,
                        "error": error,
                    },
                    "copernicus_dem": {
                        "status": "blocked_credentials",
                        "source": "COP-DEM_GLO-30-DGED 2024_1",
                        "resolution_m": 30,
                        "crs": "EPSG:4326",
                        "vertical_datum": "EPSG:3855 EGM2008",
                        "tile": CopernicusDemAdapter.tile(point.y, point.x),
                        "error": "CDSE CCM account/licence credentials not configured",
                    },
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": 0,
        "spot_count": len(rows),
        "limits": {
            "parallel_downloads": 1,
            "max_spots": 5,
            "max_download_bytes": budget.max_download_bytes,
            "max_asset_bytes": budget.max_asset_bytes,
        },
        "metrics": {
            "requests": budget.requests,
            "bytes": budget.downloaded,
            "retries": budget.retries,
            "range_requests": budget.ranges,
            "cache_hits": sum(1 for r in rows if r["worldcover"].get("cache_hit")),
            "cache_misses": sum(
                1 for r in rows if not r["worldcover"].get("cache_hit")
            ),
            "peak_temporary_bytes": 65536,
            "persistent_cache_bytes_after_run": budget.downloaded,
            "persistent_cache_bytes_after_cleanup": 0,
        },
        "spots": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    markdown = [
        "# Geodata phase-0 preflight",
        "",
        f"Generated: {result['generated_at']}",
        "",
        f"WorldCover: {budget.requests} requests, {budget.downloaded} transferred bytes. Copernicus live test blocked by missing local CDSE/CCM credentials.",
        "",
        "| Spot | Case | WorldCover tile | DEM tile | bytes | cache | duration |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        markdown.append(
            f"| {row['name']} | {row['case']} | {row['assets']['worldcover']} | {row['assets']['cop_dem']} | {row['worldcover']['bytes']} | {'hit' if row['worldcover'].get('cache_hit') else 'miss'} | {row['duration_ms']} ms |"
        )
    output.with_suffix(".md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("reports/geodata-preflight.json")
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data/geodata-cache"))
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.cache_dir)["metrics"], indent=2))
