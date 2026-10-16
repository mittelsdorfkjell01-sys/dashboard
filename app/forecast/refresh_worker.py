"""Bounded, resumable refresh cycle for published spot forecasts."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import time

from sqlalchemy import select

from app.config import get_settings
from app.forecast.publisher import enqueue
from app.models import ForecastProcessingJob, ForecastSnapshot, Spot


@dataclass(frozen=True)
class RefreshPlan:
    due_spot_ids: tuple
    skipped_fresh: int
    estimated_provider_attempts: int
    wave_context_changed_spot_ids: tuple = ()
    wave_context: str | None = None


def _snapshot_wave_publication_ids(snapshot) -> tuple[str, ...]:
    internal = getattr(snapshot, "internal", None) or {}
    wave_field = internal.get("wave_field") or {}
    publication_ids = wave_field.get("active_publication_ids")
    if publication_ids is None:
        publication_ids = wave_field.get("publication_ids") or []
    return tuple(sorted({str(value) for value in publication_ids}))


def _wave_context(publication_ids: tuple[str, ...]) -> str | None:
    if not publication_ids:
        return None
    return hashlib.sha256("|".join(publication_ids).encode()).hexdigest()[:12]


def build_plan(
    spots,
    snapshots,
    *,
    now=None,
    due_after=timedelta(hours=2),
    active_wave_publication_ids=(),
) -> RefreshPlan:
    now = now or datetime.now(timezone.utc)
    active_wave_ids = tuple(
        sorted({str(value) for value in active_wave_publication_ids})
    )
    latest = {}
    for snapshot in snapshots:
        current = latest.get(snapshot.spot_id)
        if current is None or snapshot.generated_at > current.generated_at:
            latest[snapshot.spot_id] = snapshot
    due = []
    wave_context_changed = []
    for spot in spots:
        if spot.status != "published":
            continue
        snapshot = latest.get(spot.id)
        changed = bool(
            snapshot is not None
            and active_wave_ids
            and _snapshot_wave_publication_ids(snapshot) != active_wave_ids
        )
        if snapshot is None or snapshot.generated_at <= now - due_after or changed:
            due.append(spot.id)
        if changed:
            wave_context_changed.append(spot.id)
    due_ids = tuple(due)
    published = sum(spot.status == "published" for spot in spots)
    return RefreshPlan(
        due_ids,
        published - len(due_ids),
        len(due_ids) * 2,
        tuple(wave_context_changed),
        _wave_context(active_wave_ids),
    )


def load_plan(db, *, now=None, settings=None) -> RefreshPlan:
    configured = settings or get_settings()
    spots = list(db.scalars(select(Spot).where(Spot.status == "published")))
    snapshots = list(db.scalars(select(ForecastSnapshot).where(ForecastSnapshot.active.is_(True))))
    wave_publication_ids = ()
    if getattr(configured, "wave_field_public_enabled", False):
        from app.spatial_fields.spot_forecast import active_wave_publication_ids

        wave_publication_ids = active_wave_publication_ids(
            db,
            settings=configured,
            now=now,
        )
    return build_plan(
        spots,
        snapshots,
        now=now,
        active_wave_publication_ids=wave_publication_ids,
    )


def enqueue_due(
    db,
    *,
    dry_run=True,
    max_seconds=300,
    run_request_budget=200,
    clock=time.monotonic,
    now=None,
    settings=None,
):
    plan = load_plan(db, now=now, settings=settings)
    report = {"due": len(plan.due_spot_ids), "queued": 0, "failed": 0,
              "estimated_provider_attempts": plan.estimated_provider_attempts,
              "wave_context_changed": len(plan.wave_context_changed_spot_ids),
              "wave_context": plan.wave_context,
              "stopped": None, "dry_run": dry_run}
    if dry_run:
        return report
    started = clock()
    attempts = 0
    wave_context_changed = set(plan.wave_context_changed_spot_ids)
    for spot_id in plan.due_spot_ids:
        if clock() - started >= max_seconds:
            report["stopped"] = "time_budget"
            break
        if attempts + 2 > run_request_budget:
            report["stopped"] = "provider_budget"
            break
        try:
            reason = (
                f"wave-publication-{plan.wave_context}"
                if spot_id in wave_context_changed and plan.wave_context
                else "freshness"
            )
            enqueue(db, spot_id, requested_by="local-refresh-worker", reason=reason)
            report["queued"] += 1
            attempts += 2
        except Exception:
            report["failed"] += 1
    return report


def run_refresh_cycle(db, *, settings=None, now=None) -> dict:
    """Queue all due public spots, then process one bounded worker batch.

    Enqueueing the complete due set is cheap and idempotent. Provider work remains
    bounded by ``forecast_job_batch_size`` so repeated maintenance ticks drain a
    larger catalogue without one long-running scheduler invocation.
    """
    configured = settings or get_settings()
    enqueue_report = enqueue_due(
        db,
        dry_run=False,
        run_request_budget=configured.forecast_refresh_request_budget,
        now=now,
        settings=configured,
    )
    queued_job_ids = list(
        db.scalars(
            select(ForecastProcessingJob.id)
            .where(ForecastProcessingJob.status == "queued")
            .order_by(ForecastProcessingJob.created_at)
            .limit(configured.forecast_job_batch_size)
        )
    )
    from app.forecast.publisher import run_job

    processed = []
    for job_id in queued_job_ids:
        job = run_job(db, job_id)
        if job is not None:
            processed.append(
                {
                    "job_id": str(job.id),
                    "spot_id": str(job.spot_id),
                    "status": job.status,
                    "error": job.error,
                }
            )
    return {
        "status": (
            "degraded" if any(item["status"] == "failed" for item in processed) else "ok"
        ),
        "enqueue": enqueue_report,
        "processed": processed,
    }
