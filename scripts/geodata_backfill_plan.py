"""Write the immutable phase-3 inventory and dry-run plan; performs no network I/O."""

from __future__ import annotations
import json
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
        for spot in db.scalars(select(Spot).order_by(Spot.id)).all():
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
    plan = build_plan(
        candidates,
        max_batch_size=10,
        gate_status="blocked_prerequisite" if gate.status != "ready" else "ready",
    )
    plan.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "excluded": excluded,
            "access": {
                "method": "official CDSE S3 generated access/secret keys",
                "status": gate.status,
                "reason": gate.reason,
            },
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
