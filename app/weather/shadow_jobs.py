"""Queue and claim Phase-4 collection through the existing forecast job table."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models import ForecastProcessingJob
from app.weather.shadow_study import STUDY_VERSION

JOB_KIND = "weather_shadow_cycle"
MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=30)


def target_model_run(now: datetime | None = None) -> datetime:
    """Latest conservative GFS generation expected to be safely available."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    floored = now.replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=now.hour % 6
    )
    return floored - timedelta(hours=6)


def idempotency_key(model_run: datetime) -> str:
    return f"weather-shadow:{STUDY_VERSION}:{model_run:%Y%m%d%H}"


def enqueue_shadow_cycle(
    db, *, now: datetime | None = None
) -> tuple[ForecastProcessingJob, bool]:
    """Atomically insert one job per study/model generation."""
    model_run = target_model_run(now)
    key = idempotency_key(model_run)
    values = {
        "kind": JOB_KIND,
        "status": "queued",
        "idempotency_key": key,
        "requested_by": "cron",
        "progress": 0,
        "attempt_count": 0,
        "options": {
            "study_version": STUDY_VERSION,
            "model_run": model_run.isoformat(),
            "public_effect": "none",
        },
        "diagnostics": {
            "event": "scheduler_received",
            "reference_spots": 5,
            "public_effect": "none",
        },
    }
    inserted_id = db.scalar(
        insert(ForecastProcessingJob)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(ForecastProcessingJob.id)
    )
    db.commit()
    row = db.scalar(
        select(ForecastProcessingJob).where(
            ForecastProcessingJob.idempotency_key == key
        )
    )
    if row is None:  # pragma: no cover - database invariant
        raise RuntimeError("weather shadow job insert was not observable")
    return row, inserted_id is not None


def claim_shadow_cycle(db) -> ForecastProcessingJob | None:
    """Claim at most one queued/retryable job without overlapping workers."""
    stale_before = datetime.now(timezone.utc) - STALE_AFTER
    row = db.scalar(
        select(ForecastProcessingJob)
        .where(
            ForecastProcessingJob.kind == JOB_KIND,
            or_(
                ForecastProcessingJob.status == "queued",
                (
                    (ForecastProcessingJob.status == "failed")
                    & (ForecastProcessingJob.attempt_count < MAX_ATTEMPTS)
                ),
                (
                    (ForecastProcessingJob.status == "processing")
                    & (ForecastProcessingJob.started_at < stale_before)
                    & (ForecastProcessingJob.attempt_count < MAX_ATTEMPTS)
                ),
            ),
        )
        .order_by(ForecastProcessingJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        db.rollback()
        return None
    row.status = "processing"
    row.started_at = datetime.now(timezone.utc)
    row.finished_at = None
    row.progress = 5
    row.attempt_count += 1
    row.error = None
    row.diagnostics = {
        **(row.diagnostics or {}),
        "event": "worker_claimed",
        "attempt": row.attempt_count,
    }
    db.commit()
    db.refresh(row)
    return row


def run_next_shadow_cycle() -> dict:
    """Worker entrypoint. Collection stays outside the scheduler HTTP request."""
    with SessionLocal() as db:
        job = claim_shadow_cycle(db)
        if job is None:
            return {"status": "idle", "processed": 0, "public_effect": "none"}
        job_id = job.id
    try:
        from scripts.weather_phase4_initial import main as collect

        model_run = datetime.fromisoformat(job.options["model_run"])
        result = collect(model_run_override=model_run)
        with SessionLocal() as db:
            job = db.get(ForecastProcessingJob, job_id)
            job.status = "succeeded"
            job.progress = 100
            job.finished_at = datetime.now(timezone.utc)
            job.diagnostics = {
                **(job.diagnostics or {}),
                "event": "completed",
                "collector_status": result.get("status"),
                "forecast_points": result.get("forecast_points", 0),
                "provider_requests": result.get(
                    "requests", result.get("network_requests", 0)
                ),
                "provider_bytes": result.get("bytes", result.get("network_bytes", 0)),
                "reference_spots": 5,
                "public_effect": "none",
            }
            db.commit()
        return {"status": "succeeded", "processed": 1, "public_effect": "none"}
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(ForecastProcessingJob, job_id)
            job.status = "failed"
            job.progress = 0
            job.finished_at = datetime.now(timezone.utc)
            job.error = type(exc).__name__
            job.diagnostics = {
                **(job.diagnostics or {}),
                "event": "failed",
                "error_class": type(exc).__name__,
                "retryable": job.attempt_count < MAX_ATTEMPTS,
                "public_effect": "none",
            }
            db.commit()
        return {"status": "failed", "processed": 1, "public_effect": "none"}
