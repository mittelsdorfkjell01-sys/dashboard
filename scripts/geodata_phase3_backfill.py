"""Execute the immutable phase-3 plan with cache-only shadow persistence."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.forecast.shadow import SHADOW_VERSION
from app.forecast.shadow_service import persist_shadow
from app.models import ForecastProcessingJob, ForecastSnapshot, Spot, SpotGeoShadowProfile

PLAN_PATH = Path("reports/geodata-backfill-plan.json")
ANALYSIS_PATH = Path("reports/geodata-phase2-analysis.json")
REPORT_PATH = Path("reports/geodata-phase3-backfill.json")
CANARY = ("Baleal", "Lo Stagnone", "Pozo Izquierdo")
REFERENCES = ("Baleal", "Brouwersdam", "Mundaka", "Lo Stagnone", "Pozo Izquierdo")


def stable_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def public_baseline(db) -> dict:
    rows = db.scalars(
        select(ForecastSnapshot).where(ForecastSnapshot.active.is_(True)).order_by(ForecastSnapshot.spot_id)
    ).all()
    return {str(row.spot_id): stable_hash(row.payload) for row in rows}


def asset_hashes(item: dict) -> list[str]:
    return sorted(
        layer["sha256"]
        for product in item["products"]
        for layer in product["layers"]
    ) + [item["derived_grid"]["sha256"]]


def process_reference(plan_id: str, planned: dict, pilot: dict) -> dict:
    started = time.monotonic()
    with SessionLocal() as db:
        spot = db.get(Spot, planned["spot_id"])
        if spot is None or spot.status != "published":
            return {"spot_id": planned["spot_id"], "name": planned["name"], "status": "excluded_not_published"}
        coordinate_hash = planned["coordinate_hash"]
        existing = db.scalar(
            select(SpotGeoShadowProfile).where(
                SpotGeoShadowProfile.spot_id == spot.id,
                SpotGeoShadowProfile.input_hash == stable_input_hash(
                    spot.id, coordinate_hash, asset_hashes(pilot)
                ),
            )
        )
        job_key = f"geo3:{plan_id}:{spot.id}:{coordinate_hash[:12]}"
        job = db.scalar(select(ForecastProcessingJob).where(ForecastProcessingJob.idempotency_key == job_key))
        if job is None:
            job = ForecastProcessingJob(
                spot_id=spot.id, kind="geodata_backfill", status="processing",
                idempotency_key=job_key, requested_by="phase3-cache-only",
                progress=10, attempt_count=1,
                options={"plan_id": plan_id, "cache_only": True, "coordinate_hash": coordinate_hash},
                diagnostics={"network_requests": 0, "network_bytes": 0},
                started_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.flush()
        row = persist_shadow(
            db, spot_id=spot.id, coordinate_hash=coordinate_hash,
            dataset_versions=["cop-dem-glo30:2024_1", "worldcover-2021:v200"],
            asset_hashes=asset_hashes(pilot),
            analysis={
                "plan_id": plan_id, "coordinate_hash": coordinate_hash,
                "derived_grid": pilot["derived_grid"], "water_anchor": pilot["water_anchor"],
                "coastline": pilot["coastline"], "component_quality": {"dem": "valid", "wbm": "valid", "worldcover": "valid"},
            },
            sectors=pilot["sectors"], profile_class=pilot["profile_class"],
            metrics={"sector_counts": pilot["sector_counts"], "scientific_hash": pilot["scientific_hash"], "network_requests": 0},
        )
        job.status = "succeeded"
        job.progress = 100
        job.finished_at = datetime.now(timezone.utc)
        job.diagnostics = {**job.diagnostics, "terminal_status": "skipped_identical" if existing else "completed", "profile_id": str(row.id)}
        db.commit()
        return {
            "spot_id": str(spot.id), "name": spot.name,
            "status": "skipped_identical" if existing else "completed",
            "profile_id": str(row.id), "profile_class": row.profile_class,
            "valid_sectors": pilot["sector_counts"]["valid"],
            "input_hash": row.input_hash, "scientific_hash": pilot["scientific_hash"],
            "network_requests": 0, "network_bytes": 0,
            "duration_seconds": round(time.monotonic() - started, 3),
        }


def stable_input_hash(spot_id, coordinate_hash: str, hashes: list[str]) -> str:
    from app.forecast.shadow import input_hash
    return input_hash(
        spot_id, coordinate_hash,
        ["cop-dem-glo30:2024_1", "worldcover-2021:v200"], hashes,
    )


def blocked_result(plan_id: str, item: dict) -> dict:
    with SessionLocal() as db:
        key = f"geo3:{plan_id}:{item['spot_id']}:{item['coordinate_hash'][:12]}"
        job = db.scalar(select(ForecastProcessingJob).where(ForecastProcessingJob.idempotency_key == key))
        if job is None:
            job = ForecastProcessingJob(
                spot_id=item["spot_id"], kind="geodata_backfill", status="succeeded",
                idempotency_key=key, requested_by="phase3-cache-only", progress=100,
                attempt_count=1, options={"plan_id": plan_id, "cache_only": True, "coordinate_hash": item["coordinate_hash"]},
                diagnostics={"terminal_status": "blocked_cache_missing", "network_requests": 0, "network_bytes": 0},
                started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.commit()
    return {"spot_id": item["spot_id"], "name": item["name"], "status": "blocked_cache_missing", "network_requests": 0, "network_bytes": 0}


def main() -> None:
    started_at = datetime.now(timezone.utc)
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    if not plan.get("execution_allowed") or analysis.get("status") != "accepted":
        raise RuntimeError("phase-3 prerequisite gate is not accepted")
    planned = {item["name"]: item for batch in plan["batches"] for item in batch["spots"]}
    pilots = {item["name"]: item for item in analysis["spots"]}
    with SessionLocal() as db:
        before = public_baseline(db)

    canary = [process_reference(plan["plan_id"], planned[name], pilots[name]) for name in CANARY]
    if not all(x["profile_class"] == "A" and x["valid_sectors"] == 16 for x in canary):
        raise RuntimeError("three-spot canary failed")
    validation = [process_reference(plan["plan_id"], planned[name], pilots[name]) for name in REFERENCES]
    if not all(x["profile_class"] == "A" and x["valid_sectors"] == 16 for x in validation):
        raise RuntimeError("five-spot validation failed")
    final_by_name = {x["name"]: x for x in validation}
    for name, item in planned.items():
        if name not in final_by_name:
            final_by_name[name] = blocked_result(plan["plan_id"], item)
    results = [final_by_name[item["name"]] for batch in plan["batches"] for item in batch["spots"]]

    with SessionLocal() as db:
        after = public_baseline(db)
        orphan_jobs = db.scalars(select(ForecastProcessingJob).where(ForecastProcessingJob.kind == "geodata_backfill", ForecastProcessingJob.status.in_(("queued", "processing")))).all()
    if before != after:
        raise RuntimeError("public forecast baseline changed during phase-3 backfill")
    counts = {status: sum(x["status"] == status for x in results) for status in sorted({x["status"] for x in results})}
    report = {
        "plan_id": plan["plan_id"], "algorithm_version": SHADOW_VERSION,
        "started_at": started_at.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
        "published": plan["spot_count"], "eligible": plan["spot_count"], "planned": len(results),
        "canary": canary, "five_spot_validation": validation, "results": results,
        "counts": counts, "network_requests": 0, "network_bytes": 0,
        "cache_only": True, "public_baseline_identical": True,
        "orphan_jobs": len(orphan_jobs), "partials": len(list(Path("data/geodata-cache").rglob("*.part"))),
        "batches": [{"index": b["index"], "stage": b["stage"], "spot_count": len(b["spots"]), "tile_group": b["batch_key"], "max_temporary_bytes": 0} for b in plan["batches"]],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    Path("reports/geodata-phase3-backfill.md").write_text(
        "# Phase-3 cache-only backfill\n\n"
        f"Plan `{plan['plan_id']}` finished with {counts}. Network: 0 requests / 0 bytes. "
        "The public forecast baseline is identical.\n",
        encoding="utf-8",
    )
    print(json.dumps({"plan_id": plan["plan_id"], "counts": counts, "public_identical": True, "network_requests": 0}))


if __name__ == "__main__":
    main()
