"""Immutable, deterministic and network-free phase-3 tile-centred planning."""

from __future__ import annotations
import hashlib
import math
from dataclasses import dataclass
from app.forecast.geodata import analysis_crs, tile_code
from app.forecast.shadow import RAY_OFFSETS, SECTOR_CENTERS, SHADOW_VERSION, ray_distances

PLAN_VERSION = "swd-geodata-backfill-v1"
LAYERS = ("DEM", "WBM", "HEM", "EDM", "FLM")
MAX_ASSETS_PER_BATCH = 200


@dataclass(frozen=True)
class Candidate:
    spot_id: str
    name: str
    latitude: float
    longitude: float
    priority: int = 0


def _destination(lat: float, lon: float, bearing: float, distance_m: float):
    """Spherical destination matching the shadow engine's meteorological rays."""
    radius = 6_371_000.0
    angular = distance_m / radius
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)
    theta = math.radians(bearing)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(angular)
        + math.cos(phi1) * math.sin(angular) * math.cos(theta)
    )
    lam2 = lam1 + math.atan2(
        math.sin(theta) * math.sin(angular) * math.cos(phi1),
        math.cos(angular) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), ((math.degrees(lam2) + 180) % 360) - 180


def _halo_points(lat, lon, radius_km=100):
    """Every geocell touched by the actual 16×9 multi-scale ray sampler.

    The old five-point corners/centre approximation omitted intermediate cells
    and produced D-class real pilots. Distances are deduplicated by tile below,
    so this exhaustive planning step remains cheap and performs no network I/O.
    """
    maximum = radius_km * 1000
    distances = ray_distances(maximum)
    points = [(lat, lon)]
    for center in SECTOR_CENTERS:
        for offset in RAY_OFFSETS:
            bearing = center + float(offset)
            points.extend(_destination(lat, lon, bearing, float(d)) for d in distances)
    return tuple(points)


def signature(candidate: Candidate) -> dict:
    points = _halo_points(candidate.latitude, candidate.longitude)
    dem_tiles = sorted(
        {tile_code(lat, ((lon + 180) % 360) - 180, 1) for lat, lon in points}
    )
    wc_tiles = sorted(
        {tile_code(lat, ((lon + 180) % 360) - 180, 3) for lat, lon in points}
    )
    assets = sorted(
        [f"cop-dem:2024_1:{tile}:{layer}" for tile in dem_tiles for layer in LAYERS]
        + [f"worldcover:v200:{tile}:Map" for tile in wc_tiles]
    )
    digest = hashlib.sha256("|".join([SHADOW_VERSION, *assets]).encode()).hexdigest()
    return {
        "spot_id": candidate.spot_id,
        "name": candidate.name,
        "coordinates": [candidate.latitude, candidate.longitude],
        "analysis_crs": analysis_crs(candidate.latitude, candidate.longitude),
        "assets": assets,
        "asset_signature": digest,
        "priority": candidate.priority,
    }


def build_plan(
    candidates: list[Candidate],
    *,
    max_batch_size: int = 10,
    cached: set[str] | None = None,
    gate_status="blocked_prerequisite",
) -> dict:
    if not 1 <= max_batch_size <= 10:
        raise ValueError("batch size must be 1..10")
    cached = cached or set()
    remaining = [signature(c) for c in candidates]
    remaining.sort(key=lambda x: (-x["priority"], x["spot_id"]))
    batches = []
    while remaining:
        seed = remaining.pop(0)
        batch = [seed]
        shared = set(seed["assets"])
        stage_limit = min(
            max_batch_size,
            3 if not batches else 5 if len(batches) == 1 else max_batch_size,
        )
        while remaining and len(batch) < stage_limit:
            eligible = [
                item
                for item in remaining
                if len(shared | set(item["assets"])) <= MAX_ASSETS_PER_BATCH
            ]
            if not eligible:
                break
            best = max(
                eligible,
                key=lambda item: (
                    len(shared & set(item["assets"])),
                    item["priority"],
                    item["spot_id"],
                ),
            )
            remaining.remove(best)
            batch.append(best)
            shared.update(best["assets"])
        all_assets = sorted({a for item in batch for a in item["assets"]})
        missing = [a for a in all_assets if a not in cached]
        key = hashlib.sha256(
            "|".join(
                [PLAN_VERSION, *sorted(i["spot_id"] for i in batch), *all_assets]
            ).encode()
        ).hexdigest()
        batches.append(
            {
                "index": len(batches),
                "stage": "canary"
                if not batches
                else "five"
                if len(batches) == 1
                else "expanded",
                "stage_limit": stage_limit,
                "batch_key": key,
                "status": "blocked_provider" if gate_status != "ready" else "pending",
                "spots": batch,
                "assets": all_assets,
                "cache_hits": len(all_assets) - len(missing),
                "new_assets": missing,
                "expected_requests": len(missing),
                "expected_bytes": None,
            }
        )
    inventory_hash = hashlib.sha256(
        "|".join(sorted(c.spot_id for c in candidates)).encode()
    ).hexdigest()
    return {
        "plan_version": PLAN_VERSION,
        "algorithm_version": SHADOW_VERSION,
        "inventory_hash": inventory_hash,
        "gate_status": gate_status,
        "spot_count": len(candidates),
        "batch_count": len(batches),
        "max_batch_size": max_batch_size,
        "batches": batches,
        "execution_allowed": gate_status == "ready",
    }
