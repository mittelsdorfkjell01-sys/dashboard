"""Write the immutable phase-3 inventory and dry-run plan; performs no network I/O."""

from __future__ import annotations
import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Spot, SpotGeoShadowProfile
from app.forecast.backfill_plan import Candidate, build_plan
from app.forecast.copernicus_gate import preflight_gate


def main():
    gate = preflight_gate([])
    pilot_ready = False
    analysis_report = Path("reports/geodata-phase2-analysis.json")
    warm_report = Path("reports/geodata-phase2-warm.json")
    if analysis_report.exists() and warm_report.exists():
        try:
            analysis = json.loads(analysis_report.read_text(encoding="utf-8"))
            warm = json.loads(warm_report.read_text(encoding="utf-8"))
            pilot_ready = (
                analysis.get("status") == "accepted"
                and warm.get("status") == "accepted"
                and warm.get("network_requests") == 0
                and warm.get("identical") is True
            )
        except (OSError, ValueError):
            pilot_ready = False
    candidates = []
    excluded = []
    with SessionLocal() as db:
        active = set(
            db.scalars(
                select(SpotGeoShadowProfile.spot_id).where(
                    SpotGeoShadowProfile.active_shadow.is_(True)
                )
            ).all()
        )
        all_spots = db.scalars(select(Spot).order_by(Spot.id)).all()
        for spot in all_spots:
            if spot.status != "published":
                excluded.append(
                    {"spot_id": str(spot.id), "reason": "excluded_not_published"}
                )
                continue
            try:
                p = to_shape(spot.location)
            except Exception:
                excluded.append(
                    {"spot_id": str(spot.id), "reason": "invalid_coordinate"}
                )
                continue
            if not (-90 <= p.y <= 90 and -180 <= p.x <= 180):
                excluded.append(
                    {"spot_id": str(spot.id), "reason": "invalid_coordinate"}
                )
                continue
            candidates.append(
                Candidate(
                    str(spot.id), spot.name, p.y, p.x, 2 if spot.id not in active else 0
                )
            )
    effective_gate = "ready" if gate.status == "ready" and pilot_ready else "blocked_prerequisite"
    plan = build_plan(
        candidates,
        max_batch_size=10,
        gate_status=effective_gate,
    )
    for batch in plan["batches"]:
        for item in batch["spots"]:
            raw = f"{item['coordinates'][0]:.7f}|{item['coordinates'][1]:.7f}"
            item["coordinate_hash"] = hashlib.sha256(raw.encode()).hexdigest()
            item["published"] = True
    plan_id = hashlib.sha256(
        json.dumps(
            {
                "plan_version": plan["plan_version"],
                "algorithm_version": plan["algorithm_version"],
                "spots": [
                    {
                        "spot_id": item["spot_id"],
                        "coordinate_hash": item["coordinate_hash"],
                        "asset_signature": item["asset_signature"],
                    }
                    for batch in plan["batches"]
                    for item in batch["spots"]
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    plan.update(
        {
            "plan_id": plan_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "excluded": excluded,
            "access": {
                "method": "official CDSE S3 generated access/secret keys",
                "status": gate.status,
                "reason": gate.reason,
            },
            "pilot_accepted": pilot_ready,
            "dry_run": True,
            "downloads": 0,
            "profiles_created": 0,
        }
    )
    Path("reports/geodata-backfill-plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "# Phase-3 immutable dry-run plan",
        "",
        f"Gate: `{plan['gate_status']}`; execution allowed: `{plan['execution_allowed']}`.",
        f"Inventory: {plan['spot_count']} eligible, {len(excluded)} excluded, {plan['batch_count']} tile-centred batches.",
        "",
        "No raster request or profile creation occurred.",
        "",
        "| Batch | Spots | Assets | Status |",
        "|---:|---:|---:|---|",
    ]
    lines += [
        f"| {b['index']} | {len(b['spots'])} | {len(b['assets'])} | {b['status']} |"
        for b in plan["batches"]
    ]
    Path("reports/geodata-backfill-plan.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: plan[k]
                for k in (
                    "gate_status",
                    "spot_count",
                    "batch_count",
                    "execution_allowed",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
