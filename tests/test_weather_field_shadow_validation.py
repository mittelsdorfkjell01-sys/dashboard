from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from sqlalchemy import select, update

from app.models import ForecastSnapshot, Spot
from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldModel,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.models.weather_field_shadow import (
    WeatherFieldShadowMetric,
    WeatherFieldShadowRun,
    WeatherFieldShadowSample,
)
from app.seed.seed import seed
from app.spatial_fields.jobs import enqueue_shadow_validation, run_job
from app.spatial_fields.shadow_validation import (
    circular_difference_deg,
    comparison_metrics,
    horizon_bucket,
)
from app.spatial_fields.storage import MemoryFieldObjectStorage


def _settings(scope: str):
    return SimpleNamespace(
        weather_field_scope_key=scope,
        weather_field_shadow_profile_version="field-shadow-test-v1",
        weather_field_shadow_pilot_config="config/does-not-exist.json",
        weather_field_shadow_pilot_group="core",
        weather_field_shadow_max_spots=5,
        weather_field_shadow_max_samples=100,
        weather_field_shadow_max_horizon_hours=72,
        weather_field_max_attempts=3,
    )


def test_shadow_metric_math_and_horizon_boundaries() -> None:
    assert [horizon_bucket(hour) for hour in (0, 5, 6, 23, 24, 47, 48, 72, 73)] == [
        "T+0-6",
        "T+0-6",
        "T+6-24",
        "T+6-24",
        "T+24-48",
        "T+24-48",
        "T+48-72",
        "T+48-72",
        "T+72+",
    ]
    assert circular_difference_deg(350, 10) == 20
    metrics = comparison_metrics(
        [
            {"speed_delta_ms": 1.0, "direction_delta_deg": 20.0, "gust_delta_ms": 2.0},
            {"speed_delta_ms": -1.0, "direction_delta_deg": 10.0, "gust_delta_ms": None},
        ]
    )
    assert metrics["speed"] == {
        "bias_ms": 0.0,
        "mae_ms": 1.0,
        "rmse_ms": 1.0,
        "count": 2,
    }
    assert metrics["direction_mae_deg"] == 15.0
    assert metrics["gust"]["mae_ms"] == 2.0


def test_shadow_worker_persists_immutable_comparisons_without_public_effect(
    db, monkeypatch
) -> None:
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.status == "published").order_by(Spot.name))
    assert spot is not None
    db.execute(
        update(ForecastSnapshot)
        .where(ForecastSnapshot.spot_id == spot.id)
        .values(active=False)
    )
    model_run = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    snapshot = ForecastSnapshot(
        spot_id=spot.id,
        generated_at=model_run,
        valid_until=model_run + timedelta(hours=8),
        consensus_version="legacy-test",
        physics_version="physics-test",
        quality_level="baseline",
        fallback_status="open_meteo_transition",
        payload={
            "days": [
                {
                    "hours": [
                        {
                            "time": (model_run + timedelta(hours=hour)).isoformat(),
                            "wind_ms": 5.0,
                            "gust_ms": 7.0,
                            "dir": 270.0,
                        }
                        for hour in (0, 3, 6)
                    ]
                }
            ]
        },
        internal={"source": "open-meteo"},
        attributions=[{"provider": "Open-Meteo"}],
        active=True,
    )
    suffix = uuid.uuid4().hex[:8]
    model = WeatherFieldModel(
        provider_key="test",
        model_key=f"field-shadow-{suffix}",
        display_name="Field shadow test",
        status="active",
        coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
        native_grid={"gridType": "regular_ll"},
        cadence_hours=6,
        forecast_step_hours=1,
        max_horizon_hours=120,
        priority=99,
        licence={"name": "test"},
        attribution=[{"provider": "test"}],
    )
    db.add_all([snapshot, model])
    db.flush()
    field_run = WeatherFieldRun(
        model_id=model.id,
        provider_key="test",
        model_key=model.model_key,
        model_run_at=model_run,
        contract_version="weather-field-v2",
        processing_version="field-shadow-test",
        status="ready",
        coverage=model.coverage,
        native_grid=model.native_grid,
        valid_times=[
            (model_run + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")
            for hour in (0, 3, 6)
        ],
    )
    db.add(field_run)
    db.flush()
    manifest = WeatherFieldAsset(
        run_id=field_run.id,
        asset_type="manifest",
        object_key=f"tests/{suffix}/manifest.json",
        size_bytes=1,
        sha256="a" * 64,
        content_type="application/json",
        compression="none",
        status="verified",
    )
    db.add(manifest)
    db.flush()
    scope = f"field-shadow-{suffix}"
    publication = WeatherFieldPublication(
        scope_key=scope,
        run_id=field_run.id,
        manifest_asset_id=manifest.id,
        status="active",
        active=True,
        activated_at=model_run,
        generation=1,
    )
    db.add(publication)
    db.commit()

    def sample(_db, **kwargs):
        assert kwargs["scope_key"] == scope
        return {
            "publication_id": str(publication.id),
            "model": model.model_key,
            "u_ms": 6.0,
            "v_ms": 0.0,
            "speed_ms": 6.0,
            "direction_from_deg": 280.0,
            "gust_ms": 8.0,
        }

    monkeypatch.setattr(
        "app.spatial_fields.shadow_validation.sample_active_field", sample
    )
    settings = _settings(scope)
    job, created = enqueue_shadow_validation(db, settings=settings, now=model_run)
    assert created is True and job is not None
    repeated, repeated_created = enqueue_shadow_validation(
        db, settings=settings, now=model_run + timedelta(minutes=30)
    )
    assert repeated_created is False and repeated.id == job.id
    later, later_created = enqueue_shadow_validation(
        db, settings=settings, now=model_run + timedelta(hours=1)
    )
    assert later_created is True and later.id != job.id
    later.status = "superseded"
    job.options = {**job.options, "spot_ids": [str(spot.id)]}
    job.status = "processing"
    db.commit()

    completed = run_job(
        db,
        job.id,
        settings=settings,
        storage=MemoryFieldObjectStorage(),
        now=model_run,
    )

    assert completed.status == "succeeded"
    assert completed.diagnostics["samples"] == 3
    shadow = db.scalar(
        select(WeatherFieldShadowRun).where(WeatherFieldShadowRun.job_id == job.id)
    )
    assert shadow is not None and shadow.status == "succeeded"
    samples = db.scalars(
        select(WeatherFieldShadowSample).where(
            WeatherFieldShadowSample.shadow_run_id == shadow.id
        )
    ).all()
    assert len(samples) == 3
    assert all(row.speed_delta_ms == 1.0 for row in samples)
    overall = db.scalar(
        select(WeatherFieldShadowMetric).where(
            WeatherFieldShadowMetric.shadow_run_id == shadow.id,
            WeatherFieldShadowMetric.dimensions == {"scope": "overall"},
        )
    )
    assert overall is not None
    assert overall.metrics["speed"]["mae_ms"] == 1.0
    assert overall.metrics["direction_mae_deg"] == 10.0
    assert snapshot.active is True
    assert publication.active is True
    assert shadow.diagnostics["cutover_authorized"] is False


def test_shadow_admin_evidence_is_authenticated_and_readable(
    client, anon_client, db
) -> None:
    seed(db)
    assert anon_client.get("/admin/weather-fields/shadow/status").status_code == 401
    status = client.get("/admin/weather-fields/shadow/status")
    assert status.status_code == 200
    assert status.json()["cutover_authorized"] is False
    assert status.json()["spot_rollout"]["stage"] in {
        "shadow", "pilot", "regional", "europe"
    }
    runs = client.get("/admin/weather-fields/shadow/runs")
    assert runs.status_code == 200
    assert isinstance(runs.json()["runs"], list)
    metrics = client.get("/admin/weather-fields/shadow/metrics")
    assert metrics.status_code == 200
    assert isinstance(metrics.json()["metrics"], list)
    spot = db.scalar(select(Spot).where(Spot.status == "published").order_by(Spot.name))
    readiness = client.get(f"/admin/weather-fields/spot-rollout/{spot.id}")
    assert readiness.status_code == 200
    assert readiness.json()["enabled"] is False
    assert readiness.json()["reasons"]
    assert anon_client.get(
        f"/admin/weather-fields/spot-rollout/{spot.id}"
    ).status_code == 401
