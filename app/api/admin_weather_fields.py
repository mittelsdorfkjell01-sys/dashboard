"""Authenticated operations for the Europe weather-field pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import get_actor, require_role
from app.config import get_settings
from app.db.session import get_db
from app.models.weather_field import (
    WeatherFieldJob,
    WeatherFieldModel,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.models.weather_field_shadow import (
    WeatherFieldShadowMetric,
    WeatherFieldShadowRun,
)
from app.models import Spot
from app.spatial_fields.control_plane import get_or_create_run
from app.spatial_fields.monitoring import (
    WIND_FIELD_MODELS,
    wave_field_health,
    weather_field_health,
)
from app.spatial_fields.publication import (
    PublicationNotReady,
    activate_publication,
    rollback_publication,
)
from app.spatial_fields.storage import configured_field_storage
from app.spatial_fields.spot_forecast import assess_spot_field_readiness

router = APIRouter(
    prefix="/admin/weather-fields",
    tags=["admin-weather-fields"],
    dependencies=[Depends(require_role("admin", "curator"))],
)

# Contract-compatible diagnostic alias. It is mounted only when the admin API
# is enabled, so the public deployment does not expose an authentication surface.
diagnostic_router = APIRouter(
    prefix="/weather-fields/wind",
    tags=["admin-weather-fields"],
    dependencies=[Depends(require_role("admin", "curator"))],
)


class ConfirmOperation(BaseModel):
    confirm: bool
    reason: str = Field(min_length=3, max_length=500)


def _confirmed(body: ConfirmOperation) -> None:
    if not body.confirm:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required.")


def _run_payload(run: WeatherFieldRun) -> dict:
    return {
        "id": str(run.id),
        "provider": run.provider_key,
        "model": run.model_key,
        "model_run": run.model_run_at,
        "processing_version": run.processing_version,
        "status": run.status,
        "bytes_downloaded": run.bytes_downloaded,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error": run.error,
        "diagnostics": run.diagnostics,
    }


@router.get("/status")
def field_status(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return weather_field_health(
        db,
        storage=configured_field_storage(),
        settings=settings,
        model_keys=WIND_FIELD_MODELS,
    )


@router.get("/status/waves")
def wave_field_status(db: Session = Depends(get_db)) -> dict:
    return wave_field_health(
        db,
        storage=configured_field_storage(),
        settings=get_settings(),
    )


@router.get("/runs")
@diagnostic_router.get("/runs")
def field_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(WeatherFieldRun)
        .order_by(WeatherFieldRun.model_run_at.desc(), WeatherFieldRun.created_at.desc())
        .limit(limit)
    ).all()
    return {"runs": [_run_payload(row) for row in rows]}


@router.get("/jobs")
def field_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(WeatherFieldJob)
        .order_by(WeatherFieldJob.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "jobs": [
            {
                "id": str(row.id),
                "run_id": str(row.run_id) if row.run_id else None,
                "kind": row.kind,
                "status": row.status,
                "attempt_count": row.attempt_count,
                "scheduled_at": row.scheduled_at,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "diagnostics": row.diagnostics,
                "error": row.error,
            }
            for row in rows
        ]
    }


@router.get("/publications")
def field_publications(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(WeatherFieldPublication)
        .order_by(WeatherFieldPublication.generation.desc(), WeatherFieldPublication.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "publications": [
            {
                "id": str(row.id),
                "run_id": str(row.run_id),
                "status": row.status,
                "active": row.active,
                "generation": row.generation,
                "activated_at": row.activated_at,
                "actor": row.actor,
                "reason": row.reason,
            }
            for row in rows
        ]
    }


def _shadow_run_payload(row: WeatherFieldShadowRun) -> dict:
    return {
        "id": str(row.id),
        "job_id": str(row.job_id),
        "publication_id": str(row.publication_id),
        "field_run_id": str(row.field_run_id),
        "profile_version": row.profile_version,
        "status": row.status,
        "config": row.config,
        "diagnostics": row.diagnostics,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "error": row.error,
    }


@router.get("/shadow/status")
def shadow_validation_status(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    latest = db.scalar(
        select(WeatherFieldShadowRun)
        .order_by(WeatherFieldShadowRun.created_at.desc())
        .limit(1)
    )
    active = db.scalar(
        select(WeatherFieldPublication).where(
            WeatherFieldPublication.scope_key == settings.weather_field_scope_key,
            WeatherFieldPublication.active.is_(True),
        )
    )
    return {
        "enabled": settings.weather_field_shadow_enabled,
        "profile_version": settings.weather_field_shadow_profile_version,
        "pilot": {
            "config": settings.weather_field_shadow_pilot_config,
            "group": settings.weather_field_shadow_pilot_group,
            "max_spots": settings.weather_field_shadow_max_spots,
            "max_samples": settings.weather_field_shadow_max_samples,
            "max_horizon_hours": settings.weather_field_shadow_max_horizon_hours,
        },
        "active_publication_id": str(active.id) if active else None,
        "latest_run": _shadow_run_payload(latest) if latest else None,
        "spot_rollout": {
            "stage": settings.weather_field_spot_rollout_stage,
            "allow_unverified": settings.weather_field_spot_allow_unverified,
            "region_slugs": sorted(
                value.strip()
                for value in settings.weather_field_spot_rollout_region_slugs.split(",")
                if value.strip()
            ),
            "minimum_shadow_cycles": settings.weather_field_spot_min_shadow_cycles,
            "minimum_shadow_samples": settings.weather_field_spot_min_shadow_samples,
            "minimum_observation_matches": settings.weather_field_spot_min_observations,
        },
        "cutover_authorized": False,
    }


@router.get("/spot-rollout/{spot_id}")
def spot_rollout_readiness(
    spot_id: uuid.UUID, db: Session = Depends(get_db)
) -> dict:
    spot = db.scalar(
        select(Spot)
        .where(Spot.id == spot_id)
        .options(selectinload(Spot.region))
    )
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found.")
    return assess_spot_field_readiness(
        db, spot=spot, settings=get_settings()
    ).model_dump()


@router.get("/shadow/runs")
def shadow_validation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(WeatherFieldShadowRun)
        .order_by(WeatherFieldShadowRun.created_at.desc())
        .limit(limit)
    ).all()
    return {"runs": [_shadow_run_payload(row) for row in rows]}


@router.get("/shadow/metrics")
def shadow_validation_metrics(
    run_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    selected_run = run_id
    if selected_run is None:
        selected_run = db.scalar(
            select(WeatherFieldShadowRun.id)
            .where(WeatherFieldShadowRun.status == "succeeded")
            .order_by(WeatherFieldShadowRun.created_at.desc())
            .limit(1)
        )
    if selected_run is None:
        return {"run_id": None, "metrics": []}
    rows = db.scalars(
        select(WeatherFieldShadowMetric)
        .where(WeatherFieldShadowMetric.shadow_run_id == selected_run)
        .order_by(WeatherFieldShadowMetric.sample_count.desc())
        .limit(limit)
    ).all()
    return {
        "run_id": str(selected_run),
        "metrics": [
            {
                "dimensions": row.dimensions,
                "sample_count": row.sample_count,
                "metrics": row.metrics,
                "computed_at": row.computed_at,
            }
            for row in rows
        ],
    }


@router.post("/jobs/discover", status_code=202)
def discover_fields(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.weather_field_pipeline_enabled:
        raise HTTPException(status_code=409, detail="Weather-field pipeline is disabled.")
    from app.spatial_fields.jobs import enqueue_discovery

    job, created = enqueue_discovery(db)
    return {"job_id": str(job.id), "status": "accepted" if created else "deduplicated"}


@router.post("/jobs/shadow-validation", status_code=202)
def validate_field_shadow(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.weather_field_shadow_enabled:
        raise HTTPException(status_code=409, detail="Weather-field shadow validation is disabled.")
    from app.spatial_fields.jobs import enqueue_shadow_validation

    job, created = enqueue_shadow_validation(db, settings=settings)
    if job is None:
        raise HTTPException(status_code=409, detail="No active weather-field publication.")
    return {
        "job_id": str(job.id),
        "status": "accepted" if created else "deduplicated",
        "public_effect": "none",
    }


@router.post("/jobs/retention", status_code=202)
def retain_fields(db: Session = Depends(get_db)) -> dict:
    from app.spatial_fields.jobs import enqueue_retention

    job, created = enqueue_retention(db)
    return {"job_id": str(job.id), "status": "accepted" if created else "deduplicated"}


@router.post("/runs/{run_id}/reprocess", status_code=202)
def reprocess_field_run(
    run_id: uuid.UUID,
    body: ConfirmOperation,
    actor: str = Depends(get_actor),
    db: Session = Depends(get_db),
) -> dict:
    from app.spatial_fields.jobs import enqueue_process_run

    _confirmed(body)
    original = db.get(WeatherFieldRun, run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Weather-field run not found.")
    model = db.get(WeatherFieldModel, original.model_id)
    if model is None or model.status != "active":
        raise HTTPException(status_code=409, detail="Weather-field model is not active.")
    version = f"{original.processing_version}-reprocess-{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}"
    clone = get_or_create_run(
        db,
        model=model,
        model_run_at=original.model_run_at,
        processing_version=version,
        contract_version=original.contract_version,
        coverage=original.coverage,
        native_grid={"status": "pending_source_inspection"},
        valid_times=original.valid_times,
        source_metadata={
            **(original.source_metadata or {}),
            "reprocess_of": str(original.id),
            "requested_by": actor,
            "reason": body.reason,
        },
    )
    job, _ = enqueue_process_run(db, clone)
    db.commit()
    return {"run_id": str(clone.id), "job_id": str(job.id), "status": "accepted"}


@router.post("/publications/{publication_id}/activate")
def activate_field_publication(
    publication_id: uuid.UUID,
    body: ConfirmOperation,
    actor: str = Depends(get_actor),
    db: Session = Depends(get_db),
) -> dict:
    _confirmed(body)
    try:
        publication = activate_publication(
            db,
            publication_id,
            actor=actor,
            reason=body.reason,
            rollout_policy=get_settings(),
        )
        db.commit()
    except PublicationNotReady as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"reasons": exc.reasons}) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"publication_id": str(publication.id), "generation": publication.generation, "status": publication.status}


@router.post("/publications/{publication_id}/rollback")
def rollback_field_publication(
    publication_id: uuid.UUID,
    body: ConfirmOperation,
    actor: str = Depends(get_actor),
    db: Session = Depends(get_db),
) -> dict:
    _confirmed(body)
    try:
        publication = rollback_publication(
            db,
            scope_key=get_settings().weather_field_scope_key,
            restore_publication_id=publication_id,
            actor=actor,
            reason=body.reason,
        )
        db.commit()
    except PublicationNotReady as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"reasons": exc.reasons}) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"publication_id": str(publication.id), "generation": publication.generation, "status": publication.status}
