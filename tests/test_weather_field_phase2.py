from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import numpy as np

from app.config import get_settings
from app.models.weather_field import (
    WeatherFieldJob,
    WeatherFieldModel,
    WeatherFieldPublication,
    WeatherFieldRun,
)
from app.spatial_fields.catalog import sync_free_model_catalog
from app.spatial_fields.control_plane import get_or_create_run
from app.spatial_fields.jobs import (
    _run_discovery,
    claim_next_job,
    enqueue_discovery,
    enqueue_process_run,
    enqueue_retention,
    run_job,
)
from app.spatial_fields.monitoring import weather_field_health
from app.spatial_fields.phase0 import RegularGrid
from app.spatial_fields.pipeline import process_run
from app.spatial_fields.providers import FieldSourceSlice, GfsFieldProvider, IconEuFieldProvider
from app.spatial_fields.publication import REQUIRED_HARD_GATES, activate_publication
from app.spatial_fields.retention import prune_weather_field_runs
from app.spatial_fields.serving import (
    load_active_manifest,
    sample_active_field,
    sample_active_field_series,
)
from app.spatial_fields.storage import MemoryFieldObjectStorage


def _settings(*, auto_activate: bool = False):
    return SimpleNamespace(
        weather_field_scope_key="europe-wind-test",
        weather_field_processing_version="test-v1",
        weather_field_public_base_url="/weather-field-assets",
        weather_field_max_run_download_bytes=10_000_000,
        weather_field_auto_activate=auto_activate,
        weather_field_max_attempts=3,
        weather_field_forecast_hours=[0],
        weather_field_activation_min_shadow_runs=3,
        weather_field_activation_lookback_hours=30,
        weather_field_activation_max_download_bytes=10_000_000,
        weather_field_activation_max_asset_bytes=10_000_000,
        weather_field_activation_max_processing_seconds=300,
    )


class SyntheticProvider:
    provider_key = "dwd"
    model_key = "icon-eu"

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        longitudes = np.linspace(-30.0, 50.0, 81)
        latitudes = np.linspace(25.0, 75.0, 51)
        lon, lat = np.meshgrid(longitudes, latitudes)
        definition = {
            "gridType": "regular_ll",
            "Ni": 81,
            "Nj": 51,
            "latitudeOfFirstGridPointInDegrees": 25.0,
            "longitudeOfFirstGridPointInDegrees": -30.0,
            "latitudeOfLastGridPointInDegrees": 75.0,
            "longitudeOfLastGridPointInDegrees": 50.0,
            "iDirectionIncrementInDegrees": 1.0,
            "jDirectionIncrementInDegrees": 1.0,
            "iScansNegatively": 0,
            "jScansPositively": 1,
            "jPointsAreConsecutive": 0,
        }
        u = RegularGrid(longitudes, latitudes, 5.0 + lon * 0.01, definition)
        v = RegularGrid(longitudes, latitudes, 2.0 + lat * 0.01, definition)
        gust = RegularGrid(longitudes, latitudes, np.hypot(u.values, v.values) + 3.0, definition)
        scalar_fields = {
            "temperature_2m": RegularGrid(
                longitudes, latitudes, 12.0 + lat * 0.1, definition
            ),
            "precipitation": RegularGrid(
                longitudes, latitudes, np.maximum(0.0, lon * 0.01), definition
            ),
            "pressure_msl": RegularGrid(
                longitudes, latitudes, 1015.0 - lat * 0.05, definition
            ),
            "cloud_cover": RegularGrid(
                longitudes, latitudes, np.clip(40.0 + lon * 0.2, 0.0, 100.0), definition
            ),
        }
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=u,
            v=v,
            gust=gust,
            source_urls=(f"memory://icon-eu/f{forecast_hour:03d}",),
            downloaded_bytes=1024,
            scalar_fields=scalar_fields,
        )


def test_claim_next_job_can_limit_worker_to_retention(db) -> None:
    now = datetime.now(timezone.utc)
    discovery, _ = enqueue_discovery(db, now=now, settings=_settings())
    retention, _ = enqueue_retention(db, now=now)

    claimed = claim_next_job(db, now=now, allowed_kinds=("retention",))

    assert claimed is not None
    assert claimed.id == retention.id
    assert claimed.status == "processing"
    db.refresh(discovery)
    assert discovery.status == "queued"


def test_sample_active_field_series_covers_every_valid_time_and_skips_gaps(db) -> None:
    icon = next(model for model in sync_free_model_catalog(db) if model.model_key == "icon-eu")
    model_run = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    valid_times = [model_run + timedelta(hours=hour) for hour in (0, 1, 2)]
    run = get_or_create_run(
        db,
        model=icon,
        model_run_at=model_run,
        processing_version="series-synthetic",
        contract_version="weather-field-v2",
        coverage={"west": -23.5, "south": 29.5, "east": 45.0, "north": 70.5},
        native_grid={"status": "pending_source_inspection"},
        valid_times=[instant.isoformat().replace("+00:00", "Z") for instant in valid_times],
    )
    db.commit()
    storage = MemoryFieldObjectStorage(public_base_url="/weather-field-assets")
    settings = _settings(auto_activate=True)
    settings.weather_field_forecast_hours = [0, 1, 2]
    result = process_run(
        db,
        run.id,
        provider=SyntheticProvider(),
        storage=storage,
        settings=settings,
    )
    publication = db.get(WeatherFieldPublication, result["publication_id"])
    activate_publication(db, publication.id, actor="test", reason="series synthetic run")
    db.commit()

    active = load_active_manifest(db, storage=storage, scope_key="europe-wind-test")
    assert active is not None

    samples = sample_active_field_series(
        db,
        storage=storage,
        scope_key="europe-wind-test",
        latitude=50.0,
        longitude=8.0,
        valid_times=active.manifest.valid_times,
    )
    assert [sample["valid_at"] for sample in samples] == valid_times
    assert all(sample["product"] == "model_wind" for sample in samples)
    assert all(sample["temperature_c"] is not None for sample in samples)

    # A time outside the published horizon is skipped, never fatal, so the strip
    # degrades to the hours that do have data.
    with_gap = sample_active_field_series(
        db,
        storage=storage,
        scope_key="europe-wind-test",
        latitude=50.0,
        longitude=8.0,
        valid_times=[*active.manifest.valid_times, model_run + timedelta(hours=48)],
    )
    assert len(with_gap) == len(samples)


def test_provider_discovery_and_gfs_request_are_bounded_to_free_sources() -> None:
    now = datetime(2026, 10, 3, 14, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert IconEuFieldProvider(client=client).discover_latest(now) == datetime(
        2026, 10, 3, 12, tzinfo=timezone.utc
    )
    assert GfsFieldProvider(client=client).discover_latest(now) == datetime(
        2026, 10, 3, 12, tzinfo=timezone.utc
    )

    requested = []

    def incomplete_latest(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        unavailable = "_2026100312_120_" in request.url.path
        return httpx.Response(404 if unavailable else 200, request=request)

    complete = IconEuFieldProvider(
        client=httpx.Client(transport=httpx.MockTransport(incomplete_latest))
    ).discover_latest(now, forecast_hours=[0, 120])
    assert complete == datetime(2026, 10, 3, 6, tzinfo=timezone.utc)
    assert any("_120_" in url for url in requested)

    captured = {}

    def subset(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, content=b"grib", request=request)

    provider = GfsFieldProvider(client=httpx.Client(transport=httpx.MockTransport(subset)))
    _, payload = provider._request(now.replace(hour=12), 3)
    assert payload == b"grib"
    assert captured["var_UGRD"] == captured["var_VGRD"] == captured["var_GUST"] == "on"
    assert captured["var_TMP"] == captured["var_APCP"] == "on"
    assert captured["var_PRMSL"] == captured["var_TCDC"] == "on"
    assert captured["leftlon"] == "0.0"
    assert captured["rightlon"] == "360.0"


def test_phase2_pipeline_stages_atomic_candidate_and_samples_same_assets(db) -> None:
    icon = next(model for model in sync_free_model_catalog(db) if model.model_key == "icon-eu")
    model_run = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    run = get_or_create_run(
        db,
        model=icon,
        model_run_at=model_run,
        processing_version="phase2-synthetic",
        contract_version="weather-field-v2",
        coverage={"west": -23.5, "south": 29.5, "east": 45.0, "north": 70.5},
        native_grid={"status": "pending_source_inspection"},
        valid_times=[model_run.isoformat().replace("+00:00", "Z")],
    )
    db.commit()
    storage = MemoryFieldObjectStorage(public_base_url="/weather-field-assets")
    result = process_run(
        db,
        run.id,
        provider=SyntheticProvider(),
        storage=storage,
        settings=_settings(auto_activate=True),
    )

    assert result["run_status"] == "ready"
    assert result["publication_status"] == "staged"
    assert result["public_effect"] == "none"
    assert any("need 3 consecutive" in reason for reason in result["activation_blockers"])
    assert set(result["quality"]) == REQUIRED_HARD_GATES
    assert all(result["quality"].values())

    publication = db.get(WeatherFieldPublication, result["publication_id"])
    activate_publication(db, publication.id, actor="test", reason="verified synthetic run")
    db.commit()
    active = load_active_manifest(
        db, storage=storage, scope_key="europe-wind-test"
    )
    assert active is not None
    assert active.manifest.publication_id == active.publication_id
    assert {variable.name for variable in active.manifest.variables} == {
        "wind_u",
        "wind_v",
        "wind_gust",
        "temperature_2m",
        "precipitation",
        "pressure_msl",
        "cloud_cover",
    }
    sample = sample_active_field(
        db,
        storage=storage,
        scope_key="europe-wind-test",
        latitude=50.0,
        longitude=8.0,
        valid_at=model_run,
    )
    assert sample["publication_id"] == active.publication_id
    assert sample["run_id"] == str(run.id)
    assert sample["product"] == "model_wind"
    assert abs(sample["u_ms"] - 5.08) < 0.08
    assert abs(sample["v_ms"] - 2.5) < 0.08
    assert abs(sample["temperature_c"] - 17.0) < 0.08
    assert abs(sample["precipitation_mm"] - 0.08) < 0.03
    assert abs(sample["pressure_hpa"] - 1012.5) < 0.15
    assert abs(sample["cloud_cover_percent"] - 41.6) < 0.15

    # A retained same-cycle candidate (for example a prior retry) is evidence,
    # not a pending rollout once that cycle is already active.
    db.add(
        WeatherFieldPublication(
            scope_key="europe-wind-test",
            run_id=run.id,
            manifest_asset_id=publication.manifest_asset_id,
            status="staged",
            active=False,
            generation=0,
        )
    )
    db.commit()
    health_settings = _settings()
    health_settings.weather_field_processing_stale_minutes = 30
    health_settings.weather_field_pipeline_enabled = True
    health_settings.weather_field_public_enabled = True
    health = weather_field_health(
        db,
        storage=storage,
        settings=health_settings,
        now=model_run + timedelta(hours=1),
    )
    assert health["status"] == "ok"
    assert health["shadow_readiness"] is None
    assert not any(
        issue["code"] == "shadow_rollout_not_ready" for issue in health["issues"]
    )


def test_scheduler_jobs_are_idempotent(db) -> None:
    now = datetime(2026, 10, 3, 12, 30, tzinfo=timezone.utc)
    discovery_settings = SimpleNamespace(
        weather_field_processing_version="field-v2.0.1",
        weather_field_forecast_hours=[0, 3, 6],
    )
    first, created = enqueue_discovery(db, now=now, settings=discovery_settings)
    repeated, repeated_created = enqueue_discovery(
        db, now=now + timedelta(minutes=20), settings=discovery_settings
    )
    assert created is True
    assert repeated_created is False
    assert first.id == repeated.id
    assert first.options["processing_version"] == "field-v2.0.1"
    assert first.options["forecast_hours"] == [0, 3, 6]
    assert first.options["active_models"] == [
        "dwd-ewam",
        "dwd-gwam",
        "gfs-0p25",
        "icon-d2",
        "icon-eu",
        "noaa-gfs-wave",
    ]

    catalog = sync_free_model_catalog(db)
    next(model for model in catalog if model.model_key == "icon-d2").status = "disabled"
    db.commit()
    changed_models, changed_models_created = enqueue_discovery(
        db, now=now + timedelta(minutes=20), settings=discovery_settings
    )
    assert changed_models_created is True
    assert changed_models.id != first.id
    assert changed_models.options["active_models"] == [
        "dwd-ewam",
        "dwd-gwam",
        "gfs-0p25",
        "icon-eu",
        "noaa-gfs-wave",
    ]

    expanded, expanded_created = enqueue_discovery(
        db,
        now=now + timedelta(minutes=20),
        settings=SimpleNamespace(
            weather_field_processing_version="field-v2.0.1",
            weather_field_forecast_hours=[0, 3, 6, 9],
        ),
    )
    assert expanded_created is True
    assert expanded.id != first.id

    waves_only, waves_only_created = enqueue_discovery(
        db,
        now=now + timedelta(minutes=20),
        settings=discovery_settings,
        model_keys=("dwd-ewam", "dwd-gwam", "noaa-gfs-wave"),
    )
    assert waves_only_created is True
    assert waves_only.options["active_models"] == [
        "dwd-ewam",
        "dwd-gwam",
        "noaa-gfs-wave",
    ]

    retention, retention_created = enqueue_retention(db, now=now)
    repeated_retention, repeated_retention_created = enqueue_retention(
        db, now=now + timedelta(hours=4)
    )
    assert retention_created is True
    assert repeated_retention_created is False
    assert retention.id == repeated_retention.id


def test_discovery_uses_the_profile_frozen_in_the_job(db, monkeypatch) -> None:
    model_run = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)

    class DiscoverOnlyProvider:
        def discover_latest(self, now, *, forecast_hours=None):
            return model_run

    monkeypatch.setattr(
        "app.spatial_fields.jobs.provider_for_model",
        lambda model_key, settings: DiscoverOnlyProvider(),
    )
    current_settings = SimpleNamespace(
        weather_field_processing_version="field-current",
        weather_field_forecast_hours=[0],
    )
    result = _run_discovery(
        db,
        settings=current_settings,
        now=model_run + timedelta(hours=2),
        options={
            "processing_version": "field-frozen",
            "forecast_hours": [0, 3],
        },
    )

    run = db.get(WeatherFieldRun, result["models"][0]["run_id"])
    assert run.processing_version == "field-frozen"
    assert run.valid_times == [
        "2026-10-03T12:00:00Z",
        "2026-10-03T15:00:00Z",
    ]

    run.status = "ready"
    db.commit()
    repeated = _run_discovery(
        db,
        settings=current_settings,
        now=model_run + timedelta(hours=2),
        options={
            "processing_version": "field-frozen",
            "forecast_hours": [0, 3],
        },
    )
    reused = next(item for item in repeated["models"] if item["run_id"] == str(run.id))
    assert reused["run_status"] == "ready"
    assert reused["process_job_id"] is None
    assert reused["reused"] is True


def test_discovery_executes_only_the_frozen_model_subset(db, monkeypatch) -> None:
    model_run = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)

    class DiscoverOnlyProvider:
        def discover_latest(self, now, *, forecast_hours=None):
            return model_run

    monkeypatch.setattr(
        "app.spatial_fields.jobs.provider_for_model",
        lambda model_key, settings: DiscoverOnlyProvider(),
    )
    result = _run_discovery(
        db,
        settings=SimpleNamespace(
            weather_field_processing_version="field-subset",
            weather_field_forecast_hours=[0],
        ),
        now=model_run + timedelta(hours=2),
        options={
            "processing_version": "field-subset",
            "forecast_hours": [0],
            "active_models": ["dwd-ewam"],
        },
    )

    assert [item["model"] for item in result["models"]] == ["dwd-ewam"]


def test_phase2_diagnostic_routes_are_mounted(client, monkeypatch) -> None:
    # Same reason as in test_spatial_field_contract: this asserts the DEFAULT,
    # disabled state, so it pins the flags instead of reading the developer's
    # own .env (2026-10-12).
    settings = get_settings()
    monkeypatch.setattr(settings, "weather_field_public_enabled", False)
    monkeypatch.setattr(settings, "wave_field_public_enabled", False)
    runs = client.get("/weather-fields/wind/runs")
    assert runs.status_code == 200
    assert "runs" in runs.json()
    health = client.get("/weather-fields/wind/health")
    assert health.status_code == 200
    assert health.json()["public_enabled"] is False
    wave_health = client.get("/weather-fields/waves/health")
    assert wave_health.status_code == 200
    assert wave_health.json()["public_enabled"] is False
    assert wave_health.json()["primary"]["scope_key"] == "europe-waves"
    assert wave_health.json()["fallback"]["scope_key"] == "europe-waves:dwd-gwam"
    assert wave_health.json()["extended"]["scope_key"] == "europe-waves:noaa-gfs-wave"


def test_failed_processing_is_retried_as_new_immutable_run(db, monkeypatch) -> None:
    icon = next(model for model in sync_free_model_catalog(db) if model.model_key == "icon-eu")
    model_run = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    run = get_or_create_run(
        db,
        model=icon,
        model_run_at=model_run,
        processing_version="phase2-retry-source",
        contract_version="weather-field-v2",
        coverage={"west": -23.5, "south": 29.5, "east": 45.0, "north": 70.5},
        native_grid={"status": "pending_source_inspection"},
        valid_times=[model_run.isoformat().replace("+00:00", "Z")],
    )
    process_job, _ = enqueue_process_run(db, run)
    process_job.status = "processing"
    process_job.attempt_count = 1
    db.commit()

    class FailingProvider:
        model_key = "icon-eu"

        def fetch(self, run_at, forecast_hour):
            raise RuntimeError("provider offline")

    monkeypatch.setattr(
        "app.spatial_fields.jobs.provider_for_model",
        lambda model_key, settings: FailingProvider(),
    )
    completed = run_job(
        db,
        process_job.id,
        settings=_settings(),
        storage=MemoryFieldObjectStorage(),
    )
    assert completed.status == "superseded"
    original = db.get(WeatherFieldRun, run.id)
    assert original.status == "failed"
    retry_job_id = completed.diagnostics["retry_job_id"]
    retry_job = db.get(WeatherFieldJob, retry_job_id)
    assert retry_job.status == "queued"
    assert retry_job.options["retry_count"] == 1
    retry_run = db.get(WeatherFieldRun, retry_job.run_id)
    assert retry_run.status == "discovered"


def test_stalled_processing_is_recovered_as_a_new_immutable_run(db) -> None:
    from app.spatial_fields.jobs import recover_stalled_jobs

    icon = next(model for model in sync_free_model_catalog(db) if model.model_key == "icon-eu")
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    run = get_or_create_run(
        db,
        model=icon,
        model_run_at=now - timedelta(hours=6),
        processing_version="stalled-source",
        contract_version="weather-field-v2",
        coverage={"west": -23.5, "south": 29.5, "east": 45.0, "north": 70.5},
        native_grid={"status": "pending_source_inspection"},
        valid_times=[(now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")],
    )
    run.status = "processing"
    run.started_at = now - timedelta(hours=2)
    job, _ = enqueue_process_run(db, run)
    job.status = "processing"
    job.attempt_count = 1
    job.started_at = now - timedelta(hours=2)
    db.commit()

    settings = _settings()
    settings.weather_field_processing_stale_minutes = 30
    recovered = recover_stalled_jobs(db, settings=settings, now=now)

    assert recovered[0]["status"] == "superseded"
    assert db.get(WeatherFieldRun, run.id).status == "failed"
    replacement = db.get(WeatherFieldJob, recovered[0]["recovery_job_id"])
    assert replacement.status == "queued"
    assert db.get(WeatherFieldRun, replacement.run_id).status == "discovered"


def test_retention_counts_distinct_model_cycles_not_retry_rows(db) -> None:
    icon = WeatherFieldModel(
        provider_key="test",
        model_key="retention-cycle-test",
        display_name="Retention cycle test",
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
    db.add(icon)
    db.flush()
    latest = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    runs = []
    for model_run, version in (
        (latest, "retention-primary"),
        (latest, "retention-retry"),
        (latest - timedelta(hours=6), "retention-previous"),
        (latest - timedelta(hours=12), "retention-old"),
    ):
        run = get_or_create_run(
            db,
            model=icon,
            model_run_at=model_run,
            processing_version=version,
            contract_version="weather-field-v2",
            coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
            native_grid={"gridType": "regular_ll"},
            valid_times=[model_run.isoformat().replace("+00:00", "Z")],
        )
        run.status = "ready"
        runs.append(run)
    db.commit()

    result = prune_weather_field_runs(
        db, storage=MemoryFieldObjectStorage(), retain_runs=2
    )

    # Retention is global, so a developer database can contain other eligible
    # model runs. This scenario only owns and asserts the four rows above.
    assert result["expired_runs"] >= 1
    assert [db.get(WeatherFieldRun, run.id).status for run in runs] == [
        "ready",
        "ready",
        "ready",
        "expired",
    ]


def test_retention_dry_run_reports_without_mutating(db) -> None:
    icon = WeatherFieldModel(
        provider_key="test",
        model_key="retention-dry-run-test",
        display_name="Retention dry-run test",
        status="active",
        coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
        native_grid={"gridType": "regular_ll"},
        cadence_hours=6,
        forecast_step_hours=1,
        max_horizon_hours=120,
        priority=100,
        licence={"name": "test"},
        attribution=[{"provider": "test"}],
    )
    db.add(icon)
    db.flush()
    latest = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    runs = []
    for offset in (0, 6, 12):
        run = get_or_create_run(
            db,
            model=icon,
            model_run_at=latest - timedelta(hours=offset),
            processing_version="retention-dry-run",
            contract_version="weather-field-v2",
            coverage={"west": -23.5, "south": 29.5, "east": 45, "north": 70.5},
            native_grid={"gridType": "regular_ll"},
            valid_times=[(latest - timedelta(hours=offset)).isoformat().replace("+00:00", "Z")],
        )
        run.status = "ready"
        runs.append(run)
    db.commit()

    result = prune_weather_field_runs(
        db,
        storage=MemoryFieldObjectStorage(),
        retain_runs=2,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["candidate_runs"] >= 1
    assert result["expired_runs"] == 0
    assert [db.get(WeatherFieldRun, run.id).status for run in runs] == [
        "ready",
        "ready",
        "ready",
    ]
