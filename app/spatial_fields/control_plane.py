"""Idempotent control-plane operations for weather-field processing runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldQualityEvent,
    WeatherFieldRun,
)
from app.spatial_fields.publication import REQUIRED_HARD_GATES
from app.spatial_fields.storage import validate_object_key


RUN_TRANSITIONS = {
    "discovered": frozenset({"downloading", "failed"}),
    "downloading": frozenset({"processing", "failed"}),
    "processing": frozenset({"quality_pending", "failed"}),
    "quality_pending": frozenset({"ready", "rejected", "failed"}),
    "ready": frozenset({"expired"}),
    "rejected": frozenset(),
    "failed": frozenset(),
    "expired": frozenset(),
}


def _validate_utc(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC")


def _validate_valid_times(values: list[str]) -> None:
    if not values or values != sorted(set(values)):
        raise ValueError("valid_times must be non-empty, sorted and unique")
    for raw in values:
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("valid_times must contain ISO 8601 timestamps") from exc
        _validate_utc(value, field="valid_time")


def get_or_create_run(
    db,
    *,
    model,
    model_run_at: datetime,
    processing_version: str,
    contract_version: str,
    coverage: dict,
    native_grid: dict,
    valid_times: list[str],
    source_metadata: dict | None = None,
) -> WeatherFieldRun:
    _validate_utc(model_run_at, field="model_run_at")
    _validate_valid_times(valid_times)
    if contract_version != "weather-field-v2":
        raise ValueError("weather-field runs require weather-field-v2")
    if model.status != "active":
        raise ValueError("weather-field model is not active")
    current = db.scalar(
        select(WeatherFieldRun).where(
            WeatherFieldRun.model_id == model.id,
            WeatherFieldRun.model_run_at == model_run_at,
            WeatherFieldRun.processing_version == processing_version,
        )
    )
    if current is not None:
        immutable_contract = {
            "contract_version": contract_version,
            "coverage": coverage,
            "valid_times": valid_times,
        }
        current_contract = {
            "contract_version": current.contract_version,
            "coverage": current.coverage,
            "valid_times": current.valid_times,
        }
        if current_contract != immutable_contract:
            raise ValueError(
                "weather-field processing version already exists with a different immutable run contract"
            )
        return current
    run = WeatherFieldRun(
        model_id=model.id,
        provider_key=model.provider_key,
        model_key=model.model_key,
        model_run_at=model_run_at,
        contract_version=contract_version,
        processing_version=processing_version,
        status="discovered",
        coverage=coverage,
        native_grid=native_grid,
        valid_times=valid_times,
        source_metadata=source_metadata or {},
    )
    db.add(run)
    db.flush()
    return run


def transition_run(db, run_id: uuid.UUID, status: str) -> WeatherFieldRun:
    run = db.scalar(
        select(WeatherFieldRun).where(WeatherFieldRun.id == run_id).with_for_update()
    )
    if run is None:
        raise LookupError("weather-field run not found")
    allowed = RUN_TRANSITIONS.get(run.status, frozenset())
    if status not in allowed:
        raise ValueError(f"invalid weather-field run transition: {run.status} -> {status}")
    run.status = status
    now = datetime.now(timezone.utc)
    if status == "downloading" and run.started_at is None:
        run.started_at = now
    if status in {"failed", "expired"}:
        run.completed_at = now
    db.flush()
    return run


def register_asset(
    db,
    *,
    run_id: uuid.UUID,
    asset_type: str,
    object_key: str,
    size_bytes: int,
    sha256: str,
    content_type: str,
    compression: str,
    status: str = "staged",
    valid_time: datetime | None = None,
    source_zoom: int | None = None,
    tile_x: int | None = None,
    tile_y: int | None = None,
    metadata: dict | None = None,
) -> WeatherFieldAsset:
    validate_object_key(object_key)
    if size_bytes < 0:
        raise ValueError("asset size must not be negative")
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("asset sha256 must be 64 lowercase hexadecimal characters")
    if asset_type == "tile" and None in (valid_time, source_zoom, tile_x, tile_y):
        raise ValueError("tile assets require valid_time, source_zoom, tile_x and tile_y")
    if asset_type == "series_tile" and (
        valid_time is not None or None in (source_zoom, tile_x, tile_y)
    ):
        raise ValueError("series tile assets require source_zoom, tile_x and tile_y only")
    current = db.scalar(
        select(WeatherFieldAsset).where(WeatherFieldAsset.object_key == object_key)
    )
    if current is not None:
        if current.run_id != run_id or current.sha256 != sha256 or current.size_bytes != size_bytes:
            raise ValueError("immutable asset registration conflicts with existing object key")
        return current
    asset = WeatherFieldAsset(
        run_id=run_id,
        asset_type=asset_type,
        object_key=object_key,
        valid_time=valid_time,
        source_zoom=source_zoom,
        tile_x=tile_x,
        tile_y=tile_y,
        size_bytes=size_bytes,
        sha256=sha256,
        content_type=content_type,
        compression=compression,
        status=status,
        asset_metadata=metadata or {},
    )
    db.add(asset)
    db.flush()
    return asset


def record_quality_gate(
    db,
    *,
    run_id: uuid.UUID,
    gate_key: str,
    passed: bool,
    hard_gate: bool = True,
    metrics: dict | None = None,
    message: str | None = None,
    measured_at: datetime | None = None,
) -> WeatherFieldQualityEvent:
    if hard_gate and gate_key not in REQUIRED_HARD_GATES:
        raise ValueError("unknown weather-field hard gate")
    event = db.scalar(
        select(WeatherFieldQualityEvent).where(
            WeatherFieldQualityEvent.run_id == run_id,
            WeatherFieldQualityEvent.gate_key == gate_key,
        )
    )
    if event is None:
        event = WeatherFieldQualityEvent(run_id=run_id, gate_key=gate_key)
        db.add(event)
    event.hard_gate = hard_gate
    event.passed = passed
    event.metrics = metrics or {}
    event.message = message
    event.measured_at = measured_at or datetime.now(timezone.utc)
    db.flush()
    return event


def finalize_run_quality(
    db, run_id: uuid.UUID, *, completed_at: datetime | None = None
) -> WeatherFieldRun:
    run = db.scalar(
        select(WeatherFieldRun).where(WeatherFieldRun.id == run_id).with_for_update()
    )
    if run is None:
        raise LookupError("weather-field run not found")
    if run.status != "quality_pending":
        raise ValueError("only a quality_pending weather-field run can be finalized")
    assets = db.scalars(
        select(WeatherFieldAsset).where(WeatherFieldAsset.run_id == run.id)
    ).all()
    events = db.scalars(
        select(WeatherFieldQualityEvent).where(
            WeatherFieldQualityEvent.run_id == run.id,
            WeatherFieldQualityEvent.hard_gate.is_(True),
        )
    ).all()
    gates = {event.gate_key: bool(event.passed) for event in events}
    reasons: list[str] = []
    if not assets:
        reasons.append("run has no registered assets")
    elif any(asset.status != "verified" for asset in assets):
        reasons.append("all assets must be verified")
    if not any(asset.asset_type == "manifest" and asset.status == "verified" for asset in assets):
        reasons.append("verified manifest is missing")
    missing = sorted(REQUIRED_HARD_GATES - gates.keys())
    failed = sorted(key for key in REQUIRED_HARD_GATES if gates.get(key) is False)
    if missing:
        reasons.append("missing hard gates: " + ", ".join(missing))
    if failed:
        reasons.append("failed hard gates: " + ", ".join(failed))
    run.status = "rejected" if reasons else "ready"
    run.completed_at = completed_at or datetime.now(timezone.utc)
    run.diagnostics = {**(run.diagnostics or {}), "quality_reasons": reasons}
    db.flush()
    return run
