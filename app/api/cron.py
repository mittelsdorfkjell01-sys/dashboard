"""Authenticated maintenance endpoints invoked by Vercel Cron."""

from __future__ import annotations

import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select

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

    Also sweeps expired media-search cache/budget rows and archives a bounded
    batch of old terminal image cases, so media maintenance needs no second
    scheduled endpoint.
    """
    from app.media.budget import sweep_expired
    result = {}
    try:
        result["media"] = sweep_expired(db)
    except Exception:  # never let housekeeping fail the climatology run
        db.rollback()
        logger.exception("cron_media_sweep_failed")
        result["media"] = {"error": "internal_error"}
    try:
        from app.media.archive import archive_retired_images

        settings = get_settings()
        result["media_archive"] = archive_retired_images(
            db,
            retention_days=settings.image_archive_retention_days,
            limit=settings.image_archive_batch_size,
        )
    except Exception:
        db.rollback()
        logger.exception("cron_media_archive_failed")
        result["media_archive"] = {"error": "internal_error"}
    result["media_gc"] = {}
    try:
        from app.media.gc import audit_blob_orphans

        result["media_gc"]["audit"] = audit_blob_orphans(db)
    except Exception:
        db.rollback()
        logger.exception("cron_media_gc_audit_failed")
        result["media_gc"]["audit"] = {"error": "internal_error"}
    try:
        from app.media.gc import collect_media_garbage

        result["media_gc"]["collect"] = collect_media_garbage(db)
    except Exception:
        db.rollback()
        logger.exception("cron_media_gc_collect_failed")
        result["media_gc"]["collect"] = {"error": "internal_error"}
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
    except Exception:
        db.rollback()
        logger.exception("cron_forecast_refresh_failed")
        result["forecast"] = {"error": "internal_error"}
    try:
        # Publish today's featured list off the visitor request path. Combined
        # with the retained previous-day entry, the landing page is instant
        # even across the UTC date rollover and a serverless cold start.
        from app.discovery.warmup import warm_once

        # /spots/top?limit=5 ranks eight candidates before safe serialization.
        warmed = warm_once(limits=[8], sports=[None], db=db)
        result["featured"] = {"spots": warmed[0][2] if warmed else 0}
    except Exception:
        db.rollback()
        logger.exception("cron_featured_warmup_failed")
        result["featured"] = {"error": "internal_error"}
    return result


@router.get("/observations", dependencies=[Depends(_require_cron)])
def collect_observations(db: Session = Depends(get_db)) -> dict:
    """Import a bounded batch of due station observations (validation only).

    Observations are stored for verification/calibration and never enter a
    forecast value. Idempotent through the observation uniqueness constraint;
    repeated cron invocations drain the active-station catalogue.
    """
    settings = get_settings()
    try:
        from app.weather.observation_worker import run_observation_import

        return run_observation_import(
            db, limit=settings.weather_observation_cron_batch_size, dry_run=False
        )
    except Exception:
        db.rollback()
        logger.exception("cron_observation_import_failed")
        return {"error": "internal_error"}


@router.get("/verification", dependencies=[Depends(_require_cron)])
def run_verification(db: Session = Depends(get_db)) -> dict:
    """Refresh model calibration stats and the raw-forecast verification scores.

    Calibration recompute keeps the existing holdout activation gate (decisions
    land as ``pending_review``; no second gate is introduced). Scoring and
    calibration are isolated so one failure cannot mask the other.
    """
    settings = get_settings()
    result: dict = {}
    try:
        from app.weather.verification import recompute_calibrations

        result["calibrations_updated"] = recompute_calibrations(db, lookback_days=90)
    except Exception:
        db.rollback()
        logger.exception("cron_recompute_calibrations_failed")
        result["calibrations_updated"] = {"error": "internal_error"}
    try:
        from app.weather.verification import run_gated_verification_scoring

        # Scores the current serving baseline AND each spot's latest candidate
        # in one run, so the activation gate compares before/after over identical
        # samples/observations. Writes measurement rows only; no served value changes.
        result["verification"] = run_gated_verification_scoring(
            db, lookback_days=settings.weather_verification_lookback_days
        )
    except Exception:
        db.rollback()
        logger.exception("cron_verification_scoring_failed")
        result["verification"] = {"error": "internal_error"}
    try:
        from app.weather.sector_calibration import recalibrate_eligible_spots

        # Shrink sector factors from their WP3/WP5 prior towards measurement as
        # station data accumulates. Writes a disabled candidate version for a
        # later WP1-gated activation; never emits station wind as a forecast value.
        result["sector_calibration"] = recalibrate_eligible_spots(db)
    except Exception:
        db.rollback()
        logger.exception("cron_sector_calibration_failed")
        result["sector_calibration"] = {"error": "internal_error"}
    try:
        from app.weather.verification import prune_forecast_samples

        result["forecast_sample_retention"] = prune_forecast_samples(
            db,
            retention_days=settings.weather_forecast_sample_retention_days,
            batch_size=settings.weather_forecast_sample_retention_batch_size,
        )
    except Exception:
        db.rollback()
        logger.exception("cron_forecast_sample_retention_failed")
        result["forecast_sample_retention"] = {"error": "internal_error"}
    return result


@router.get("/build-sectors", dependencies=[Depends(_require_cron)])
def build_sectors(db: Session = Depends(get_db)) -> dict:
    """Build a bounded batch of CANDIDATE sector factors (never activated).

    Writes enabled=False candidates only; activation is a separate WP1-gated
    admin path, so this cannot change a served value. Resumable: spots are
    ordered by least-recently-built, so repeated invocations drain the full
    published catalogue without starving or double-running a spot.
    """
    settings = get_settings()
    try:
        from app.forecast.sector_runner import run_sector_producer

        limit = max(1, min(settings.sector_build_batch_size, 5))
        return run_sector_producer(db, producer="combined", limit=limit)
    except Exception:
        db.rollback()
        logger.exception("cron_build_sectors_failed")
        return {"error": "internal_error"}


@router.get("/wind-climatology", dependencies=[Depends(_require_cron)])
def maintain_wind_climatology(
    db: Session = Depends(get_db),
) -> dict:
    """Build a bounded batch of missing public wind-month datasets.

    This intentionally runs inside the public Vercel deployment so it always
    uses the same database as the read endpoint. Provider I/O is capped to a
    small batch; repeated cron invocations drain the full published catalogue.
    """
    from app.models import WindClimatologyRun
    from app.wind_climatology.service import backfill, process

    limit = max(1, min(get_settings().climatology_cron_batch_size, 3))
    queued = backfill(db, limit=limit)
    pending_ids = list(
        db.scalars(
            select(WindClimatologyRun.id)
            .where(WindClimatologyRun.status == "pending")
            .order_by(WindClimatologyRun.created_at)
            .limit(limit)
        )
    )

    ready = 0
    failed = 0
    for run_id in pending_ids:
        run = process(db, run_id)
        if run.status == "ready":
            ready += 1
        else:
            failed += 1

    remaining = db.scalar(
        select(func.count())
        .select_from(WindClimatologyRun)
        .where(WindClimatologyRun.status == "pending")
    ) or 0
    has_more = bool(remaining) or len(queued) == limit
    return {
        "status": "complete_with_failures" if failed else ("more" if has_more else "complete"),
        "newly_queued": len(queued),
        "processed": len(pending_ids),
        "ready": ready,
        "failed": failed,
        "pending": int(remaining),
    }
