"""Bounded retention for high-churn operational tables."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from app.models import (
    ForecastProcessingJob,
    ForecastSnapshot,
    RecommendationLog,
    WeatherLiveWindHoldoutCase,
    WeatherLiveWindJob,
)


def prune_operational_history(
    db: Session,
    *,
    snapshot_days: int,
    job_days: int,
    failed_job_days: int,
    recommendation_days: int,
    live_wind_job_days: int,
    live_wind_failed_job_days: int,
    batch_size: int,
    now: datetime | None = None,
) -> dict[str, int]:
    """Delete at most one bounded batch per table, preserving active work."""
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    limit = max(1, batch_size)

    snapshot_ids = (
        select(ForecastSnapshot.id)
        .where(
            ForecastSnapshot.active.is_(False),
            ForecastSnapshot.generated_at < instant - timedelta(days=snapshot_days),
        )
        .order_by(ForecastSnapshot.generated_at)
        .limit(limit)
    )
    job_ids = (
        select(ForecastProcessingJob.id)
        .where(
            or_(
                (
                    ForecastProcessingJob.status.in_(("succeeded", "superseded"))
                    & (
                        ForecastProcessingJob.finished_at
                        < instant - timedelta(days=job_days)
                    )
                ),
                (
                    (ForecastProcessingJob.status == "failed")
                    & (
                        ForecastProcessingJob.finished_at
                        < instant - timedelta(days=failed_job_days)
                    )
                ),
            ),
        )
        .order_by(ForecastProcessingJob.finished_at)
        .limit(limit)
    )
    recommendation_ids = (
        select(RecommendationLog.id)
        .where(
            RecommendationLog.created_at
            < instant - timedelta(days=recommendation_days)
        )
        .order_by(RecommendationLog.created_at)
        .limit(limit)
    )
    referenced_holdout = exists(
        select(WeatherLiveWindHoldoutCase.id).where(
            WeatherLiveWindHoldoutCase.shadow_job_id == WeatherLiveWindJob.id
        )
    )
    live_wind_job_ids = (
        select(WeatherLiveWindJob.id)
        .where(
            ~referenced_holdout,
            or_(
                (
                    (WeatherLiveWindJob.status == "succeeded")
                    & (
                        WeatherLiveWindJob.finished_at
                        < instant - timedelta(days=live_wind_job_days)
                    )
                ),
                (
                    (WeatherLiveWindJob.status == "failed")
                    & (
                        WeatherLiveWindJob.finished_at
                        < instant - timedelta(days=live_wind_failed_job_days)
                    )
                ),
            ),
        )
        .order_by(WeatherLiveWindJob.finished_at)
        .limit(limit)
    )

    counts = {
        "forecast_snapshots": int(
            db.execute(delete(ForecastSnapshot).where(ForecastSnapshot.id.in_(snapshot_ids))).rowcount
            or 0
        ),
        "forecast_jobs": int(
            db.execute(
                delete(ForecastProcessingJob).where(ForecastProcessingJob.id.in_(job_ids))
            ).rowcount
            or 0
        ),
        "recommendation_logs": int(
            db.execute(
                delete(RecommendationLog).where(RecommendationLog.id.in_(recommendation_ids))
            ).rowcount
            or 0
        ),
        "live_wind_jobs": int(
            db.execute(
                delete(WeatherLiveWindJob).where(
                    WeatherLiveWindJob.id.in_(live_wind_job_ids)
                )
            ).rowcount
            or 0
        ),
    }
    db.commit()
    return counts
