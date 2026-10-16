from types import SimpleNamespace
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import time

from app.api.weather_fields import _cached_manifest_response
from app.forecast.providers import DwdIconProvider
from app.spatial_fields.jobs import _forecast_hours_for_model
from app.spatial_fields.pipeline import _lod_profile, provider_for_model
from app.spatial_fields.providers import ICON_D2_COVERAGE, IconD2FieldProvider
from app.spatial_fields.scopes import model_scope


def test_model_scopes_keep_primary_backward_compatible() -> None:
    assert model_scope("europe-wind", "icon-eu", primary_model="icon-eu") == "europe-wind"
    assert (
        model_scope("europe-wind", "gfs-0p25", primary_model="icon-eu")
        == "europe-wind:gfs-0p25"
    )


def test_icon_d2_uses_regional_coverage_and_higher_display_lods() -> None:
    settings = SimpleNamespace(
        weather_field_request_timeout_seconds=45,
        weather_field_max_source_bytes=16_777_216,
    )
    provider = provider_for_model("icon-d2", settings=settings)
    source_lods, manifest_lods, display_resolution = _lod_profile("icon-d2")

    assert isinstance(provider, IconD2FieldProvider)
    assert provider.coverage == ICON_D2_COVERAGE
    assert source_lods == (5, 6)
    assert manifest_lods[-1]["consumer_zoom_max"] == 10
    assert display_resolution == 5.0


def test_icon_d2_uses_dwd_two_dimensional_filename() -> None:
    url = DwdIconProvider.file_url(
        "icon-d2", datetime(2026, 10, 4, tzinfo=timezone.utc), "u_10m", 0
    )
    assert url.endswith("_000_2d_u_10m.grib2.bz2")
    assert "icon-d2_germany_icosahedral" in url


def test_operational_forecast_profiles_bound_regional_and_global_work() -> None:
    configured = [
        *range(0, 25),
        *range(27, 73, 3),
        *range(78, 121, 6),
        *range(126, 241, 6),
    ]

    assert _forecast_hours_for_model("icon-d2", configured) == [
        *range(0, 25),
        *range(27, 49, 3),
    ]
    assert _forecast_hours_for_model("icon-eu", configured) == [
        *range(0, 25),
        *range(27, 73, 3),
        *range(78, 121, 6),
    ]
    assert _forecast_hours_for_model("gfs-0p25", configured) == [
        0,
        3,
        6,
        9,
        12,
        18,
        24,
        36,
        48,
        72,
        96,
        120,
        *range(126, 241, 6),
    ]
    assert _forecast_hours_for_model("dwd-ewam", list(range(0, 100))) == list(
        range(0, 79)
    )
    assert _forecast_hours_for_model("dwd-gwam", list(range(0, 200))) == list(
        range(0, 175, 3)
    )
    assert _forecast_hours_for_model(
        "noaa-gfs-wave", list(range(168, 241))
    ) == list(range(168, 241, 3))


def test_manifest_response_cache_collapses_concurrent_cold_reads() -> None:
    builds: list[int] = []

    def build() -> dict:
        builds.append(1)
        time.sleep(0.05)
        return {"publication_id": "test"}

    key = f"test-cold-read-{time.monotonic_ns()}"
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(
            executor.map(lambda _: _cached_manifest_response(key, build), range(40))
        )

    assert builds == [1]
    assert all(result == {"publication_id": "test"} for result in results)
