"""Benchmark real ICON-EU fields to freeze the weather-field-v2 tile contract."""

from __future__ import annotations

import argparse
import bz2
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forecast.providers import DwdIconProvider  # noqa: E402
from app.spatial_fields.phase0 import (  # noqa: E402
    assert_same_grid,
    decode_regular_latlon,
    project_xyz_tile,
    xyz_tiles_for_bounds,
)
from app.spatial_fields.tile_codec import (  # noqa: E402
    TileVariable,
    decode_field_tile,
    encode_field_tile,
)


EUROPE = (-23.5, 29.5, 45.0, 70.5)


@dataclass(frozen=True)
class Candidate:
    name: str
    zoom: int
    tile_size: int
    scale: float
    overlap: int = 1


CANDIDATES = (
    Candidate("z4-128-q001", zoom=4, tile_size=128, scale=0.01),
    Candidate("z4-128-q005", zoom=4, tile_size=128, scale=0.05),
    Candidate("z4-256-q001", zoom=4, tile_size=256, scale=0.01),
    Candidate("z5-128-q001", zoom=5, tile_size=128, scale=0.01),
    Candidate("z5-128-q005", zoom=5, tile_size=128, scale=0.05),
)


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


def download_message(
    provider: DwdIconProvider, run: datetime, variable: str, forecast_hour: int
) -> tuple[bytes, int]:
    url = provider.file_url("icon-eu", run, variable, forecast_hour)
    response = provider.client.get(url, timeout=provider.timeout, follow_redirects=True)
    response.raise_for_status()
    if len(response.content) > provider.max_bytes:
        raise RuntimeError(f"download byte budget exceeded for {variable} f{forecast_hour:03d}")
    return bz2.decompress(response.content), len(response.content)


def benchmark_candidate(candidate: Candidate, fields: list[tuple[int, object, object]]) -> dict:
    tiles = xyz_tiles_for_bounds(*EUROPE, candidate.zoom)
    variables = (
        TileVariable("wind_u", scale=candidate.scale),
        TileVariable("wind_v", scale=candidate.scale),
    )
    total_bytes = 0
    max_quantization_error = 0.0
    encoded_tiles = 0
    started = perf_counter()
    timestep_bytes: list[int] = []
    for forecast_hour, u_grid, v_grid in fields:
        current_bytes = 0
        for z, x, y in tiles:
            u = project_xyz_tile(
                u_grid,
                z=z,
                x=x,
                y=y,
                tile_size=candidate.tile_size,
                overlap=candidate.overlap,
            )
            v = project_xyz_tile(
                v_grid,
                z=z,
                x=x,
                y=y,
                tile_size=candidate.tile_size,
                overlap=candidate.overlap,
            )
            payload = encode_field_tile(
                {"wind_u": u, "wind_v": v},
                metadata={"forecast_hour": forecast_hour, "z": z, "x": x, "y": y},
                variables=variables,
                compression="gzip",
            )
            decoded = decode_field_tile(payload, compression="gzip")
            for name, source in (("wind_u", u), ("wind_v", v)):
                finite = np.isfinite(source)
                if finite.any():
                    error = np.max(np.abs(decoded.arrays[name][finite] - source[finite]))
                    max_quantization_error = max(max_quantization_error, float(error))
            current_bytes += len(payload)
            encoded_tiles += 1
        timestep_bytes.append(current_bytes)
        total_bytes += current_bytes
    elapsed = perf_counter() - started
    return {
        "name": candidate.name,
        "zoom": candidate.zoom,
        "tile_size": candidate.tile_size,
        "overlap": candidate.overlap,
        "quantization_scale_ms": candidate.scale,
        "timesteps": len(fields),
        "tiles_per_timestep": len(tiles),
        "encoded_tiles": encoded_tiles,
        "timestep_bytes": timestep_bytes,
        "mean_timestep_bytes": round(float(np.mean(timestep_bytes))),
        "total_bytes": total_bytes,
        "processing_seconds": round(elapsed, 3),
        "max_quantization_error_ms": round(max_quantization_error, 5),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-at", help="UTC run such as 2026-10-03T12:00:00Z")
    parser.add_argument("--forecast-hours", type=int, nargs="+", default=[0, 3, 6])
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/weather-field-phase0b")
    )
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

    fields = []
    compressed_download_bytes = 0
    download_started = perf_counter()
    for forecast_hour in sorted(set(args.forecast_hours)):
        u_raw, u_size = download_message(provider, run, "u_10m", forecast_hour)
        v_raw, v_size = download_message(provider, run, "v_10m", forecast_hour)
        compressed_download_bytes += u_size + v_size
        u_grid = decode_regular_latlon(u_raw)
        v_grid = decode_regular_latlon(v_raw)
        assert_same_grid(u_grid, v_grid)
        fields.append((forecast_hour, u_grid, v_grid))
    download_decode_seconds = perf_counter() - download_started

    results = [benchmark_candidate(candidate, fields) for candidate in CANDIDATES]
    baseline = next(result for result in results if result["name"] == "z4-128-q001")
    for result in results:
        result["payload_ratio_to_baseline"] = round(
            result["mean_timestep_bytes"] / baseline["mean_timestep_bytes"], 3
        )

    report = {
        "status": "phase0b-benchmark",
        "model": "ICON-EU",
        "model_run": run.isoformat().replace("+00:00", "Z"),
        "forecast_hours": [item[0] for item in fields],
        "compressed_download_bytes": compressed_download_bytes,
        "download_decode_seconds": round(download_decode_seconds, 3),
        "candidates": results,
        "decision": {
            "tile_size": 128,
            "overlap": 1,
            "quantization_scale_ms": 0.05,
            "compression": "gzip",
            "base_lod": {"zoom": 4, "consumer_zoom_min": 0, "consumer_zoom_max": 5},
            "detail_lod": {"zoom": 5, "consumer_zoom_min": 6, "consumer_zoom_max": 8},
            "reason": "z4/128 minimizes initial transfer; z5/128 retains near-native detail only when zoomed in. q0.05 saves about 25% while keeping quantization error <=0.025 m/s.",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / f"{run:%Y%m%dT%HZ}-benchmark.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(destination), **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
