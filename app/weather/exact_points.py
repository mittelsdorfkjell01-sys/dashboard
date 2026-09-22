"""Persistent compact u/v samples from immutable exact-run GRIB bundles.

The raw GRIB cache may be ephemeral.  These rows retain only reproducible point
evidence and can therefore feed later station residuals without fetching a
historical model after the observation became known.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import WeatherExactModelBundle, WeatherExactModelPoint
from app.weather.exact_run import (
    EXACT_BUNDLE_VERSION,
    EXACT_LOADER_VERSION,
    EXPECTED_MODELS,
    compatible_dataset_manifests,
)
from app.weather.model_error import (
    DEFAULT_MODEL_ERROR_POLICY,
    EXACT_SAMPLE_VERSION,
    ModelWindPoint,
    StationModelBaseline,
    _interpolate_member,
)


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _bundle_identity(manifest: dict) -> dict:
    return {
        "version": manifest.get("version"),
        "loader": manifest.get("loader_version"),
        "members": manifest.get("members"),
        "statuses": manifest.get("statuses"),
    }


def _valid_point_hash(
    point: ModelWindPoint,
    *,
    latitude: float,
    longitude: float,
    dataset_bundle_hash: str,
) -> bool:
    # Keep the exact-run producer's manifest byte-for-byte compatible while the
    # helper above makes the fields visible to reviewers.
    payload = {
        "sampling_version": EXACT_SAMPLE_VERSION,
        "dataset_bundle_hash": dataset_bundle_hash,
        "asset_content_hashes": list(point.asset_content_hashes),
        "coordinate": {"latitude": float(latitude), "longitude": float(longitude)},
        "valid_at": point.valid_at.isoformat(),
        "model": point.model_id,
        "sampling_method": point.sampling_method,
        "source_cells": point.source_cells,
        "u_ms": round(float(point.u_ms), 9),
        "v_ms": round(float(point.v_ms), 9),
    }
    return point.sample_hash == _hash(payload)


def persist_exact_point_bundle(
    db,
    *,
    target_kind: str,
    target_id,
    latitude: float,
    longitude: float,
    sampled_for_at: datetime,
    captured_at: datetime,
    baseline: StationModelBaseline,
) -> dict:
    """Idempotently retain one activation-eligible exact point bundle."""
    if target_kind not in {"station", "spot"}:
        raise ValueError("unsupported exact-point target kind")
    identifier = uuid.UUID(str(target_id))
    sampled_for = _utc(sampled_for_at, "sampled_for_at")
    captured = _utc(captured_at, "captured_at")
    if captured < sampled_for:
        raise ValueError("captured_at must not precede sampled_for_at")
    manifest = baseline.bundle_manifest
    dataset = baseline.dataset_manifest
    if (
        baseline.baseline_version != EXACT_BUNDLE_VERSION
        or not baseline.activation_eligible
        or tuple(baseline.expected_model_ids) != EXPECTED_MODELS
        or not isinstance(manifest, dict)
        or not isinstance(dataset, dict)
        or baseline.bundle_hash != _hash(_bundle_identity(manifest))
        or baseline.dataset_bundle_hash != _hash(dataset)
        or not compatible_dataset_manifests(dataset, dataset)
    ):
        return {"status": "ineligible", "bundle_inserted": 0, "points_inserted": 0}
    points = tuple(baseline.points)
    if not points or any(
        point.available_at is None
        or point.available_at > captured
        or point.baseline_version != EXACT_BUNDLE_VERSION
        or point.model_run_quality != "exact"
        or point.sampling_version != EXACT_SAMPLE_VERSION
        or not point.sample_hash
        or not _valid_point_hash(
            point,
            latitude=latitude,
            longitude=longitude,
            dataset_bundle_hash=baseline.dataset_bundle_hash,
        )
        for point in points
    ):
        return {"status": "ineligible", "bundle_inserted": 0, "points_inserted": 0}

    values = {
        "target_kind": target_kind,
        "target_id": identifier,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "sampled_for_at": sampled_for,
        "captured_at": captured,
        "baseline_version": baseline.baseline_version,
        "loader_version": str(manifest["loader_version"]),
        "bundle_hash": baseline.bundle_hash,
        "bundle_manifest": manifest,
        "dataset_bundle_hash": baseline.dataset_bundle_hash,
        "dataset_manifest": dataset,
        "activation_eligible": True,
        "member_statuses": baseline.member_statuses or {},
    }
    inserted_id = db.scalar(
        insert(WeatherExactModelBundle)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_weather_exact_bundle_target")
        .returning(WeatherExactModelBundle.id)
    )
    bundle_inserted = int(inserted_id is not None)
    bundle_id = inserted_id or db.scalar(select(WeatherExactModelBundle.id).where(
        WeatherExactModelBundle.target_kind == target_kind,
        WeatherExactModelBundle.target_id == identifier,
        WeatherExactModelBundle.bundle_hash == baseline.bundle_hash,
    ))
    if bundle_id is None:
        raise RuntimeError("exact point bundle identity was not persisted")
    point_values = [{
        "bundle_id": bundle_id,
        "provider": point.provider,
        "model_id": point.model_id,
        "dataset_version": point.dataset_version,
        "model_run_id": point.model_run_id,
        "model_run_at": point.model_run_at,
        "model_run_quality": point.model_run_quality,
        "valid_at": point.valid_at,
        "fetched_at": point.fetched_at,
        "available_at": point.available_at,
        "latitude": point.latitude,
        "longitude": point.longitude,
        "grid_distance_km": point.grid_distance_km,
        "u_ms": point.u_ms,
        "v_ms": point.v_ms,
        "source_key": point.source_key,
        "asset_hashes": list(point.asset_hashes),
        "asset_content_hashes": list(point.asset_content_hashes),
        "sample_hash": point.sample_hash,
        "sampling_version": point.sampling_version,
        "sampling_method": point.sampling_method,
        "source_cells": point.source_cells,
        "grid_definition": point.grid_definition,
        "model_height_m": point.model_height_m,
    } for point in points]
    points_inserted = len(db.scalars(
        insert(WeatherExactModelPoint)
        .values(point_values)
        .on_conflict_do_nothing(
            constraint="uq_weather_exact_point_bundle_model_time"
        )
        .returning(WeatherExactModelPoint.id)
    ).all())
    return {
        "status": "persisted",
        "bundle_id": str(bundle_id),
        "bundle_inserted": bundle_inserted,
        "points_inserted": points_inserted,
    }


def _point(row, baseline_version: str) -> ModelWindPoint:
    return ModelWindPoint(
        baseline_version=baseline_version,
        provider=row.provider,
        model_id=row.model_id,
        dataset_version=row.dataset_version,
        model_run_id=row.model_run_id,
        model_run_at=row.model_run_at,
        model_run_quality=row.model_run_quality,
        valid_at=row.valid_at,
        fetched_at=row.fetched_at,
        available_at=row.available_at,
        latitude=row.latitude,
        longitude=row.longitude,
        grid_distance_km=row.grid_distance_km,
        u_ms=row.u_ms,
        v_ms=row.v_ms,
        source_key=row.source_key,
        asset_hashes=tuple(row.asset_hashes or ()),
        asset_content_hashes=tuple(row.asset_content_hashes or ()),
        sample_hash=row.sample_hash,
        sampling_version=row.sampling_version,
        sampling_method=row.sampling_method,
        source_cells=row.source_cells or {},
        grid_definition=row.grid_definition,
        model_height_m=row.model_height_m,
    )


def load_persisted_exact_baseline(
    db,
    *,
    target_kind: str,
    target_id,
    at: datetime,
    as_of: datetime | None = None,
) -> StationModelBaseline:
    """Load the newest complete point bundle that was known at ``as_of``."""
    instant = _utc(at, "at")
    cutoff = _utc(as_of or instant, "as_of")
    identifier = uuid.UUID(str(target_id))
    bundles = db.scalars(select(WeatherExactModelBundle).where(
        WeatherExactModelBundle.target_kind == target_kind,
        WeatherExactModelBundle.target_id == identifier,
        WeatherExactModelBundle.activation_eligible.is_(True),
        WeatherExactModelBundle.captured_at <= cutoff,
    ).order_by(
        WeatherExactModelBundle.sampled_for_at.desc(),
        WeatherExactModelBundle.id,
    ).limit(24)).all()
    for bundle in bundles:
        if (
            bundle.baseline_version != EXACT_BUNDLE_VERSION
            or bundle.loader_version != EXACT_LOADER_VERSION
            or bundle.bundle_hash != _hash(_bundle_identity(bundle.bundle_manifest))
            or bundle.dataset_bundle_hash != _hash(bundle.dataset_manifest)
            or not compatible_dataset_manifests(
                bundle.dataset_manifest, bundle.dataset_manifest
            )
        ):
            continue
        rows = db.scalars(select(WeatherExactModelPoint).where(
            WeatherExactModelPoint.bundle_id == bundle.id,
            WeatherExactModelPoint.available_at <= cutoff,
        ).order_by(
            WeatherExactModelPoint.model_id,
            WeatherExactModelPoint.valid_at,
            WeatherExactModelPoint.id,
        )).all()
        try:
            points = tuple(_point(row, bundle.baseline_version) for row in rows)
        except (TypeError, ValueError):
            continue
        if any(not _valid_point_hash(
            point,
            latitude=bundle.latitude,
            longitude=bundle.longitude,
            dataset_bundle_hash=bundle.dataset_bundle_hash,
        ) for point in points):
            continue
        complete = True
        for model_id in EXPECTED_MODELS:
            member, _reason = _interpolate_member(
                [point for point in points if point.model_id == model_id],
                instant,
                policy=DEFAULT_MODEL_ERROR_POLICY,
            )
            if member is None:
                complete = False
                break
        if not complete:
            continue
        return StationModelBaseline(
            points=points,
            expected_model_ids=EXPECTED_MODELS,
            baseline_version=bundle.baseline_version,
            bundle_hash=bundle.bundle_hash,
            bundle_manifest=bundle.bundle_manifest,
            dataset_bundle_hash=bundle.dataset_bundle_hash,
            dataset_manifest=bundle.dataset_manifest,
            activation_eligible=True,
            member_statuses=bundle.member_statuses,
        )
    return StationModelBaseline(
        points=(),
        expected_model_ids=EXPECTED_MODELS,
        baseline_version=EXACT_BUNDLE_VERSION,
        activation_eligible=False,
        member_statuses={model: "availability_unproven" for model in EXPECTED_MODELS},
    )


class PersistedStationBaselineLoader:
    """Station residual loader backed only by pre-observation point evidence."""

    def __init__(self, db):
        self.db = db

    def __call__(self, station, observation) -> StationModelBaseline:
        return load_persisted_exact_baseline(
            self.db,
            target_kind="station",
            target_id=station.id,
            at=observation.observed_at,
            as_of=observation.observed_at,
        )
