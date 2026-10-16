from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.weather_field import WeatherFieldModel, WeatherFieldRun
from app.spatial_fields.rollout import assess_shadow_readiness


def _settings(*, required: int = 3):
    return SimpleNamespace(
        weather_field_forecast_hours=[0, 3],
        weather_field_activation_min_shadow_runs=required,
        weather_field_activation_lookback_hours=30,
        weather_field_activation_max_download_bytes=250_000_000,
        weather_field_activation_max_asset_bytes=180_000_000,
        weather_field_activation_max_processing_seconds=300,
    )


def _run(db, model, *, model_run: datetime, suffix: str) -> WeatherFieldRun:
    run = WeatherFieldRun(
        model_id=model.id,
        provider_key="dwd",
        model_key="icon-eu",
        model_run_at=model_run,
        contract_version="weather-field-v2",
        processing_version=f"shadow-{suffix}",
        status="ready",
        coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
        native_grid={"gridType": "regular_ll"},
        valid_times=[
            model_run.isoformat().replace("+00:00", "Z"),
            (model_run + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
        ],
        diagnostics={"asset_bytes": 140_000_000},
        bytes_downloaded=175_000_000,
        started_at=model_run + timedelta(minutes=20),
        completed_at=model_run + timedelta(minutes=22),
    )
    db.add(run)
    db.flush()
    return run


def test_three_consecutive_full_horizon_cycles_are_rollout_ready(db) -> None:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    model = WeatherFieldModel(
        provider_key="dwd",
        model_key="icon-eu-rollout",
        display_name="ICON-EU rollout",
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
    _run(db, model, model_run=now - timedelta(hours=12), suffix="one")
    _run(db, model, model_run=now - timedelta(hours=6), suffix="two")
    candidate = _run(db, model, model_run=now, suffix="three")

    readiness = assess_shadow_readiness(
        db, candidate_run_id=candidate.id, settings=_settings(), now=now
    )

    assert readiness.ready is True
    assert readiness.consecutive_runs == 3
    assert len(readiness.qualified_run_ids) == 3


def test_resource_overrun_breaks_the_consecutive_shadow_sequence(db) -> None:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    model = WeatherFieldModel(
        provider_key="dwd",
        model_key="icon-eu-rollout-budget",
        display_name="ICON-EU rollout budget",
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
    _run(db, model, model_run=now - timedelta(hours=12), suffix="one")
    oversized = _run(db, model, model_run=now - timedelta(hours=6), suffix="two")
    oversized.diagnostics = {"asset_bytes": 190_000_000}
    candidate = _run(db, model, model_run=now, suffix="three")

    readiness = assess_shadow_readiness(
        db, candidate_run_id=candidate.id, settings=_settings(), now=now
    )

    assert readiness.ready is False
    assert readiness.consecutive_runs == 1
    assert any("need 3 consecutive" in reason for reason in readiness.reasons)


def test_missing_model_cycle_breaks_the_shadow_sequence(db) -> None:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    model = WeatherFieldModel(
        provider_key="dwd",
        model_key="icon-eu-rollout-gap",
        display_name="ICON-EU rollout gap",
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
    _run(db, model, model_run=now - timedelta(hours=12), suffix="one")
    candidate = _run(db, model, model_run=now, suffix="three")

    readiness = assess_shadow_readiness(
        db, candidate_run_id=candidate.id, settings=_settings(), now=now
    )

    assert readiness.ready is False
    assert readiness.consecutive_runs == 1
