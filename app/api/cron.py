"""Authenticated maintenance endpoints invoked by Vercel Cron."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.admin.deps import get_extract_client
from app.config import get_settings
from app.db.session import get_db

router = APIRouter(prefix="/cron", tags=["maintenance"])


def _require_cron(request: Request) -> None:
    expected = get_settings().cron_secret
    provided = request.headers.get("Authorization")
    if not expected:
        raise HTTPException(status_code=503, detail="Cron maintenance is not configured.")
    if not provided or not secrets.compare_digest(provided, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/climatology", dependencies=[Depends(_require_cron)])
def maintain_climatology(
    db: Session = Depends(get_db),
    client=Depends(get_extract_client),
) -> dict:
    """Queue stale snapshots and process a bounded daily batch.

    Also sweeps expired media-search cache entries and old budget buckets — a
    cheap DELETE that rides along on the existing schedule, so the media picker
    needs no cron of its own.
    """
    from app.admin.era5_worker import process_due_batch
    from app.media.budget import sweep_expired

    result = process_due_batch(
        db,
        client=client,
        limit=min(max(get_settings().climatology_cron_batch_size, 1), 5),
    )
    try:
        result["media"] = sweep_expired(db)
    except Exception as exc:  # never let housekeeping fail the climatology run
        db.rollback()
        result["media"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from app.forecast.publisher import run_job
        from app.models import ForecastProcessingJob
        jobs = db.scalars(select(ForecastProcessingJob).where(ForecastProcessingJob.status == "queued").order_by(ForecastProcessingJob.created_at).limit(get_settings().forecast_job_batch_size)).all()
        result["forecast"] = [{"id": str(job.id), "status": run_job(db, job.id).status} for job in jobs]
    except Exception as exc:
        db.rollback()
        result["forecast"] = {"error": f"{type(exc).__name__}: {exc}"}
    return result
