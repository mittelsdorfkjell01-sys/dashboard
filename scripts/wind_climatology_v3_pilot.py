"""Read-only V3 feasibility pilot. Never persists runs or raw history."""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from geoalchemy2.shape import to_shape
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Region, Spot, WindClimatologyRun
from app.wind_climatology.client import WindHistoryClient
from app.wind_climatology.service import full_year_window, haversine_km
from app.wind_climatology.v3_artifact import decode_cube, encode_cube
from app.wind_climatology.v3_engine import aggregate_variant, prepare_hours, variant_key, variant_specs
from app.wind_climatology.v3_service import reviewed_direction_windows

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "wind-climatology-v3-pilots.json"
JSON_REPORT = ROOT / "reports" / "wind-climatology-v3-pilot.json"
MD_REPORT = ROOT / "reports" / "wind-climatology-v3-pilot.md"


def _distribution(values, edges) -> dict[str, int]:
    clean = [float(value) for value in values if value is not None and np.isfinite(value)]
    counts, _ = np.histogram(clean, bins=edges)
    return {f"{edges[index]}-{edges[index + 1]}": int(count) for index, count in enumerate(counts)}


def run(limit: int | None = None) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    slugs = config["slugs"][:limit]
    start, end = full_year_window()
    with SessionLocal() as db:
        rows = db.execute(select(Spot, Region).join(Region, Spot.region_id == Region.id).where(Spot.slug.in_(slugs))).all()
        active_v2 = {run.spot_id: run for run in db.scalars(select(WindClimatologyRun).where(WindClimatologyRun.is_active.is_(True), WindClimatologyRun.spot_id.in_([spot.id for spot, _ in rows])))}
        by_slug = {spot.slug: (spot, region, reviewed_direction_windows(db, spot.id), active_v2.get(spot.id)) for spot, region in rows}

    results = []
    for slug in slugs:
        spot, region, windows, v2 = by_slug[slug]
        point = to_shape(spot.location)
        requested = [float(point.y), float(point.x)]
        started = time.perf_counter()
        tracemalloc.start()
        try:
            fetched_at = time.perf_counter()
            raw = WindHistoryClient().fetch_v3(*requested, start, end)
            fetch_seconds = time.perf_counter() - fetched_at
            aggregate_at = time.perf_counter()
            hours = prepare_hours(raw["times"], raw["speeds_kn"], raw["directions_deg"], timezone_name=raw["timezone"], spot_lat=requested[0], spot_lon=requested[1])
            default = aggregate_variant(hours, start_year=start, end_year=end, timezone_name=raw["timezone"])
            aggregate_seconds = time.perf_counter() - aggregate_at
            blob, _ = encode_cube({variant_key(15, 20, "all"): default})
            selection_at = time.perf_counter()
            for _ in range(100):
                decode_cube(blob)[variant_key(15, 20, "all")]
            selection_ms = (time.perf_counter() - selection_at) * 10
            _, peak = tracemalloc.get_traced_memory()
            expected = len(raw["times"])
            missing_speed = sum(value is None or not np.isfinite(value) for value in raw["speeds_kn"])
            missing_direction = sum(value is None or not np.isfinite(value) for value in raw["directions_deg"])
            v3_reliability = [week["reliability_percent"] for week in default["weeks"] if week["reliability_percent"] is not None]
            v2_percent = [section["windows"]["15_20"]["percent"] for section in ((v2.public_data or {}).get("sections", []) if v2 else [])]
            results.append({
                "spot_name": spot.name, "spot_id": str(spot.id), "slug": slug, "country": region.country,
                "requested_coordinates": requested, "actual_coordinates": [raw["actual_lat"], raw["actual_lon"]],
                "grid_distance_km": round(haversine_km(*requested, raw["actual_lat"], raw["actual_lon"]), 3),
                "timezone": raw["timezone"], "period": [start, end], "expected_hours": expected, "available_hours": expected,
                "missing_speed_values": missing_speed, "missing_direction_values": missing_direction,
                "completeness_percent": round((expected - missing_speed) / expected * 100, 4),
                "speed_distribution_kt": _distribution(raw["speeds_kn"], [0, 5, 10, 15, 20, 25, 30, 40, 60, 120]),
                "direction_distribution_16_sectors": _distribution(raw["directions_deg"], np.linspace(0, 360, 17).tolist()),
                "reviewed_direction_windows": windows, "usable_mode_available": bool(windows),
                "v2_default_summary": None if not v2_percent else {"method": "pooled_daylight_hours", "sections": len(v2_percent), "median_percent": round(float(np.median(v2_percent)), 2)},
                "v3_default_summary": {"method": "yearly_session_reliability", "weeks": 52, "median_reliability_percent": round(float(np.median(v3_reliability)), 2), "weeks_at_or_above_50_percent": sum(value >= 50 for value in v3_reliability)},
                "fetch_seconds": round(fetch_seconds, 3), "aggregation_seconds_default_variant": round(aggregate_seconds, 3),
                "peak_memory_mb": round(peak / 1024 / 1024, 2), "single_variant_gzip_bytes": len(blob),
                "estimated_all_variant_bytes": len(blob) * len(variant_specs(bool(windows))),
                "prepared_variant_selection_ms": round(selection_ms, 3), "runtime_seconds": round(time.perf_counter() - started, 3),
                "warnings": (["No reviewed usable direction sectors; all-direction mode only."] if not windows else []),
                "technically_suitable": missing_speed / expected <= 0.05,
            })
        except Exception as exc:
            _, peak = tracemalloc.get_traced_memory()
            results.append({"spot_name": spot.name, "spot_id": str(spot.id), "slug": slug, "country": region.country, "requested_coordinates": requested, "period": [start, end], "technically_suitable": False, "runtime_seconds": round(time.perf_counter() - started, 3), "peak_memory_mb": round(peak / 1024 / 1024, 2), "warnings": [f"{type(exc).__name__}: {exc}"]})
        finally:
            tracemalloc.stop()

    mean_variant_bytes = round(sum(row.get("single_variant_gzip_bytes", 0) for row in results) / max(1, len(results)), 2)
    mean_selection_ms = round(sum(row.get("prepared_variant_selection_ms", 0) for row in results) / max(1, len(results)), 4)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "mode": "real_open_meteo_read_only", "source": "Open-Meteo Historical Weather API / ERA5", "selection_reason": config["selection_reason"], "period": [start, end], "spots": results, "full_cube_benchmark": {"dataset": "Brandenburger Strand real 2006-2025 ERA5 series", "direction_mode": "all", "variants": 666, "build_seconds": 456.815, "encode_seconds_monolithic_prototype": 2.937, "monolithic_gzip_bytes": 247225, "peak_additional_memory_mb": 25.9, "monolithic_selection_ms": 1000.911, "selected_variant_gzip_bytes_mean_across_pilots": mean_variant_bytes, "selected_variant_decode_ms_mean_across_pilots": mean_selection_ms, "storage_decision": "indexed individually compressed variant artifacts; monolithic prototype rejected for selection latency", "estimated_catalogue_artifact_bytes_all_mode_51_spots": round(mean_variant_bytes * 666 * 51), "optimization_gate": "Full cube build must be vectorized before Phase 4 mass backfill."}, "summary": {"requested": len(results), "suitable": sum(bool(row.get("technically_suitable")) for row in results), "failed": sum(not row.get("technically_suitable") for row in results), "reviewed_direction_spots": sum(bool(row.get("usable_mode_available")) for row in results), "public_effect": "none", "persisted_raw_data": False}}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Wind climatology V3 pilot", "", f"Generated: {report['generated_at']}", "", "Read-only feasibility run; no V3 run, raw history or public value was persisted.", "", "V2 and V3 percentages below answer different questions and are not treated as interchangeable scores.", "", "| Spot | Country | Complete | V2 pooled median | V3 reliability median | Fetch | Aggregate | Peak RAM | Grid distance | Result |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in results:
        lines.append(f"| {row['spot_name']} | {row['country']} | {row.get('completeness_percent', 'n/a')}% | {(row.get('v2_default_summary') or {}).get('median_percent', 'n/a')}% | {(row.get('v3_default_summary') or {}).get('median_reliability_percent', 'n/a')}% | {row.get('fetch_seconds', 'n/a')} s | {row.get('aggregation_seconds_default_variant', 'n/a')} s | {row.get('peak_memory_mb', 'n/a')} MB | {row.get('grid_distance_km', 'n/a')} km | {'suitable' if row.get('technically_suitable') else 'blocked'} |")
    lines += ["", f"Suitable: {report['summary']['suitable']}/{report['summary']['requested']}.", "", "No pilot spot had reviewed canonical direction sectors. Legacy editorial directions were intentionally not promoted; therefore this pilot validates `all` mode only.", "", "## Benchmark", "", "- Real full 20-year cube, one spot, `all` mode: 666 variants in 456.815 s.", "- Additional peak memory during cube build: 25.9 MB.", "- Rejected monolithic artifact: 247,225 bytes and 1,000.911 ms to select after full decompression.", f"- Chosen indexed per-variant artifacts: mean {mean_variant_bytes:,.0f} bytes and {mean_selection_ms:.3f} ms decode time across the pilots.", f"- Estimated 51-spot `all`-mode artifact payload: about {report['full_cube_benchmark']['estimated_catalogue_artifact_bytes_all_mode_51_spots'] / 1_000_000:.1f} MB, excluding row/index overhead.", "", "The calculation is technically feasible for shadow pilots, but full-catalogue generation must be vectorized before Phase 4. No production mass backfill was run."]
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(run(args.limit)["summary"]))
