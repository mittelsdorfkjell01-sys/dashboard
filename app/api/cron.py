"""Authenticated maintenance endpoints invoked by Vercel Cron."""

from __future__ import annotations

import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, select

from app.config import get_settings
from app.db.session import get_db

router = APIRouter(prefix="/cron", tags=["maintenance"])
logger = logging.getLogger(__name__)


def _require_cron(request: Request) -> None:
    expected = get_settings().cron_secret
    provided = request.headers.get("Authorization")
    if not expected:
        logger.error("cron_auth_configuration_missing")
        raise HTTPException(
            status_code=503, detail="Cron maintenance is not configured."
        )
    if not provided or not secrets.compare_digest(provided, f"Bearer {expected}"):
        logger.warning("cron_auth_rejected")
        raise HTTPException(status_code=401, detail="Unauthorized")
    logger.info("cron_auth_accepted")


@router.post(
    "/weather-shadow",
    dependencies=[Depends(_require_cron)],
    status_code=status.HTTP_202_ACCEPTED,
)
def collect_weather_shadow(db: Session = Depends(get_db)) -> dict:
    """Atomically enqueue one model generation and return without provider I/O."""
    from app.weather.shadow_jobs import enqueue_shadow_cycle

    job, created = enqueue_shadow_cycle(db)
    return {
        "status": "accepted" if created else "deduplicated",
        "job_id": str(job.id),
        "job_status": job.status,
        "study_version": job.options.get("study_version"),
        "model_run": job.options.get("model_run"),
        "public_effect": "none",
    }


@router.get("/climatology", dependencies=[Depends(_require_cron)])
def maintain_climatology(
    db: Session = Depends(get_db),
) -> dict:
    """Queue stale snapshots and process a bounded daily batch.

    Also sweeps expired media-search cache entries and old budget buckets — a
    cheap DELETE that rides along on the existing schedule, so the media picker
    needs no cron of its own.
    """
    from app.media.budget import sweep_expired
    result = {}
    try:
        result["media"] = sweep_expired(db)
    except Exception as exc:  # never let housekeeping fail the climatology run
        db.rollback()
        result["media"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from datetime import datetime, timezone
        from app.forecast.publisher import enqueue, run_job
        from app.models import ForecastProcessingJob, ForecastSnapshot, Spot

        limit = get_settings().forecast_job_batch_size
        candidates = db.scalars(
            select(Spot)
            .outerjoin(
                ForecastSnapshot,
                (ForecastSnapshot.spot_id == Spot.id)
                & ForecastSnapshot.active.is_(True),
            )
            .where(
                Spot.status == "published",
                or_(
                    ForecastSnapshot.id.is_(None),
                    ForecastSnapshot.valid_until < datetime.now(timezone.utc),
                ),
            )
            .order_by(Spot.updated_at)
            .limit(limit)
        ).all()
        for spot in candidates:
            enqueue(db, spot.id, reason="cron")
        jobs = db.scalars(
            select(ForecastProcessingJob)
            .where(ForecastProcessingJob.status == "queued")
            .order_by(ForecastProcessingJob.created_at)
            .limit(get_settings().forecast_job_batch_size)
        ).all()
        result["forecast"] = [
            {"id": str(job.id), "status": run_job(db, job.id).status} for job in jobs
        ]
    except Exception as exc:
        db.rollback()
        result["forecast"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        # Publish today's featured list off the visitor request path. Combined
        # with the retained previous-day entry, the landing page is instant
        # even across the UTC date rollover and a serverless cold start.
        from app.discovery.warmup import warm_once

        # /spots/top?limit=5 ranks eight candidates before safe serialization.
        warmed = warm_once(limits=[8], sports=[None], db=db)
        result["featured"] = {"spots": warmed[0][2] if warmed else 0}
    except Exception as exc:
        db.rollback()
        result["featured"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from app.models import WindClimatologyRun
        from app.wind_climatology.service import backfill, process

        backfill(db, limit=2)
        queued = db.scalars(select(WindClimatologyRun).where(WindClimatologyRun.status == "pending").order_by(WindClimatologyRun.created_at).limit(1)).all()
        result["wind_climatology_v2"] = [{"id": str(run.id), "status": process(db, run.id).status} for run in queued]
    except Exception as exc:
        db.rollback()
        result["wind_climatology_v2"] = {"error": f"{type(exc).__name__}: {exc}"}
    return result
