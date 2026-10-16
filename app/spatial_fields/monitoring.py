"""Machine-readable health for the weather-field control and data planes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

from sqlalchemy import func, select

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldJob,
    WeatherFieldModel,
    WeatherFieldPublication,
    WeatherFieldQualityEvent,
    WeatherFieldRun,
)
from app.spatial_fields.contracts_v2 import FieldManifestV2
from app.spatial_fields.publication import active_publication_state
from app.spatial_fields.rollout import assess_shadow_readiness
from app.spatial_fields.scopes import model_scope
from app.spatial_fields.forecast_profile import wave_model_keys


WIND_FIELD_MODELS = ("icon-d2", "icon-eu", "gfs-0p25")
WAVE_FIELD_MODELS = ("dwd-ewam", "dwd-gwam", "noaa-gfs-wave")


def _health_tile_sample(assets: list, *, deep: bool) -> list:
    """Return a deterministic, bounded readiness sample or the full audit set."""
    if deep or len(assets) <= 3:
        return assets
    return [assets[0], assets[len(assets) // 2], assets[-1]]


def weather_field_health(
    db,
    *,
    storage,
    settings,
    now: datetime | None = None,
    scope_key: str | None = None,
    public_enabled: bool | None = None,
    model_keys: tuple[str, ...] | None = None,
    deep: bool = False,
) -> dict:
    instant = now or datetime.now(timezone.utc)
    selected_scope = scope_key or settings.weather_field_scope_key
    selected_public_enabled = (
        settings.weather_field_public_enabled
        if public_enabled is None
        else public_enabled
    )
    state = active_publication_state(db, selected_scope, now=instant)
    latest_query = select(WeatherFieldRun)
    if model_keys:
        latest_query = latest_query.where(WeatherFieldRun.model_key.in_(model_keys))
    latest_run = db.scalar(
        latest_query.order_by(
            WeatherFieldRun.model_run_at.desc(), WeatherFieldRun.created_at.desc()
        ).limit(1)
    )
    stalled_before = instant - timedelta(
        minutes=settings.weather_field_processing_stale_minutes
    )
    stalled_query = select(WeatherFieldRun).where(
            WeatherFieldRun.status.in_(("downloading", "processing", "quality_pending")),
            WeatherFieldRun.started_at < stalled_before,
        )
    if model_keys:
        stalled_query = stalled_query.where(WeatherFieldRun.model_key.in_(model_keys))
    stalled = db.scalars(stalled_query).all()
    queued_jobs = db.scalar(
        select(func.count()).select_from(WeatherFieldJob).where(
            WeatherFieldJob.status == "queued"
        )
    )
    failed_jobs = db.scalar(
        select(func.count()).select_from(WeatherFieldJob).where(
            WeatherFieldJob.status == "failed"
        )
    )
    issues: list[dict] = []
    asset_health = None
    quality = None
    active_payload = None
    shadow_readiness = None
    if state is None:
        issues.append({"code": "no_active_publication", "severity": "warning"})
    else:
        publication = db.get(WeatherFieldPublication, state.publication_id)
        manifest = db.get(WeatherFieldAsset, publication.manifest_asset_id)
        counts = dict(
            db.execute(
                select(WeatherFieldAsset.status, func.count())
                .where(WeatherFieldAsset.run_id == state.run_id)
                .group_by(WeatherFieldAsset.status)
            ).all()
        )
        manifest_exists = bool(manifest and storage.exists(manifest.object_key))
        manifest_checksum_ok = False
        parsed_manifest = None
        if manifest_exists:
            try:
                manifest_payload = storage.get(manifest.object_key)
                manifest_checksum_ok = (
                    hashlib.sha256(manifest_payload).hexdigest() == manifest.sha256
                )
                if manifest_checksum_ok:
                    parsed_manifest = FieldManifestV2.model_validate_json(manifest_payload)
            except (OSError, KeyError, ValueError):
                manifest_checksum_ok = False
        if not manifest_exists:
            issues.append({"code": "active_manifest_missing", "severity": "error"})
        elif not manifest_checksum_ok:
            issues.append({"code": "active_manifest_checksum", "severity": "error"})
        if counts.get("invalid", 0):
            issues.append({"code": "invalid_assets", "severity": "error"})
        tile_assets = db.scalars(
            select(WeatherFieldAsset).where(
                WeatherFieldAsset.run_id == state.run_id,
                WeatherFieldAsset.asset_type == "tile",
                WeatherFieldAsset.status == "verified",
            )
        ).all()
        # Normal readiness must stay bounded for remote object stores. Complete
        # verification is available to scheduled/deployment audits via ``deep``.
        checked_tile_assets = _health_tile_sample(tile_assets, deep=deep)
        missing_tiles = sum(
            1 for asset in checked_tile_assets if not storage.exists(asset.object_key)
        )
        if missing_tiles:
            issues.append(
                {
                    "code": "published_tile_404",
                    "severity": "error",
                    "count": missing_tiles,
                }
            )
        index_asset = db.scalar(
            select(WeatherFieldAsset).where(
                WeatherFieldAsset.run_id == state.run_id,
                WeatherFieldAsset.asset_type == "asset_index",
            )
        )
        index_checksum_ok = False
        if index_asset and storage.exists(index_asset.object_key):
            index_checksum_ok = (
                hashlib.sha256(storage.get(index_asset.object_key)).hexdigest()
                == index_asset.sha256
            )
        if parsed_manifest and (
            index_asset is None
            or parsed_manifest.checksums.asset_index != index_asset.sha256
            or not index_checksum_ok
        ):
            issues.append({"code": "asset_index_checksum", "severity": "error"})
        asset_health = {
            "counts": counts,
            "manifest_exists": manifest_exists,
            "manifest_checksum_ok": manifest_checksum_ok,
            "asset_index_checksum_ok": index_checksum_ok,
            "missing_tiles": missing_tiles,
            "checked_tiles": len(checked_tile_assets),
            "total_tiles": len(tile_assets),
            "deep_check": deep,
        }
        gates = db.scalars(
            select(WeatherFieldQualityEvent).where(
                WeatherFieldQualityEvent.run_id == state.run_id
            )
        ).all()
        quality = {
            "passed": all(event.passed for event in gates if event.hard_gate),
            "gates": {event.gate_key: event.passed for event in gates},
        }
        active_run = db.get(WeatherFieldRun, state.run_id)
        active_model = db.get(WeatherFieldModel, active_run.model_id)
        active_payload = {
            "publication_id": str(state.publication_id),
            "run_id": str(state.run_id),
            "generation": state.generation,
            "model_run": state.model_run_at.isoformat(),
            "freshness": state.freshness,
            "age_seconds": state.age_seconds,
            "coverage": active_run.coverage,
            "expected_next_update": (
                state.model_run_at + timedelta(hours=active_model.cadence_hours)
            ).isoformat(),
        }
        if state.freshness in {"stale", "expired"}:
            issues.append(
                {"code": f"active_publication_{state.freshness}", "severity": "error"}
            )
    if latest_run is None:
        issues.append({"code": "no_model_run", "severity": "warning"})
    elif latest_run.status == "failed":
        issues.append({"code": "latest_run_failed", "severity": "error"})
    elif latest_run.status == "rejected":
        issues.append({"code": "latest_run_quality_rejected", "severity": "warning"})
    if failed_jobs:
        issues.append(
            {"code": "worker_jobs_failed", "severity": "warning", "count": failed_jobs}
        )
    if stalled:
        issues.append(
            {
                "code": "processing_stalled",
                "severity": "error",
                "run_ids": [str(run.id) for run in stalled],
            }
        )
    staged_query = (
        select(WeatherFieldPublication)
        .join(WeatherFieldRun, WeatherFieldRun.id == WeatherFieldPublication.run_id)
        .where(
            WeatherFieldPublication.scope_key == selected_scope,
            WeatherFieldPublication.status == "staged",
        )
        .order_by(
            WeatherFieldRun.model_run_at.desc(),
            WeatherFieldPublication.created_at.desc(),
        )
        .limit(1)
    )
    # A retained shadow publication older than the active generation is rollback
    # evidence, not a pending rollout. Only warn for a genuinely newer candidate.
    if state is not None:
        staged_query = staged_query.where(
            WeatherFieldRun.model_run_at > state.model_run_at
        )
    staged = db.scalar(staged_query)
    if staged is not None:
        rollout = assess_shadow_readiness(
            db,
            candidate_run_id=staged.run_id,
            settings=settings,
            now=instant,
        )
        shadow_readiness = {
            "publication_id": str(staged.id),
            "run_id": str(staged.run_id),
            **rollout.model_dump(),
        }
        if not rollout.ready:
            issues.append(
                {
                    "code": "shadow_rollout_not_ready",
                    "severity": "warning",
                    "reasons": list(rollout.reasons),
                }
            )
    status = "error" if any(issue["severity"] == "error" for issue in issues) else (
        "degraded" if issues else "ok"
    )
    return {
        "status": status,
        "scope_key": selected_scope,
        "pipeline_enabled": settings.weather_field_pipeline_enabled,
        "public_enabled": selected_public_enabled,
        "active_publication": active_payload,
        "latest_run": (
            {
                "id": str(latest_run.id),
                "model": latest_run.model_key,
                "model_run": latest_run.model_run_at.isoformat(),
                "status": latest_run.status,
            }
            if latest_run
            else None
        ),
        "quality": quality,
        "asset_health": asset_health,
        "shadow_readiness": shadow_readiness,
        "jobs": {"queued": queued_jobs or 0, "failed": failed_jobs or 0},
        "issues": issues,
    }


def wave_field_health(
    db, *, storage, settings, now: datetime | None = None, deep: bool = False
) -> dict:
    """Report every member of the ten-day wave chain independently."""
    primary_scope = settings.wave_field_scope_key
    fallback_scope = model_scope(
        primary_scope,
        settings.wave_field_fallback_model,
        primary_model=settings.wave_field_primary_model,
    )
    primary = weather_field_health(
        db,
        storage=storage,
        settings=settings,
        now=now,
        scope_key=primary_scope,
        public_enabled=settings.wave_field_public_enabled,
        model_keys=(settings.wave_field_primary_model,),
        deep=deep,
    )
    fallback = weather_field_health(
        db,
        storage=storage,
        settings=settings,
        now=now,
        scope_key=fallback_scope,
        public_enabled=settings.wave_field_public_enabled,
        model_keys=(settings.wave_field_fallback_model,),
        deep=deep,
    )
    extended_model = getattr(settings, "wave_field_extended_model", "noaa-gfs-wave")
    extended_scope = model_scope(
        primary_scope,
        extended_model,
        primary_model=settings.wave_field_primary_model,
    )
    extended = weather_field_health(
        db,
        storage=storage,
        settings=settings,
        now=now,
        scope_key=extended_scope,
        public_enabled=settings.wave_field_public_enabled,
        model_keys=(extended_model,),
        deep=deep,
    )
    statuses = {primary["status"], fallback["status"], extended["status"]}
    status = "error" if "error" in statuses else "degraded" if "degraded" in statuses else "ok"
    return {
        "status": status,
        "pipeline_enabled": settings.weather_field_pipeline_enabled,
        "public_enabled": settings.wave_field_public_enabled,
        "primary": primary,
        "fallback": fallback,
        "extended": extended,
        "model_chain": list(wave_model_keys(settings)),
    }
