from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import numpy as np

from app.models.wave_verification import WaveForecastSample, WaveObservationPlatform
from app.models.weather_field import WeatherFieldPublication
from app.forecast.refresh_worker import build_plan
from app.spatial_fields.catalog import sync_free_model_catalog
from app.spatial_fields.control_plane import get_or_create_run
from app.spatial_fields.phase0 import RegularGrid
from app.spatial_fields.pipeline import process_run
from app.spatial_fields.providers import (
    DwdWaveFieldProvider,
    FieldSourceSlice,
    NOAA_GFS_WAVE_ROLES,
    NoaaGfsWaveProvider,
    _normalize_wave_field,
)
from app.spatial_fields.serving import load_active_manifest, sample_active_field
from app.spatial_fields.spot_forecast import active_wave_publication_ids
from app.spatial_fields.storage import MemoryFieldObjectStorage


def _grid(values: np.ndarray) -> RegularGrid:
    longitudes = np.linspace(-12.0, 44.0, 57)
    latitudes = np.linspace(28.0, 68.0, 41)
    definition = {
        "gridType": "regular_ll", "Ni": 57, "Nj": 41,
        "latitudeOfFirstGridPointInDegrees": 28.0,
        "longitudeOfFirstGridPointInDegrees": -12.0,
        "latitudeOfLastGridPointInDegrees": 68.0,
        "longitudeOfLastGridPointInDegrees": 44.0,
        "iDirectionIncrementInDegrees": 1.0,
        "jDirectionIncrementInDegrees": 1.0,
        "iScansNegatively": 0, "jScansPositively": 1,
        "jPointsAreConsecutive": 0,
    }
    return RegularGrid(longitudes, latitudes, values, definition)


class SyntheticWaveProvider:
    model_key = "dwd-ewam"

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        longitude, latitude = np.meshgrid(
            np.linspace(-12.0, 44.0, 57), np.linspace(28.0, 68.0, 41)
        )
        height = 1.8 + longitude * 0.002
        direction = np.full_like(height, 270.0)
        radians = np.radians(direction)
        scalars = {
            "total_wave_height": _grid(height),
            "total_wave_direction": _grid(direction),
            "total_wave_period": _grid(np.full_like(height, 8.5)),
            "wind_sea_height": _grid(np.full_like(height, 0.6)),
            "wind_sea_direction": _grid(np.full_like(height, 250.0)),
            "wind_sea_period": _grid(np.full_like(height, 4.2)),
            "primary_swell_height": _grid(np.full_like(height, 1.5)),
            "primary_swell_direction": _grid(np.full_like(height, 275.0)),
            "primary_swell_period": _grid(np.full_like(height, 9.0)),
        }
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=_grid(-height * np.sin(radians)),
            v=_grid(-height * np.cos(radians)),
            gust=None,
            source_urls=("memory://dwd-ewam/synthetic",),
            downloaded_bytes=1024,
            scalar_fields=scalars,
            product="wave",
            vector_u_name="wave_u",
            vector_v_name="wave_v",
            magnitude_name="total_wave_height",
        )


class SyntheticNoaaWaveProvider:
    model_key = "noaa-gfs-wave"

    def fetch(self, run_at: datetime, forecast_hour: int) -> FieldSourceSlice:
        height = np.full((41, 57), 2.1)
        direction = np.full_like(height, 300.0)
        radians = np.radians(direction)
        scalars = {
            "total_wave_height": _grid(height),
            "primary_wave_direction": _grid(direction),
            "primary_wave_period": _grid(np.full_like(height, 9.5)),
            "wind_sea_height": _grid(np.full_like(height, 0.7)),
            "wind_sea_direction": _grid(np.full_like(height, 280.0)),
            "wind_sea_period": _grid(np.full_like(height, 4.5)),
            "primary_swell_height": _grid(np.full_like(height, 1.6)),
            "primary_swell_direction": _grid(np.full_like(height, 305.0)),
            "primary_swell_period": _grid(np.full_like(height, 10.0)),
        }
        return FieldSourceSlice(
            forecast_hour=forecast_hour,
            valid_time=run_at + timedelta(hours=forecast_hour),
            u=_grid(-height * np.sin(radians)),
            v=_grid(-height * np.cos(radians)),
            gust=None,
            source_urls=("memory://noaa-gfs-wave/synthetic",),
            downloaded_bytes=1024,
            scalar_fields=scalars,
            product="wave",
            vector_u_name="wave_u",
            vector_v_name="wave_v",
            magnitude_name="total_wave_height",
        )


def test_dwd_wave_url_uses_public_ewam_layout() -> None:
    provider = DwdWaveFieldProvider("dwd-ewam")
    url = provider.file_url(datetime(2026, 10, 9, 12, tzinfo=timezone.utc), "swh", 7)
    assert url.endswith("/ewam/grib/12/swh/EWAM_SWH_2026100912_007.grib2.bz2")


def test_dwd_wave_directions_are_normalized_below_360_degrees() -> None:
    source = _grid(np.array([[360.004] * 57] * 41))
    normalized = _normalize_wave_field("total_wave_direction", source)
    assert float(np.nanmax(normalized.values)) < 360.0


def test_noaa_gfs_wave_uses_free_global_subset_and_discovers_ten_day_tail() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"grib", request=request)

    provider = NoaaGfsWaveProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    run_at = datetime(2026, 10, 11, 6, tzinfo=timezone.utc)

    assert provider.discover_latest(
        run_at + timedelta(hours=2), forecast_hours=[168, 240]
    ) == run_at
    source_url, payload = provider._request(run_at, 240)

    assert payload == b"grib"
    assert "filter_gfswave.pl" in source_url
    query = dict(requests[-1].url.params)
    assert query["file"] == "gfswave.t06z.global.0p25.f240.grib2"
    assert query["dir"] == "/gfs.20261011/06/wave/gridded"
    assert query["var_HTSGW"] == query["var_SWELL"] == "on"
    assert query["leftlon"] == "0.0"
    assert query["rightlon"] == "360.0"


def test_noaa_primary_wave_fields_are_not_mapped_to_total_wave_semantics() -> None:
    assert NOAA_GFS_WAVE_ROLES["swh"] == "total_wave_height"
    assert NOAA_GFS_WAVE_ROLES["perpw"] == "primary_wave_period"
    assert NOAA_GFS_WAVE_ROLES["dirpw"] == "primary_wave_direction"


def test_wave_run_publishes_and_samples_arbitrary_point(db) -> None:
    model = next(row for row in sync_free_model_catalog(db) if row.model_key == "dwd-ewam")
    model_run = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    run = get_or_create_run(
        db,
        model=model,
        model_run_at=model_run,
        processing_version="wave-synthetic-v1",
        contract_version="weather-field-v2",
        coverage={"west": -10.5, "south": 30.0, "east": 42.0, "north": 66.0},
        native_grid={"status": "pending_source_inspection"},
        valid_times=[model_run.isoformat().replace("+00:00", "Z")],
    )
    platform = WaveObservationPlatform(
        provider_key="copernicus-marine",
        external_id="synthetic-north-sea-buoy",
        name="Synthetic North Sea buoy",
        latitude=50.0,
        longitude=8.0,
        region_code="north-sea",
        location_class="offshore",
        active=True,
        platform_metadata={},
    )
    db.add(platform)
    db.commit()
    settings = SimpleNamespace(
        weather_field_scope_key="wind-test",
        weather_field_primary_model="icon-eu",
        wave_field_scope_key="waves-test",
        wave_field_primary_model="dwd-ewam",
        weather_field_public_base_url="/weather-field-assets",
        weather_field_max_run_download_bytes=10_000_000,
        weather_field_auto_activate=False,
        wave_field_auto_activate=True,
    )
    storage = MemoryFieldObjectStorage(public_base_url="/weather-field-assets")
    result = process_run(
        db, run.id, provider=SyntheticWaveProvider(), storage=storage, settings=settings
    )
    publication = db.get(WeatherFieldPublication, result["publication_id"])
    assert publication.active is True
    archived = db.query(WaveForecastSample).filter_by(platform_id=platform.id).one()
    assert archived.significant_height_m > 1.7
    assert archived.period_s == 8.5
    assert archived.period_semantic == "energy_period_tm10"
    assert archived.direction_semantic == "mean_direction_from"
    assert result["wave_backtest_samples"] >= 1
    active = load_active_manifest(db, storage=storage, scope_key="waves-test")
    assert active is not None
    assert {item.name for item in active.manifest.variables} >= {
        "wave_u", "wave_v", "total_wave_height", "primary_swell_height"
    }
    semantics = {item.name: item.semantic for item in active.manifest.variables}
    assert semantics["total_wave_period"] == "energy_period_tm10"
    assert semantics["total_wave_direction"] == "mean_direction_from"
    sample = sample_active_field(
        db,
        storage=storage,
        scope_key="waves-test",
        latitude=50.0,
        longitude=8.0,
        valid_at=model_run,
        model_key="dwd-ewam",
    )
    assert sample["product"] == "model_wave"
    assert sample["total_wave_height_m"] > 1.7
    assert sample["total_wave_direction_from_deg"] == 270.0
    assert sample["primary_swell_period_s"] == 9.0

    publication_ids = active_wave_publication_ids(
        db,
        settings=SimpleNamespace(
            wave_field_public_enabled=True,
            wave_field_scope_key="waves-test",
            wave_field_primary_model="dwd-ewam",
            wave_field_fallback_model="dwd-gwam",
            wave_field_extended_model="noaa-gfs-wave",
        ),
        now=model_run + timedelta(hours=1),
    )
    spot_id = "spot-after-wave-activation"
    plan = build_plan(
        [SimpleNamespace(id=spot_id, status="published")],
        [
            SimpleNamespace(
                spot_id=spot_id,
                generated_at=model_run + timedelta(minutes=30),
                internal={
                    "wave_field": {"active_publication_ids": ["previous-publication"]}
                },
            )
        ],
        now=model_run + timedelta(hours=1),
        active_wave_publication_ids=publication_ids,
    )
    assert publication_ids == (str(publication.id),)
    assert plan.wave_context_changed_spot_ids == (spot_id,)


def test_noaa_wave_run_exposes_primary_wave_details_without_relabeling(db) -> None:
    model = next(
        row
        for row in sync_free_model_catalog(db)
        if row.model_key == "noaa-gfs-wave"
    )
    model_run = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    valid_at = model_run + timedelta(hours=168)
    run = get_or_create_run(
        db,
        model=model,
        model_run_at=model_run,
        processing_version="wave-noaa-semantics-v1",
        contract_version="weather-field-v2",
        coverage={"west": -10.5, "south": 30.0, "east": 42.0, "north": 66.0},
        native_grid={"status": "pending_source_inspection"},
        valid_times=[valid_at.isoformat().replace("+00:00", "Z")],
    )
    db.commit()
    settings = SimpleNamespace(
        weather_field_scope_key="wind-test",
        weather_field_primary_model="icon-eu",
        wave_field_scope_key="waves-noaa-semantics",
        wave_field_primary_model="dwd-ewam",
        weather_field_public_base_url="/weather-field-assets",
        weather_field_max_run_download_bytes=10_000_000,
        weather_field_auto_activate=False,
        wave_field_auto_activate=True,
    )
    storage = MemoryFieldObjectStorage(public_base_url="/weather-field-assets")

    result = process_run(
        db,
        run.id,
        provider=SyntheticNoaaWaveProvider(),
        storage=storage,
        settings=settings,
    )
    scope = "waves-noaa-semantics:noaa-gfs-wave"
    active = load_active_manifest(db, storage=storage, scope_key=scope)
    assert active is not None
    semantics = {item.name: item.semantic for item in active.manifest.variables}
    assert "total_wave_period" not in semantics
    assert "total_wave_direction" not in semantics
    assert semantics["primary_wave_period"] == "primary_wave_mean_period"
    assert semantics["primary_wave_direction"] == "primary_wave_direction_from"

    sample = sample_active_field(
        db,
        storage=storage,
        scope_key=scope,
        latitude=50.0,
        longitude=8.0,
        valid_at=valid_at,
        model_key="noaa-gfs-wave",
    )
    assert sample["total_wave_height_m"] == 2.1
    assert sample["total_wave_period_s"] is None
    assert sample["total_wave_direction_from_deg"] is None
    assert sample["primary_wave_period_s"] == 9.5
    assert sample["primary_wave_direction_from_deg"] == 300.0
    assert result["public_effect"] == "field-publication"
