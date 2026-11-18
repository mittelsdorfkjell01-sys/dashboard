"""Retention that always protects the active and immediately previous field."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldJob,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.spatial_fields.storage import FieldObjectStorage


DELETE_COMMIT_BATCH_SIZE = 100


def tracked_weather_field_storage_bytes(db) -> int:
    """Return bytes still owned by the field asset ledger."""
    return int(
        db.scalar(
            select(func.coalesce(func.sum(WeatherFieldAsset.size_bytes), 0)).where(
                WeatherFieldAsset.status != "deleted"
            )
        )
        or 0
    )


def fail_stale_unmanaged_runs(
    db,
    *,
    model_key: str,
    stale_before: datetime,
    now: datetime | None = None,
) -> list[str]:
    """Fail abandoned direct-publisher runs without touching active worker jobs."""
    active_job_run_ids = set(
        db.scalars(
            select(WeatherFieldJob.run_id).where(
                WeatherFieldJob.status == "processing",
                WeatherFieldJob.run_id.is_not(None),
            )
        ).all()
    )
    runs = db.scalars(
        select(WeatherFieldRun)
        .where(
            WeatherFieldRun.model_key == model_key,
            WeatherFieldRun.status.in_(
                {"downloading", "processing", "quality_pending"}
            ),
            WeatherFieldRun.started_at < stale_before,
        )
        .with_for_update(skip_locked=True)
    ).all()
    failed_ids: list[str] = []
    completed_at = now or datetime.now(timezone.utc)
    for run in runs:
        if run.id in active_job_run_ids:
            continue
        run.status = "failed"
        run.completed_at = completed_at
        run.error = "direct publisher exceeded processing stale threshold"
        failed_ids.append(str(run.id))
    if failed_ids:
        db.commit()
    return failed_ids


def prune_weather_field_runs(
    db,
    *,
    storage: FieldObjectStorage,
    retain_runs: int,
    dry_run: bool = False,
) -> dict:
    publications = db.scalars(
        select(WeatherFieldPublication).where(
            WeatherFieldPublication.active.is_(True)
        )
    ).all()
    protected_run_ids = {publication.run_id for publication in publications}
    previous_ids = {
        publication.supersedes_publication_id
        for publication in publications
        if publication.supersedes_publication_id is not None
    }
    if previous_ids:
        protected_run_ids.update(
            db.scalars(
                select(WeatherFieldPublication.run_id).where(
                    WeatherFieldPublication.id.in_(previous_ids)
                )
            ).all()
        )

    models = db.scalars(select(WeatherFieldRun.model_id).distinct()).all()
    expired_runs = 0
    deleted_assets = 0
    deleted_bytes = 0
    candidate_runs = 0
    candidate_assets = 0
    candidate_bytes = 0
    candidates: list[dict] = []
    errors: list[dict] = []
    for model_id in models:
        runs = db.scalars(
            select(WeatherFieldRun)
            .where(WeatherFieldRun.model_id == model_id)
            .order_by(WeatherFieldRun.model_run_at.desc(), WeatherFieldRun.created_at.desc())
        ).all()
        # Retention is defined in model cycles, not raw run rows. Retries and
        # reprocessing versions of one cycle must not crowd an older distinct
        # cycle out of the shadow-readiness window.
        retainable_statuses = {"ready", "rejected"}
        retained_cycles: list = []
        for run in runs:
            if run.status not in retainable_statuses:
                continue
            if run.model_run_at not in retained_cycles:
                retained_cycles.append(run.model_run_at)
            if len(retained_cycles) >= retain_runs:
                break
        retained = {
            run.id
            for run in runs
            if run.status in retainable_statuses
            and run.model_run_at in retained_cycles
        } | protected_run_ids
        for run in runs:
            if run.id in retained or run.status not in {
                "ready",
                "rejected",
                "failed",
                "expired",
            }:
                continue
            run_id = run.id
            assets = db.scalars(
                select(WeatherFieldAsset).where(
                    WeatherFieldAsset.run_id == run_id,
                    WeatherFieldAsset.status != "deleted",
                )
            ).all()
            asset_records = [
                (asset.id, asset.object_key, asset.size_bytes) for asset in assets
            ]
            candidate_runs += 1
            candidate_assets += len(asset_records)
            run_bytes = sum(size_bytes for _, _, size_bytes in asset_records)
            candidate_bytes += run_bytes
            candidates.append(
                {
                    "run_id": str(run.id),
                    "model": run.model_key,
                    "model_run": run.model_run_at.isoformat(),
                    "status": run.status,
                    "assets": len(asset_records),
                    "bytes": run_bytes,
                }
            )
            if dry_run:
                continue
            # Object-store I/O can take minutes for a large failed run. End the
            # read transaction first so serverless Postgres does not terminate
            # an otherwise idle connection while objects are deleted.
            db.commit()
            run_failed = False
            deleted_batch: list = []
            for asset_id, object_key, size_bytes in asset_records:
                try:
                    storage.delete(object_key)
                    deleted_batch.append(asset_id)
                    deleted_assets += 1
                    deleted_bytes += size_bytes
                    if len(deleted_batch) >= DELETE_COMMIT_BATCH_SIZE:
                        db.execute(
                            update(WeatherFieldAsset)
                            .where(WeatherFieldAsset.id.in_(deleted_batch))
                            .values(status="deleted")
                        )
                        db.commit()
                        deleted_batch.clear()
                except Exception as exc:
                    run_failed = True
                    errors.append(
                        {
                            "run_id": str(run_id),
                            "asset_id": str(asset_id),
                            "error": type(exc).__name__,
                        }
                    )
            if deleted_batch:
                db.execute(
                    update(WeatherFieldAsset)
                    .where(WeatherFieldAsset.id.in_(deleted_batch))
                    .values(status="deleted")
                )
                db.commit()
            if not run_failed:
                run = db.get(WeatherFieldRun, run_id)
                run.status = "expired"
                expired_runs += 1
        if not dry_run:
            db.commit()
    return {
        "dry_run": dry_run,
        "candidate_runs": candidate_runs,
        "candidate_assets": candidate_assets,
        "candidate_bytes": candidate_bytes,
        "candidates": candidates,
        "expired_runs": expired_runs,
        "deleted_assets": deleted_assets,
        "deleted_bytes": deleted_bytes,
        "protected_runs": len(protected_run_ids),
        "errors": errors,
    }
