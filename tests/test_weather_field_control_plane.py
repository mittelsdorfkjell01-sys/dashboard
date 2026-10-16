from datetime import datetime, timedelta, timezone

import pytest

from app.spatial_fields.catalog import sync_free_model_catalog
from app.spatial_fields.control_plane import (
    finalize_run_quality,
    get_or_create_run,
    record_quality_gate,
    register_asset,
    transition_run,
)
from app.spatial_fields.publication import REQUIRED_HARD_GATES


def _run(db, *, version: str):
    models = sync_free_model_catalog(db)
    icon_eu = next(model for model in models if model.model_key == "icon-eu")
    now = datetime.now(timezone.utc)
    run = get_or_create_run(
        db,
        model=icon_eu,
        model_run_at=now,
        processing_version=version,
        contract_version="weather-field-v2",
        coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
        native_grid={"gridType": "regular_ll"},
        valid_times=[now.isoformat()],
    )
    return run, now


def test_free_catalog_is_idempotent_and_activates_regional_and_global_models(db) -> None:
    first = sync_free_model_catalog(db)
    second = sync_free_model_catalog(db)

    assert [row.id for row in first] == [row.id for row in second]
    assert next(row for row in first if row.model_key == "icon-eu").status == "active"
    assert next(row for row in first if row.model_key == "icon-d2").status == "active"
    gfs = next(row for row in first if row.model_key == "gfs-0p25")
    assert gfs.status == "active"
    assert gfs.model_metadata["blend"] is False


def test_run_assets_gates_and_finalization_are_idempotent(db) -> None:
    run, valid_time = _run(db, version="control-ready")
    icon_eu = next(
        model for model in sync_free_model_catalog(db) if model.model_key == "icon-eu"
    )
    same = get_or_create_run(
        db,
        model=icon_eu,
        model_run_at=run.model_run_at,
        processing_version=run.processing_version,
        contract_version=run.contract_version,
        coverage=run.coverage,
        native_grid=run.native_grid,
        valid_times=run.valid_times,
    )
    assert same.id == run.id

    with pytest.raises(ValueError, match="different immutable run contract"):
        get_or_create_run(
            db,
            model=icon_eu,
            model_run_at=run.model_run_at,
            processing_version=run.processing_version,
            contract_version=run.contract_version,
            coverage=run.coverage,
            native_grid=run.native_grid,
            valid_times=[
                run.valid_times[0],
                (valid_time + timedelta(hours=3)).isoformat(),
            ],
        )

    manifest = register_asset(
        db,
        run_id=run.id,
        asset_type="manifest",
        object_key="europe/control-ready/manifest.json",
        size_bytes=100,
        sha256="a" * 64,
        content_type="application/json",
        compression="none",
        status="verified",
    )
    repeated = register_asset(
        db,
        run_id=run.id,
        asset_type="manifest",
        object_key=manifest.object_key,
        size_bytes=100,
        sha256="a" * 64,
        content_type="application/json",
        compression="none",
        status="verified",
    )
    assert repeated.id == manifest.id
    register_asset(
        db,
        run_id=run.id,
        asset_type="tile",
        object_key="europe/control-ready/assets/4/8/5.swf2.gz",
        valid_time=valid_time,
        source_zoom=4,
        tile_x=8,
        tile_y=5,
        size_bytes=200,
        sha256="b" * 64,
        content_type="application/vnd.surfwinddata.field-tile",
        compression="gzip",
        status="verified",
    )
    for gate in REQUIRED_HARD_GATES:
        record_quality_gate(db, run_id=run.id, gate_key=gate, passed=True)

    transition_run(db, run.id, "downloading")
    transition_run(db, run.id, "processing")
    transition_run(db, run.id, "quality_pending")

    finalized = finalize_run_quality(db, run.id)
    assert finalized.status == "ready"
    assert finalized.diagnostics["quality_reasons"] == []


def test_finalization_rejects_incomplete_run_and_asset_key_conflicts(db) -> None:
    run, _ = _run(db, version="control-rejected")
    register_asset(
        db,
        run_id=run.id,
        asset_type="manifest",
        object_key="europe/control-rejected/manifest.json",
        size_bytes=100,
        sha256="a" * 64,
        content_type="application/json",
        compression="none",
        status="staged",
    )
    with pytest.raises(ValueError, match="conflicts"):
        register_asset(
            db,
            run_id=run.id,
            asset_type="manifest",
            object_key="europe/control-rejected/manifest.json",
            size_bytes=101,
            sha256="c" * 64,
            content_type="application/json",
            compression="none",
        )

    transition_run(db, run.id, "downloading")
    transition_run(db, run.id, "processing")
    transition_run(db, run.id, "quality_pending")
    finalized = finalize_run_quality(db, run.id)
    assert finalized.status == "rejected"
    assert any("verified" in reason for reason in finalized.diagnostics["quality_reasons"])


def test_run_state_machine_rejects_skipped_stages(db) -> None:
    run, _ = _run(db, version="bad-transition")
    with pytest.raises(ValueError, match="discovered -> ready"):
        transition_run(db, run.id, "ready")
