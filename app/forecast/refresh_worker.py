"""Local-only, resumable forecast refresh planning foundation.

No scheduler imports this module. Activation remains blocked while production DB
capacity is unavailable.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time

from sqlalchemy import select

from app.forecast.publisher import enqueue
from app.models import ForecastSnapshot, Spot


@dataclass(frozen=True)
class RefreshPlan:
    due_spot_ids: tuple
    skipped_fresh: int
    estimated_provider_attempts: int


def build_plan(spots, snapshots, *, now=None, due_after=timedelta(hours=2)) -> RefreshPlan:
    now = now or datetime.now(timezone.utc)
    latest = {}
    for snapshot in snapshots:
        current = latest.get(snapshot.spot_id)
        if current is None or snapshot.generated_at > current.generated_at:
            latest[snapshot.spot_id] = snapshot
    due = tuple(
        spot.id for spot in spots
        if spot.status == "published" and (
            spot.id not in latest or latest[spot.id].generated_at <= now - due_after
        )
    )
    published = sum(spot.status == "published" for spot in spots)
    return RefreshPlan(due, published - len(due), len(due) * 2)


def load_plan(db, *, now=None) -> RefreshPlan:
    spots = list(db.scalars(select(Spot).where(Spot.status == "published")))
    snapshots = list(db.scalars(select(ForecastSnapshot).where(ForecastSnapshot.active.is_(True))))
    return build_plan(spots, snapshots, now=now)


def enqueue_due(db, *, dry_run=True, max_seconds=300, run_request_budget=200, clock=time.monotonic):
    plan = load_plan(db)
    report = {"due": len(plan.due_spot_ids), "queued": 0, "failed": 0,
              "estimated_provider_attempts": plan.estimated_provider_attempts,
              "stopped": None, "dry_run": dry_run}
    if dry_run:
        return report
    started = clock()
    attempts = 0
    for spot_id in plan.due_spot_ids:
        if clock() - started >= max_seconds:
            report["stopped"] = "time_budget"
            break
        if attempts + 2 > run_request_budget:
            report["stopped"] = "provider_budget"
            break
        try:
            enqueue(db, spot_id, requested_by="local-refresh-worker", reason="freshness")
            report["queued"] += 1
            attempts += 2
        except Exception:
            report["failed"] += 1
    return report
