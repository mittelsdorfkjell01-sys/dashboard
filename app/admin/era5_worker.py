"""Durable climatology queue and serverless-safe worker helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from app.db.session import SessionLocal
from app.era5.freshness import (
    CLIMATOLOGY_ALGORITHM_VERSION,
    expected_window,
    stale_reasons,
    state,
)
from app.models import Era5Job, Spot

MAX_ATTEMPTS = 3
RETRY_DELAYS = (timedelta(minutes=15), timedelta(hours=6))
STUCK_AFTER = timedelta(minutes=20)


def _latest_job(db, spot_id) -> Era5Job | None:
    return db.scalar(
        select(Era5Job)
        .where(Era5Job.spot_id == spot_id)
        .order_by(Era5Job.created_at.desc())
    )


def _params(job: Era5Job) -> dict:
    return dict(job.params or {})


def _parse_instant(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def mark_failed(db, spot_id, detail: str, *, job_id=None) -> str:
    """Persist an error and schedule bounded retries before final failure."""
    job = db.get(Era5Job, job_id) if job_id is not None else _latest_job(db, spot_id)
    if job is None:
        return "failed"
    now = datetime.now(timezone.utc)
    params = _params(job)
    attempts = int(params.get("attempt_count") or 0)
    job.error = detail[:2000]
    if attempts < MAX_ATTEMPTS:
        delay = RETRY_DELAYS[min(max(attempts - 1, 0), len(RETRY_DELAYS) - 1)]
        params["next_attempt_at"] = (now + delay).isoformat()
        job.status = "queued"
        job.completed_at = None
    else:
        params["next_attempt_at"] = None
        job.status = "failed"
        job.completed_at = now
    job.params = params
    db.commit()
    return job.status


def count_queued(db) -> int:
    return int(
        db.scalar(
            select(func.count(func.distinct(Era5Job.spot_id))).where(
                Era5Job.status.in_(("queued", "processing", "extracting"))
            )
        )
        or 0
    )


def climatology_summary(db) -> dict[str, int]:
    """Freshness counters for the passive dashboard status summary."""
    spots = db.scalars(select(Spot).where(Spot.status != "archived")).all()
    counts = {"missing": 0, "stale": 0, "current": 0, "failed": 0}
    latest_by_spot: dict = {}
    jobs = db.scalars(select(Era5Job).order_by(Era5Job.created_at.desc())).all()
    for job in jobs:
        if job.spot_id is not None and job.spot_id not in latest_by_spot:
            latest_by_spot[job.spot_id] = job
    for spot in spots:
        freshness = state(spot)
        latest = latest_by_spot.get(spot.id)
        if latest is not None and latest.status == "failed" and freshness != "current":
            counts["failed"] += 1
        else:
            counts[freshness] += 1
    return counts


def enqueue_refreshes(db, *, client, limit: int = 100) -> int:
    """Ensure every missing/stale spot has one persistent queued job."""
    from app.admin.jobs import ACTIVE_JOB_STATUSES, trigger_era5_job

    active_spots = set(
        db.scalars(
            select(Era5Job.spot_id).where(Era5Job.status.in_(ACTIVE_JOB_STATUSES))
        ).all()
    )
    latest_by_spot: dict = {}
    for job in db.scalars(
        select(Era5Job).order_by(Era5Job.created_at.desc())
    ).all():
        if job.spot_id is not None and job.spot_id not in latest_by_spot:
            latest_by_spot[job.spot_id] = job
    priority = case((Spot.status == "published", 0), else_=1)
    spots = db.scalars(
        select(Spot)
        .where(Spot.status != "archived")
        .order_by(priority, Spot.updated_at.desc())
    ).all()
    queued = 0
    for spot in spots:
        if queued >= limit:
            break
        freshness = state(spot)
        if freshness == "current" or spot.id in active_spots:
            continue
        # A new draft waits for the explicit form button or Go Live. Published
        # spots may never remain without climate data after a transient failure.
        if freshness == "missing" and spot.status != "published":
            continue
        latest = latest_by_spot.get(spot.id)
        if latest is not None and latest.status == "failed":
            params = _params(latest)
            same_target = (
                params.get("window") == expected_window()
                and params.get("algorithm_version") == CLIMATOLOGY_ALGORITHM_VERSION
                and latest.cell == spot.era5_cell
            )
            if same_target:
                continue
        reasons = stale_reasons(spot)
        reason = "missing" if freshness == "missing" else (
            "annual_refresh" if "data_window" in reasons else "version_refresh"
        )
        trigger_era5_job(
            spot.id, db=db, client=client, force=True, reason=reason
        )
        active_spots.add(spot.id)
        queued += 1
    return queued


def _recover_stuck_jobs(db, now: datetime) -> int:
    jobs = db.scalars(
        select(Era5Job).where(
            Era5Job.status.in_(("processing", "extracting")),
            Era5Job.started_at < now - STUCK_AFTER,
        )
    ).all()
    for job in jobs:
        params = _params(job)
        params["next_attempt_at"] = None
        job.params = params
        job.status = "queued"
        job.error = "Vorheriger Lauf wurde unterbrochen und automatisch fortgesetzt."
    if jobs:
        db.commit()
    return len(jobs)


def claim_due_jobs(db, *, limit: int = 3) -> list[tuple]:
    """Atomically claim due jobs so overlapping cron calls cannot duplicate work."""
    now = datetime.now(timezone.utc)
    _recover_stuck_jobs(db, now)
    candidates = db.scalars(
        select(Era5Job)
        .join(Spot, Spot.id == Era5Job.spot_id)
        .where(Era5Job.status == "queued", Spot.status != "archived")
        .order_by(Era5Job.created_at)
        .with_for_update(skip_locked=True)
        .limit(1000)
    ).all()
    claimed: list[tuple] = []
    for job in candidates:
        due_at = _parse_instant(_params(job).get("next_attempt_at"))
        if due_at is not None and due_at > now:
            continue
        job.status = "processing"
        job.started_at = now
        claimed.append((job.id, job.spot_id))
        if len(claimed) >= limit:
            break
    db.commit()
    return claimed


def compute_now(spot_id, *, client, job_id=None) -> tuple[str, str]:
    """Compute and store one snapshot synchronously in its own DB session."""
    from app.era5 import pipeline

    db = SessionLocal()
    selected_job_id = job_id
    try:
        spot = db.get(Spot, spot_id)
        if spot is None:
            return "fail", "unknown spot"
        job = db.get(Era5Job, job_id) if job_id is not None else _latest_job(db, spot_id)
        if job is not None:
            selected_job_id = job.id
            params = _params(job)
            params["attempt_count"] = int(params.get("attempt_count") or 0) + 1
            params["next_attempt_at"] = None
            job.params = params
            job.status = "processing"
            job.error = None
            job.completed_at = None
            job.started_at = datetime.now(timezone.utc)
            db.commit()
        pipeline.derive_and_store(
            spot, db=db, client=client, job_id=selected_job_id
        )
        return "ok", "derived"
    except Exception as exc:
        db.rollback()
        detail = f"{type(exc).__name__}: {exc}"
        mark_failed(db, spot_id, detail, job_id=selected_job_id)
        return "fail", detail
    finally:
        db.close()


def process_due_batch(db, *, client, limit: int = 3) -> dict:
    """Schedule stale snapshots, then process one bounded serverless batch."""
    enqueued = enqueue_refreshes(db, client=client)
    claimed = claim_due_jobs(db, limit=limit)
    results = []
    for job_id, spot_id in claimed:
        outcome, detail = compute_now(spot_id, client=client, job_id=job_id)
        results.append(
            {"spot_id": str(spot_id), "status": outcome, "detail": detail}
        )
    summary = climatology_summary(db)
    return {
        "enqueued": enqueued,
        "processed": len(results),
        "succeeded": sum(item["status"] == "ok" for item in results),
        "failed": sum(item["status"] != "ok" for item in results),
        "remaining": count_queued(db),
        "freshness": summary,
        "results": results,
    }
