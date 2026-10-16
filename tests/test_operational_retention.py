"""Bounded retention policy for disposable operational history."""

from datetime import datetime, timedelta, timezone
import uuid

from geoalchemy2 import WKTElement
from sqlalchemy import func, select

from app.db.retention import prune_operational_history
from app.models import (
    ForecastProcessingJob,
    ForecastSnapshot,
    RecommendationLog,
    Region,
    Spot,
    WeatherLiveWindJob,
)


def test_operational_retention_keeps_active_recent_and_failed_evidence(db):
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"retention-{suffix}",
        name="Retention Fixture",
        country="DE",
        status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"retention-{suffix}",
        name="Retention Fixture",
        region_id=region.id,
        location=WKTElement("POINT(10 54)", srid=4326),
        status="published",
        sports=["wind"],
        water_type=["sea"],
    )
    db.add(spot)
    db.flush()

    def snapshot(age: int, *, active: bool):
        generated = now - timedelta(days=age)
        return ForecastSnapshot(
            spot_id=spot.id,
            generated_at=generated,
            valid_until=generated + timedelta(days=10),
            consensus_version="test",
            physics_version="test",
            quality_level="baseline",
            fallback_status="none",
            payload={},
            active=active,
        )

    db.add_all(
        [snapshot(8, active=False), snapshot(6, active=False), snapshot(30, active=True)]
    )
    for status, age in (("succeeded", 8), ("failed", 15), ("failed", 8), ("queued", 30)):
        db.add(
            ForecastProcessingJob(
                spot_id=spot.id,
                kind="retention-test",
                status=status,
                idempotency_key=f"retention-{suffix}-{status}-{age}",
                finished_at=None if status == "queued" else now - timedelta(days=age),
            )
        )
    for age in (31, 29):
        db.add(
            RecommendationLog(
                user_ref=f"anon:{suffix}:{age}",
                audience_segment="anonymous",
                spot_id=spot.id,
                surface="now",
                window_start=now - timedelta(days=age),
                components={},
                params_version=1,
                profile_fingerprint="f" * 64,
                created_at=now - timedelta(days=age),
            )
        )
    for status, age in (("succeeded", 8), ("failed", 15), ("failed", 8), ("processing", 30)):
        db.add(
            WeatherLiveWindJob(
                spot_id=spot.id,
                cycle_at=now - timedelta(days=age),
                rollout_stage="shadow",
                analysis_version=f"retention-{status}-{age}",
                status=status,
                finished_at=(
                    None if status == "processing" else now - timedelta(days=age)
                ),
            )
        )
    db.commit()

    counts = prune_operational_history(
        db,
        snapshot_days=7,
        job_days=7,
        failed_job_days=14,
        recommendation_days=30,
        live_wind_job_days=7,
        live_wind_failed_job_days=14,
        batch_size=100,
        now=now,
    )

    assert counts == {
        "forecast_snapshots": 1,
        "forecast_jobs": 2,
        "recommendation_logs": 1,
        "live_wind_jobs": 2,
    }
    assert db.scalar(
        select(func.count()).select_from(ForecastSnapshot).where(
            ForecastSnapshot.spot_id == spot.id
        )
    ) == 2
    assert db.scalar(
        select(func.count()).select_from(ForecastProcessingJob).where(
            ForecastProcessingJob.spot_id == spot.id
        )
    ) == 2
    assert db.scalar(
        select(func.count()).select_from(RecommendationLog).where(
            RecommendationLog.spot_id == spot.id
        )
    ) == 1
    assert db.scalar(
        select(func.count()).select_from(WeatherLiveWindJob).where(
            WeatherLiveWindJob.spot_id == spot.id
        )
    ) == 2

    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()
