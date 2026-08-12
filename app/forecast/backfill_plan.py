"""Immutable, deterministic and network-free phase-3 tile-centred planning."""

from __future__ import annotations
import hashlib
import math
from dataclasses import dataclass
from app.forecast.geodata import analysis_crs, tile_code
from app.forecast.shadow import SHADOW_VERSION

PLAN_VERSION = "swd-geodata-backfill-v1"
LAYERS = ("DEM", "WBM", "HEM", "EDM", "FLM")


@dataclass(frozen=True)
class Candidate:
    spot_id: str
    name: str
    latitude: float
    longitude: float
    priority: int = 0


def _halo_points(lat, lon, radius_km=100):
    dy = radius_km / 111
    dx = radius_km / (111 * max(0.15, math.cos(math.radians(lat))))
    return (
        (lat - dy, lon - dx),
        (lat - dy, lon + dx),
        (lat + dy, lon - dx),
        (lat + dy, lon + dx),
        (lat, lon),
    )


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
            best = max(
                remaining,
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
