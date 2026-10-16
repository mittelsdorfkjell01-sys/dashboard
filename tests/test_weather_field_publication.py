from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldModel,
    WeatherFieldQualityEvent,
    WeatherFieldRun,
)
from app.spatial_fields.publication import (
    REQUIRED_HARD_GATES,
    PublicationNotReady,
    active_publication_state,
    activate_publication,
    assess_publication_readiness,
    rollback_publication,
    stage_publication,
)


def test_readiness_reports_every_hard_blocker() -> None:
    readiness = assess_publication_readiness(
        run_status="processing",
        asset_statuses=["verified", "invalid"],
        manifest_verified=False,
        hard_gates={"uv_pair": False},
    )
    assert not readiness.ready
    assert any("run status" in reason for reason in readiness.reasons)
    assert any("all registered assets" in reason for reason in readiness.reasons)
    assert any("missing hard gates" in reason for reason in readiness.reasons)
    assert any("failed hard gates" in reason for reason in readiness.reasons)


def _ready_run(db, suffix: str):
    now = datetime.now(timezone.utc)
    model = WeatherFieldModel(
        provider_key="dwd",
        model_key=f"icon-eu-{suffix}",
        display_name="ICON-EU",
        status="active",
        coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
        native_grid={"gridType": "regular_ll"},
        cadence_hours=6,
        forecast_step_hours=1,
        max_horizon_hours=120,
        priority=10,
        licence={"name": "GeoNutzV"},
        attribution=[{"provider": "DWD"}],
    )
    db.add(model)
    db.flush()
    run = WeatherFieldRun(
        model_id=model.id,
        provider_key="dwd",
        model_key="icon-eu",
        model_run_at=now,
        contract_version="weather-field-v2",
        processing_version=f"test-{suffix}",
        status="ready",
        coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
        native_grid={"gridType": "regular_ll"},
        valid_times=[now.isoformat()],
    )
    db.add(run)
    db.flush()
    manifest = WeatherFieldAsset(
        run_id=run.id,
        asset_type="manifest",
        object_key=f"europe/{suffix}/manifest.json",
        size_bytes=100,
        sha256="a" * 64,
        content_type="application/json",
        compression="none",
        status="verified",
    )
    tile = WeatherFieldAsset(
        run_id=run.id,
        asset_type="tile",
        object_key=f"europe/{suffix}/assets/tile.swf2.gz",
        valid_time=now,
        source_zoom=4,
        tile_x=8,
        tile_y=5,
        size_bytes=200,
        sha256="b" * 64,
        content_type="application/vnd.surfwinddata.field-tile",
        compression="gzip",
        status="verified",
    )
    db.add_all([manifest, tile])
    db.flush()
    db.add_all(
        [
            WeatherFieldQualityEvent(
                run_id=run.id,
                gate_key=gate,
                hard_gate=True,
                passed=True,
                measured_at=now,
            )
            for gate in REQUIRED_HARD_GATES
        ]
    )
    db.flush()
    return run, manifest


def test_activation_and_rollback_are_atomic_control_plane_changes(db) -> None:
    first_run, first_manifest = _ready_run(db, "first")
    first = stage_publication(
        db,
        scope_key="europe-wind",
        run_id=first_run.id,
        manifest_asset_id=first_manifest.id,
    )
    activate_publication(db, first.id, actor="test", reason="initial")
    assert first.active and first.status == "active" and first.generation == 1

    second_run, second_manifest = _ready_run(db, "second")
    second = stage_publication(
        db,
        scope_key="europe-wind",
        run_id=second_run.id,
        manifest_asset_id=second_manifest.id,
    )
    activate_publication(db, second.id, actor="test", reason="new run")
    assert second.active and second.generation == 2
    assert not first.active and first.status == "superseded"

    restored = rollback_publication(
        db,
        scope_key="europe-wind",
        restore_publication_id=first.id,
        actor="operator@test",
        reason="bad downstream rendering",
    )
    assert restored.active and restored.run_id == first_run.id
    assert restored.generation == 3
    assert not second.active and second.status == "rolled_back"
    state = active_publication_state(
        db, "europe-wind", now=first_run.model_run_at + timedelta(hours=10)
    )
    assert state is not None
    assert state.publication_id == restored.id
    assert state.freshness == "delayed"


def test_activation_rejects_failed_hard_gate(db) -> None:
    run, manifest = _ready_run(db, "blocked")
    event = db.scalar(
        select(WeatherFieldQualityEvent).where(
            WeatherFieldQualityEvent.run_id == run.id,
            WeatherFieldQualityEvent.gate_key == "asset_integrity",
        )
    )
    assert event is not None
    event.passed = False
    publication = stage_publication(
        db,
        scope_key="blocked-wind",
        run_id=run.id,
        manifest_asset_id=manifest.id,
    )
    with pytest.raises(PublicationNotReady, match="asset_integrity"):
        activate_publication(db, publication.id)


def test_activation_rejects_insufficient_shadow_cycles(db) -> None:
    run, manifest = _ready_run(db, "shadow-blocked")
    run.diagnostics = {"asset_bytes": 1_000}
    run.bytes_downloaded = 1_000
    run.started_at = run.model_run_at
    run.completed_at = run.model_run_at + timedelta(seconds=10)
    publication = stage_publication(
        db,
        scope_key="shadow-blocked-wind",
        run_id=run.id,
        manifest_asset_id=manifest.id,
    )
    policy = SimpleNamespace(
        weather_field_forecast_hours=[0],
        weather_field_activation_min_shadow_runs=2,
        weather_field_activation_lookback_hours=30,
        weather_field_activation_max_download_bytes=10_000,
        weather_field_activation_max_asset_bytes=10_000,
        weather_field_activation_max_processing_seconds=60,
    )

    with pytest.raises(PublicationNotReady, match="need 2 consecutive"):
        activate_publication(db, publication.id, rollout_policy=policy)
