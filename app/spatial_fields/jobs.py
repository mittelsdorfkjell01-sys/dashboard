"""Queue and worker orchestration for the Phase-2 weather-field pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from sqlalchemy import select

from app.config import get_settings
from app.forecast.providers import ProviderUnavailable
from app.models.weather_field import (
    WeatherFieldJob,
    WeatherFieldModel,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.spatial_fields.catalog import sync_free_model_catalog
from app.spatial_fields.control_plane import get_or_create_run
from app.spatial_fields.forecast_profile import forecast_hours_for_model
from app.spatial_fields.pipeline import process_run, provider_for_model
from app.spatial_fields.providers import EUROPE_COVERAGE
from app.spatial_fields.retention import prune_weather_field_runs
from app.spatial_fields.storage import configured_field_storage


def _key(*parts: object) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _forecast_hours_for_model(model_key: str, hours: list[int]) -> list[int]:
    """Compatibility wrapper for callers and existing focused tests."""
    return forecast_hours_for_model(model_key, hours)


def _discovery_profile(
    settings, active_models: tuple[str, ...] = ()
) -> tuple[
    str,
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
    str,
]:
    version = settings.weather_field_processing_version
    forecast_hours = tuple(settings.weather_field_forecast_hours)
    wave_hours = tuple(getattr(settings, "wave_field_forecast_hours", range(0, 79)))
    global_wave_hours = tuple(
        getattr(settings, "wave_field_global_forecast_hours", range(0, 175, 3))
    )
    extended_wave_hours = tuple(
        getattr(settings, "wave_field_extended_forecast_hours", range(168, 241, 3))
    )
    profile = _key(
        version,
        *forecast_hours,
        "ewam",
        *wave_hours,
        "gwam",
        *global_wave_hours,
        "gfs-wave",
        *extended_wave_hours,
        *active_models,
    )[:16]
    return (
        version,
        forecast_hours,
        wave_hours,
        global_wave_hours,
        extended_wave_hours,
        profile,
    )


def enqueue_discovery(
    db,
    *,
    now: datetime | None = None,
    settings=None,
    model_keys: tuple[str, ...] | None = None,
) -> tuple[WeatherFieldJob, bool]:
    instant = now or datetime.now(timezone.utc)
    configured = settings or get_settings()
    bucket = instant.strftime("%Y%m%d%H")
    active_models = tuple(
        db.scalars(
            select(WeatherFieldModel.model_key)
            .where(WeatherFieldModel.status == "active")
            .order_by(WeatherFieldModel.model_key)
        ).all()
    )
    if model_keys is not None:
        requested = set(model_keys)
        active_models = tuple(key for key in active_models if key in requested)
    (
        processing_version,
        forecast_hours,
        wave_hours,
        global_wave_hours,
        extended_wave_hours,
        profile,
    ) = _discovery_profile(configured, active_models)
    idempotency_key = _key("weather-field", "discover", bucket, profile)
    current = db.scalar(
        select(WeatherFieldJob).where(
            WeatherFieldJob.idempotency_key == idempotency_key
        )
    )
    if current is not None:
        return current, False
    job = WeatherFieldJob(
        kind="discover",
        status="queued",
        idempotency_key=idempotency_key,
        scheduled_at=instant,
        options={
            "discovery_bucket": bucket,
            "ingestion_profile": profile,
            "processing_version": processing_version,
            "forecast_hours": list(forecast_hours),
            "wave_forecast_hours": list(wave_hours),
            "global_wave_forecast_hours": list(global_wave_hours),
            "extended_wave_forecast_hours": list(extended_wave_hours),
            "active_models": list(active_models),
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def enqueue_process_run(db, run: WeatherFieldRun) -> tuple[WeatherFieldJob, bool]:
    idempotency_key = _key("weather-field", "process", run.id, run.processing_version)
    current = db.scalar(
        select(WeatherFieldJob).where(
            WeatherFieldJob.idempotency_key == idempotency_key
        )
    )
    if current is not None:
        return current, False
    job = WeatherFieldJob(
        run_id=run.id,
        kind="process",
        status="queued",
        idempotency_key=idempotency_key,
        scheduled_at=datetime.now(timezone.utc),
        options={
            "model": run.model_key,
            "model_run": run.model_run_at.isoformat(),
            "retry_count": int((run.source_metadata or {}).get("retry_count", 0)),
        },
    )
    db.add(job)
    db.flush()
    return job, True


def enqueue_retention(db, *, now: datetime | None = None) -> tuple[WeatherFieldJob, bool]:
    instant = now or datetime.now(timezone.utc)
    bucket = instant.strftime("%Y%m%d")
    idempotency_key = _key("weather-field", "retention", bucket)
    current = db.scalar(
        select(WeatherFieldJob).where(
            WeatherFieldJob.idempotency_key == idempotency_key
        )
    )
    if current is not None:
        return current, False
    job = WeatherFieldJob(
        kind="retention",
        status="queued",
        idempotency_key=idempotency_key,
        scheduled_at=instant,
        options={"retention_bucket": bucket},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def enqueue_shadow_validation(
    db, *, now: datetime | None = None, settings=None
) -> tuple[WeatherFieldJob | None, bool]:
    """Queue one immutable Phase-5 comparison for the active publication."""
    configured = settings or get_settings()
    instant = now or datetime.now(timezone.utc)
    publication = db.scalar(
        select(WeatherFieldPublication).where(
            WeatherFieldPublication.scope_key == configured.weather_field_scope_key,
            WeatherFieldPublication.active.is_(True),
        )
    )
    if publication is None:
        return None, False
    idempotency_key = _key(
        "weather-field",
        "shadow-validate",
        publication.id,
        configured.weather_field_shadow_profile_version,
        instant.strftime("%Y%m%d%H"),
    )
    current = db.scalar(
        select(WeatherFieldJob).where(
            WeatherFieldJob.idempotency_key == idempotency_key
        )
    )
    if current is not None:
        return current, False
    job = WeatherFieldJob(
        run_id=publication.run_id,
        kind="shadow_validate",
        status="queued",
        idempotency_key=idempotency_key,
        scheduled_at=instant,
        options={
            "publication_id": str(publication.id),
            "profile_version": configured.weather_field_shadow_profile_version,
            "validation_bucket": instant.strftime("%Y%m%d%H"),
            "public_effect": "none",
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def _run_discovery(db, *, settings, now: datetime, options: dict | None = None) -> dict:
    job_options = options or {}
    frozen_active_models = {
        str(model_key) for model_key in job_options.get("active_models", ())
    }
    processing_version = str(
        job_options.get("processing_version", settings.weather_field_processing_version)
    )
    forecast_hours = [
        int(hour)
        for hour in job_options.get(
            "forecast_hours", settings.weather_field_forecast_hours
        )
    ]
    wave_forecast_hours = [
        int(hour)
        for hour in job_options.get(
            "wave_forecast_hours",
            job_options.get(
                "forecast_hours",
                getattr(settings, "wave_field_forecast_hours", range(0, 79)),
            ),
        )
    ]
    global_wave_forecast_hours = [
        int(hour)
        for hour in job_options.get(
            "global_wave_forecast_hours",
            job_options.get(
                "forecast_hours",
                getattr(settings, "wave_field_global_forecast_hours", range(0, 175, 3)),
            ),
        )
    ]
    extended_wave_forecast_hours = [
        int(hour)
        for hour in job_options.get(
            "extended_wave_forecast_hours",
            job_options.get(
                "forecast_hours",
                getattr(
                    settings,
                    "wave_field_extended_forecast_hours",
                    range(168, 241, 3),
                ),
            ),
        )
    ]
    catalog = sync_free_model_catalog(db)
    discovered = []
    for model in catalog:
        if model.status != "active":
            continue
        if frozen_active_models and model.model_key not in frozen_active_models:
            continue
        provider = provider_for_model(model.model_key, settings=settings)
        configured_hours = (
            wave_forecast_hours
            if model.model_key == "dwd-ewam"
            else global_wave_forecast_hours
            if model.model_key == "dwd-gwam"
            else extended_wave_forecast_hours
            if model.model_key == "noaa-gfs-wave"
            else forecast_hours
        )
        model_forecast_hours = [
            hour
            for hour in _forecast_hours_for_model(model.model_key, configured_hours)
            if hour <= model.max_horizon_hours
        ]
        model_run_at = provider.discover_latest(
            now, forecast_hours=model_forecast_hours
        )
        if model_run_at is None:
            discovered.append({"model": model.model_key, "status": "not_found"})
            continue
        valid_times = [
            (model_run_at + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")
            for hour in model_forecast_hours
        ]
        provider_coverage = getattr(provider, "coverage", None)
        if provider_coverage is None:
            model_coverage = model.coverage
            provider_coverage = (
                (
                    float(model_coverage["west"]),
                    float(model_coverage["south"]),
                    float(model_coverage["east"]),
                    float(model_coverage["north"]),
                )
                if all(
                    key in model_coverage
                    for key in ("west", "south", "east", "north")
                )
                else EUROPE_COVERAGE
            )
        west, south, east, north = provider_coverage
        model_processing_version = (
            getattr(settings, "wave_field_processing_version", processing_version)
            if (model.model_metadata or {}).get("product") == "wave"
            else processing_version
        )
        run = get_or_create_run(
            db,
            model=model,
            model_run_at=model_run_at,
            processing_version=model_processing_version,
            contract_version="weather-field-v2",
            coverage={"west": west, "south": south, "east": east, "north": north},
            native_grid={"status": "pending_source_inspection"},
            valid_times=valid_times,
            source_metadata={"discovered_by": "weather-field-worker"},
        )
        if run.status != "discovered":
            discovered.append(
                {
                    "model": model.model_key,
                    "model_run": model_run_at.isoformat(),
                    "run_id": str(run.id),
                    "run_status": run.status,
                    "process_job_id": None,
                    "process_job_created": False,
                    "reused": True,
                }
            )
            continue
        process_job, created = enqueue_process_run(db, run)
        discovered.append(
            {
                "model": model.model_key,
                "model_run": model_run_at.isoformat(),
                "run_id": str(run.id),
                "process_job_id": str(process_job.id),
                "process_job_created": created,
            }
        )
    db.commit()
    return {"models": discovered, "public_effect": "none"}


def claim_next_job(
    db,
    *,
    now: datetime | None = None,
    allowed_kinds: tuple[str, ...] | None = None,
) -> WeatherFieldJob | None:
    instant = now or datetime.now(timezone.utc)
    query = select(WeatherFieldJob).where(
        WeatherFieldJob.status == "queued",
        WeatherFieldJob.scheduled_at <= instant,
    )
    if allowed_kinds is not None:
        if not allowed_kinds:
            return None
        query = query.where(WeatherFieldJob.kind.in_(allowed_kinds))
    job = db.scalar(
        query
        .order_by(WeatherFieldJob.scheduled_at, WeatherFieldJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = "processing"
    job.started_at = instant
    job.attempt_count += 1
    db.commit()
    db.refresh(job)
    return job


def recover_stalled_jobs(db, *, settings, now: datetime | None = None) -> list[dict]:
    """Recover jobs abandoned by a terminated worker without mutating assets.

    A partially processed field run is immutable evidence and is therefore
    failed in place. A fresh run identity is queued for the same model cycle;
    discovery/retention jobs can be safely returned to their idempotent queue.
    """
    instant = now or datetime.now(timezone.utc)
    stalled_before = instant - timedelta(
        minutes=settings.weather_field_processing_stale_minutes
    )
    jobs = db.scalars(
        select(WeatherFieldJob)
        .where(
            WeatherFieldJob.status == "processing",
            WeatherFieldJob.started_at < stalled_before,
        )
        .order_by(WeatherFieldJob.started_at)
        .with_for_update(skip_locked=True)
    ).all()
    recovered: list[dict] = []
    for job in jobs:
        reason = "worker heartbeat exceeded processing stale threshold"
        if job.attempt_count >= settings.weather_field_max_attempts:
            job.status = "failed"
            job.finished_at = instant
            job.error = reason
            recovered.append({"job_id": str(job.id), "status": "failed"})
            continue
        if job.kind != "process":
            job.status = "queued"
            job.scheduled_at = instant
            job.started_at = None
            job.finished_at = None
            job.error = reason
            recovered.append({"job_id": str(job.id), "status": "requeued"})
            continue

        run = db.get(WeatherFieldRun, job.run_id) if job.run_id else None
        if run is None:
            job.status = "failed"
            job.finished_at = instant
            job.error = f"{reason}; process run is missing"
            recovered.append({"job_id": str(job.id), "status": "failed"})
            continue
        if run.status == "discovered":
            job.status = "queued"
            job.scheduled_at = instant
            job.started_at = None
            job.finished_at = None
            job.error = reason
            recovered.append({"job_id": str(job.id), "status": "requeued"})
            continue
        model = db.get(WeatherFieldModel, run.model_id)
        if model is None or model.status != "active" or run.status not in {
            "downloading",
            "processing",
            "quality_pending",
        }:
            job.status = "failed"
            job.finished_at = instant
            job.error = f"{reason}; run cannot be retried from status {run.status}"
            recovered.append({"job_id": str(job.id), "status": "failed"})
            continue

        run.status = "failed"
        run.completed_at = instant
        run.error = reason
        recovery_number = int((run.source_metadata or {}).get("retry_count", 0)) + 1
        retry = get_or_create_run(
            db,
            model=model,
            model_run_at=run.model_run_at,
            processing_version=f"{run.processing_version}-recovery-{recovery_number}",
            contract_version=run.contract_version,
            coverage=run.coverage,
            native_grid={"status": "pending_source_inspection"},
            valid_times=run.valid_times,
            source_metadata={
                **(run.source_metadata or {}),
                "retry_of": str(run.id),
                "retry_reason": reason,
                "retry_count": recovery_number,
            },
        )
        retry_job, _ = enqueue_process_run(db, retry)
        retry_job.scheduled_at = instant
        job.status = "superseded"
        job.finished_at = instant
        job.error = reason
        job.diagnostics = {"recovery_job_id": str(retry_job.id)}
        recovered.append(
            {
                "job_id": str(job.id),
                "status": "superseded",
                "recovery_job_id": str(retry_job.id),
            }
        )
    db.commit()
    return recovered


def run_job(db, job_id: uuid.UUID, *, settings, storage=None, now=None) -> WeatherFieldJob:
    job = db.get(WeatherFieldJob, job_id)
    if job is None:
        raise LookupError("weather-field job not found")
    if job.status != "processing":
        return job
    instant = now or datetime.now(timezone.utc)
    try:
        if job.kind == "discover":
            result = _run_discovery(
                db, settings=settings, now=instant, options=job.options
            )
        elif job.kind == "process":
            if job.run_id is None:
                raise ValueError("process job has no run")
            run = db.get(WeatherFieldRun, job.run_id)
            if run is None:
                raise LookupError("process run not found")
            provider = provider_for_model(run.model_key, settings=settings)
            result = process_run(
                db,
                run.id,
                provider=provider,
                storage=storage or configured_field_storage(),
                settings=settings,
            )
        elif job.kind == "retention":
            result = prune_weather_field_runs(
                db,
                storage=storage or configured_field_storage(),
                retain_runs=settings.weather_field_retention_runs,
            )
        elif job.kind == "shadow_validate":
            from app.spatial_fields.shadow_validation import run_shadow_validation

            result = run_shadow_validation(
                db,
                job_id=job.id,
                publication_id=uuid.UUID(job.options["publication_id"]),
                settings=settings,
                storage=storage or configured_field_storage(),
                explicit_spot_ids=job.options.get("spot_ids"),
                now=instant,
            )
        else:  # protected by DB constraint
            raise ValueError(f"unsupported weather-field job kind: {job.kind}")
        job = db.get(WeatherFieldJob, job_id)
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        job.diagnostics = result
        db.commit()
        return job
    except Exception as exc:
        db.rollback()
        failed = db.get(WeatherFieldJob, job_id)
        if failed is None:
            raise
        failed.finished_at = datetime.now(timezone.utc)
        failed.error = f"{type(exc).__name__}: {exc}"[:4000]
        retry_count = int((failed.options or {}).get("retry_count", 0))
        can_retry = (
            retry_count + 1 < settings.weather_field_max_attempts
            if failed.kind == "process"
            else failed.attempt_count < settings.weather_field_max_attempts
        )
        if can_retry:
            if failed.kind == "process" and failed.run_id is not None:
                original = db.get(WeatherFieldRun, failed.run_id)
                model = (
                    db.get(WeatherFieldModel, original.model_id)
                    if original is not None
                    else None
                )
                if original is not None and model is not None and model.status == "active":
                    retry = get_or_create_run(
                        db,
                        model=model,
                        model_run_at=original.model_run_at,
                        processing_version=(
                            f"{original.processing_version}-retry-{retry_count + 1}"
                        ),
                        contract_version=original.contract_version,
                        coverage=original.coverage,
                        native_grid={"status": "pending_source_inspection"},
                        valid_times=original.valid_times,
                        source_metadata={
                            **(original.source_metadata or {}),
                            "retry_of": str(original.id),
                            "retry_reason": failed.error,
                            "retry_count": retry_count + 1,
                        },
                    )
                    retry_job, _ = enqueue_process_run(db, retry)
                    retry_job.scheduled_at = datetime.now(timezone.utc) + timedelta(
                        minutes=(
                            30
                            if isinstance(exc, ProviderUnavailable)
                            else min(30, 2 ** (retry_count + 1))
                        )
                    )
                    failed.status = "superseded"
                    failed.diagnostics = {"retry_job_id": str(retry_job.id)}
                else:
                    failed.status = "failed"
            else:
                failed.status = "queued"
                failed.scheduled_at = datetime.now(timezone.utc) + timedelta(
                    minutes=min(30, 2**failed.attempt_count)
                )
                failed.finished_at = None
        else:
            failed.status = "failed"
        db.commit()
        return failed


def run_worker_batch(
    db,
    *,
    settings,
    storage=None,
    allowed_kinds: tuple[str, ...] | None = None,
    recover_stalled: bool = True,
) -> list[dict]:
    if recover_stalled:
        recover_stalled_jobs(db, settings=settings)
    output = []
    for _ in range(settings.weather_field_worker_batch_size):
        job = claim_next_job(db, allowed_kinds=allowed_kinds)
        if job is None:
            break
        completed = run_job(
            db, job.id, settings=settings, storage=storage
        )
        output.append(
            {
                "job_id": str(completed.id),
                "kind": completed.kind,
                "status": completed.status,
                "error": completed.error,
            }
        )
    return output
