"""Retention that always protects the active and immediately previous field."""

from __future__ import annotations

from sqlalchemy import select

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.spatial_fields.storage import FieldObjectStorage


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
        retained_cycles: list = []
        for run in runs:
            if run.model_run_at not in retained_cycles:
                retained_cycles.append(run.model_run_at)
            if len(retained_cycles) >= retain_runs:
                break
        retained = {
            run.id for run in runs if run.model_run_at in retained_cycles
        } | protected_run_ids
        for run in runs:
            if run.id in retained or run.status not in {
                "ready",
                "rejected",
                "failed",
                "expired",
            }:
                continue
            assets = db.scalars(
                select(WeatherFieldAsset).where(
                    WeatherFieldAsset.run_id == run.id,
                    WeatherFieldAsset.status != "deleted",
                )
            ).all()
            candidate_runs += 1
            candidate_assets += len(assets)
            run_bytes = sum(asset.size_bytes for asset in assets)
            candidate_bytes += run_bytes
            candidates.append(
                {
                    "run_id": str(run.id),
                    "model": run.model_key,
                    "model_run": run.model_run_at.isoformat(),
                    "status": run.status,
                    "assets": len(assets),
                    "bytes": run_bytes,
                }
            )
            if dry_run:
                continue
            run_failed = False
            for asset in assets:
                try:
                    storage.delete(asset.object_key)
                    asset.status = "deleted"
                    deleted_assets += 1
                    deleted_bytes += asset.size_bytes
                except Exception as exc:
                    run_failed = True
                    errors.append(
                        {
                            "run_id": str(run.id),
                            "asset_id": str(asset.id),
                            "error": type(exc).__name__,
                        }
                    )
            if not run_failed:
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
