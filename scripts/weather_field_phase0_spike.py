"""Run the isolated, non-production ICON-EU weather-field phase-0 spike."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forecast.providers import DwdIconProvider  # noqa: E402
from app.spatial_fields.contracts_v2 import (  # noqa: E402
    FieldManifestV2,
    WIND_COMPONENT_SCALE_MS_V2,
    classify_freshness,
)
from app.spatial_fields.phase0 import (  # noqa: E402
    assert_same_grid,
    decode_regular_latlon,
    project_xyz_tile,
    xyz_pixel_lonlat,
    xyz_tiles_for_bounds,
)
from app.spatial_fields.sampling import bilinear_uv  # noqa: E402
from app.spatial_fields.tile_codec import (  # noqa: E402
    TileVariable,
    decode_field_tile,
    encode_field_tile,
    sha256_hex,
)


EUROPE = (-23.5, 29.5, 45.0, 70.5)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def latest_available_run(provider: DwdIconProvider, now: datetime) -> datetime:
    candidate = now.replace(minute=0, second=0, microsecond=0)
    candidate = candidate.replace(hour=(candidate.hour // 6) * 6)
    for offset in range(0, 31, 6):
        run = candidate - timedelta(hours=offset)
        try:
            response = provider.client.head(
                provider.file_url("icon-eu", run, "u_10m", 0),
                timeout=provider.timeout,
                follow_redirects=True,
            )
            if response.status_code == 200:
                return run
        except httpx.HTTPError:
            continue
    raise RuntimeError("no recent ICON-EU run was discoverable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-at", help="UTC model run, e.g. 2026-10-01T18:00:00Z")
    parser.add_argument("--forecast-hour", type=int, default=0)
    parser.add_argument("--zoom", type=int, default=4)
    parser.add_argument("--tile-size", type=int, default=128)
    parser.add_argument("--overlap", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("data/weather-field-phase0"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider = DwdIconProvider(timeout=45, max_bytes=4_000_000)
    run = (
        datetime.fromisoformat(args.run_at.replace("Z", "+00:00"))
        if args.run_at
        else latest_available_run(provider, datetime.now(timezone.utc))
    )
    if run.tzinfo is None or run.utcoffset() != timedelta(0):
        raise ValueError("--run-at must be timezone-aware UTC")
    valid_time = run + timedelta(hours=args.forecast_hour)
    publication_id = f"icon-eu-{run:%Y%m%dT%HZ}-f{args.forecast_hour:03d}-phase0"
    root = args.output_dir / publication_id
    root.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    t0 = perf_counter()
    raw: dict[str, bytes] = {}
    urls: dict[str, str] = {}
    compressed_sizes: dict[str, int] = {}
    for variable in ("u_10m", "v_10m"):
        url = provider.file_url("icon-eu", run, variable, args.forecast_hour)
        before = perf_counter()
        response = provider.client.get(url, timeout=provider.timeout, follow_redirects=True)
        response.raise_for_status()
        if len(response.content) > provider.max_bytes:
            raise RuntimeError(f"download byte budget exceeded for {variable}")
        compressed_sizes[variable] = len(response.content)
        raw[variable] = __import__("bz2").decompress(response.content)
        urls[variable] = url
        if perf_counter() - before > provider.timeout:
            raise RuntimeError(f"download budget exceeded for {variable}")
    download_seconds = perf_counter() - t0

    decode_started = perf_counter()
    u_grid = decode_regular_latlon(raw["u_10m"])
    v_grid = decode_regular_latlon(raw["v_10m"])
    assert_same_grid(u_grid, v_grid)
    decode_seconds = perf_counter() - decode_started

    west, south, east, north = EUROPE
    tiles = xyz_tiles_for_bounds(west, south, east, north, args.zoom)
    variables = (TileVariable("wind_u"), TileVariable("wind_v"))
    assets: list[dict] = []
    component_min = float("inf")
    component_max = float("-inf")
    comparison_errors: list[float] = []
    process_started = perf_counter()
    valid_key = valid_time.strftime("%Y%m%dT%HZ")
    for z, x, y in tiles:
        u = project_xyz_tile(u_grid, z=z, x=x, y=y, tile_size=args.tile_size, overlap=args.overlap)
        v = project_xyz_tile(v_grid, z=z, x=x, y=y, tile_size=args.tile_size, overlap=args.overlap)
        relative = Path("assets") / valid_key / str(z) / str(x) / f"{y}.swf2.gz"
        payload = encode_field_tile(
            {"wind_u": u, "wind_v": v},
            metadata={"valid_time": utc_text(valid_time), "z": z, "x": x, "y": y, "overlap": args.overlap},
            variables=variables,
            compression="gzip",
        )
        decoded = decode_field_tile(payload, compression="gzip")
        finite = np.concatenate(
            [values[np.isfinite(values)] for values in decoded.arrays.values()]
        )
        if finite.size:
            component_min = min(component_min, float(finite.min()))
            component_max = max(component_max, float(finite.max()))
        center = args.overlap + args.tile_size // 2
        center_lon, center_lat = xyz_pixel_lonlat(
            z,
            x,
            y,
            pixel_x=center - args.overlap + 0.5,
            pixel_y=center - args.overlap + 0.5,
            tile_size=args.tile_size,
        )
        native = bilinear_uv(
            u_grid.longitudes,
            u_grid.latitudes,
            u_grid.values,
            v_grid.values,
            longitude=center_lon,
            latitude=center_lat,
        )
        if native is not None:
            tiled_u = decoded.arrays["wind_u"][center, center]
            tiled_v = decoded.arrays["wind_v"][center, center]
            if np.isfinite(tiled_u) and np.isfinite(tiled_v):
                comparison_errors.extend(
                    [abs(float(tiled_u) - native.u_ms), abs(float(tiled_v) - native.v_ms)]
                )
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        assets.append({"path": relative.as_posix(), "bytes": len(payload), "sha256": sha256_hex(payload), "z": z, "x": x, "y": y})
    processing_seconds = perf_counter() - process_started

    index_bytes = json.dumps({"assets": assets}, sort_keys=True, separators=(",", ":")).encode()
    (root / "asset-index.json").write_bytes(index_bytes)
    published = datetime.now(timezone.utc)
    manifest = FieldManifestV2.model_validate({
        "publication_id": publication_id,
        "provider": "Deutscher Wetterdienst",
        "model": "ICON-EU",
        "model_run": run,
        "published_at": published,
        "valid_times": [valid_time],
        "coverage": {"west": west, "south": south, "east": east, "north": north},
        "grid": {
            "projection": "regular_ll",
            "grid_type": "regular_ll",
            "rows": int(u_grid.values.shape[0]), "columns": int(u_grid.values.shape[1]),
            "longitude_convention": "-180_180",
            "scanning_mode": {key: u_grid.definition[key] for key in ("iScansNegatively", "jScansPositively", "jPointsAreConsecutive")},
            "definition": u_grid.definition,
            "coordinates_sha256": u_grid.coordinate_checksum,
        },
        "native_resolution": {"approximate_km": 7.0, "description": "Derived UI metric; native grid definition is authoritative"},
        "display_resolution": {"approximate_km": 10.0, "description": f"Experimental z{args.zoom}/{args.tile_size}px Web Mercator representation"},
        "variables": [{"name": "wind_u", "semantic": "eastward"}, {"name": "wind_v", "semantic": "northward"}],
        "quantization": {"variables": [{"variable": "wind_u", "scale": WIND_COMPONENT_SCALE_MS_V2}, {"variable": "wind_v", "scale": WIND_COMPONENT_SCALE_MS_V2}]},
        "compression": "gzip",
        "tile_scheme": {"tile_size": args.tile_size, "overlap": args.overlap, "lod": [{"source_zoom": args.zoom, "consumer_zoom_min": args.zoom, "consumer_zoom_max": args.zoom, "source_decimation": 1}]},
        "processing_version": "phase0.1",
        "quality_status": "experimental",
        "freshness": {
            "status": classify_freshness(max(0, int((published - run).total_seconds()))),
            "model_run_at": run, "source_discovered_at": started, "processing_started_at": started,
            "published_at": published, "expected_next_run_at": run + timedelta(hours=6),
            "age_seconds": max(0, int((published - run).total_seconds())),
        },
        "attribution": [{"provider": "DWD", "text": "Contains data from Deutscher Wetterdienst Open Data", "url": "https://opendata.dwd.de/weather/nwp/icon-eu/", "licence": "GeoNutzV"}],
        "field_template": "assets/{valid_time}/{z}/{x}/{y}.swf2.gz",
        "checksums": {"asset_index": sha256_hex(index_bytes)},
    })
    (root / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    shutil.copy2(Path(__file__).with_name("weather_field_phase0_viewer.html"), root / "viewer.html")
    report = {
        "status": "experimental", "publication_id": publication_id,
        "source_urls": urls,
        "download_compressed_bytes": compressed_sizes,
        "download_decompressed_bytes": {key: len(value) for key, value in raw.items()},
        "download_seconds": round(download_seconds, 3), "decode_seconds": round(decode_seconds, 3),
        "processing_seconds": round(processing_seconds, 3), "total_seconds": round(perf_counter() - t0, 3),
        "native_grid": {"rows": u_grid.values.shape[0], "columns": u_grid.values.shape[1]},
        "tile_count": len(assets), "tile_compressed_bytes": sum(item["bytes"] for item in assets),
        "quality": {
            "paired_uv": True,
            "all_asset_checksums_present": all(len(item["sha256"]) == 64 for item in assets),
            "component_range_ms": [round(component_min, 2), round(component_max, 2)],
            "grib_tile_center_samples": len(comparison_errors) // 2,
            "grib_tile_max_component_error_ms": round(max(comparison_errors), 4) if comparison_errors else None,
            "grib_tile_tolerance_ms": 0.2,
            "grib_tile_comparison_passed": bool(comparison_errors) and max(comparison_errors) <= 0.2,
        },
        "browser_metrics": {"desktop_fps": None, "mobile_fps": None, "javascript_heap_bytes": None, "gpu_memory_bytes": None, "note": "Captured by the viewer at runtime; GPU memory is not exposed by standard browser APIs."},
    }
    (root / "spike-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(root), **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
