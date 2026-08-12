from datetime import datetime, timezone

import pytest

from app.forecast.contracts import GridPoint, NormalizedModelValue, ProviderRequest
from app.forecast.providers import DwdIconProvider, InvalidModelData, NoaaGfsProvider
from app.forecast.registry import MODELS, SOURCES, public_attributions
from app.forecast.physics import apply_automatic_physics
from app.forecast.consensus import combine

RUN = datetime(2026, 8, 12, 0, tzinfo=timezone.utc)


def request(hours=(0, 3)):
    return ProviderRequest(
        latitude=54.4,
        longitude=10.2,
        model="gfs-0p25",
        run_at=RUN,
        forecast_hours=hours,
    )


def test_registry_has_direct_global_and_european_models_and_legal_records():
    enabled = {m.key for m in MODELS if m.enabled}
    assert {"gfs-0p25", "icon-global", "icon-eu", "icon-d2"} <= enabled
    assert all(SOURCES[m.provider].official_url.startswith("https://") for m in MODELS)
    assert {a["provider"] for a in public_attributions({"noaa-gfs", "dwd-icon"})} == {
        "NOAA/NCEP",
        "Deutscher Wetterdienst",
    }


def test_noaa_grid_indices_wrap_longitude():
    assert NoaaGfsProvider.point_indices(90, 0) == (0, 0)
    assert NoaaGfsProvider.point_indices(-90, -0.25) == (720, 1439)


def test_noaa_ascii_normalizes_uv_units_temperature_and_gust_floor():
    payload = """ugrd10m, [2][1][1]\n3, 0\nvgrd10m, [2][1][1]\n4, 5\ngustsfc, [2][1][1]\n2, 8\ntmp2m, [2][1][1]\n273.15, 274.15\napcpsfc, [2][1][1]\n0, 1.5\n"""
    rows = NoaaGfsProvider.parse_ascii(payload, request())
    assert len(rows) == 2 and rows[0].speed_ms == pytest.approx(5)
    assert (
        rows[0].gust_ms == pytest.approx(5)
        and "gust_clamped_to_mean" in rows[0].quality_flags
    )
    assert rows[1].temperature_c == pytest.approx(1) and rows[
        1
    ].precipitation_mm == pytest.approx(1.5)
    assert rows[1].valid_at.hour == 3


def test_noaa_incomplete_payload_fails_closed():
    with pytest.raises(InvalidModelData):
        NoaaGfsProvider.parse_ascii("ugrd10m, [1]\n3", request((0,)))


def test_normalized_contract_rejects_naive_time_and_clamps_gust():
    with pytest.raises(ValueError):
        NormalizedModelValue(
            provider="x",
            model="x",
            model_run=datetime.now(),
            valid_at=RUN,
            fetched_at=RUN,
            grid_point=GridPoint(latitude=0, longitude=0, distance_km=0),
            horizontal_resolution_km=10,
            horizon_hours=0,
            u_ms=1,
            v_ms=1,
            speed_ms=1,
            direction_deg=1,
            source_key="x",
        )


def test_dwd_urls_are_variable_scoped_and_run_scoped():
    url = DwdIconProvider.file_url("icon-eu", RUN, "u_10m", 3)
    assert "/icon-eu/grib/00/u_10m/" in url and "2026081200_003_U_10M.grib2.bz2" in url
    assert len(DwdIconProvider.checksum(b"grib")) == 64


def test_provider_request_rejects_unsorted_or_duplicate_hours():
    with pytest.raises(ValueError):
        request((3, 0))
    with pytest.raises(ValueError):
        request((0, 0))


def value(model="gfs-0p25", u=3, v=4, gust=6):
    return NormalizedModelValue(
        provider="test",
        model=model,
        model_run=RUN,
        valid_at=RUN,
        fetched_at=RUN,
        grid_point=GridPoint(latitude=0, longitude=0, distance_km=0),
        horizontal_resolution_km=10,
        horizon_hours=0,
        u_ms=u,
        v_ms=v,
        speed_ms=(u * u + v * v) ** 0.5,
        direction_deg=216.869897,
        gust_ms=gust,
        source_key="test",
    )


def test_physics_is_neutral_without_raster_and_bounded_with_shelter():
    raw = value()
    neutral = apply_automatic_physics(raw, None)
    assert neutral.speed_ms == raw.speed_ms and not neutral.components
    profile = {
        "corrections_enabled": True,
        "elevation_m": 100,
        "sectors": [{"terrain_shelter": 1} for _ in range(16)],
    }
    corrected = apply_automatic_physics(raw, profile, model_elevation_m=0)
    assert raw.speed_ms * 0.78 <= corrected.speed_ms < raw.speed_ms
    assert {c.key for c in corrected.components} == {"elevation", "terrain_shelter"}


def test_consensus_vector_aggregation_family_cap_and_gust_floor():
    rows = [
        apply_automatic_physics(value("gfs-0p25", 3, 4, 4), None),
        apply_automatic_physics(value("icon-global", 4, 3, 7), None),
        apply_automatic_physics(value("icon-eu", 4, 3, 7), None),
    ]
    result = combine(rows, now=RUN)
    assert result.model_count == 3 and result.gust_ms >= result.speed_ms
    assert result.low_ms <= result.speed_ms <= result.high_ms
    assert result.confidence in {"hoch", "mittel", "niedrig"}


def test_public_contract_never_exposes_model_registry(client, db):
    from app.main import app
    from app.live.deps import get_cache, get_om_client
    from app.live.cache import InMemoryCache
    from tests.live_helpers import FakeOpenMeteoClient
    from app.models import Spot
    from app.seed.seed import seed
    from sqlalchemy import select

    seed(db)
    spot = db.scalar(select(Spot).where(Spot.status == "published"))
    app.dependency_overrides[get_om_client] = lambda: FakeOpenMeteoClient(data_days=11)
    app.dependency_overrides[get_cache] = lambda: InMemoryCache()
    try:
        response = client.get(f"/spots/{spot.id}/forecast")
    finally:
        app.dependency_overrides.pop(get_om_client, None)
        app.dependency_overrides.pop(get_cache, None)
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "surfwinddata" and body["models"] == []
    assert body["product"] == "Surfwinddata Forecast" and body["attributions"]


def test_recalculate_is_deduplicated_and_role_protected(
    client, curator_client, db, monkeypatch
):
    from app.models import Spot
    from app.seed.seed import seed
    from sqlalchemy import select

    seed(db)
    spot = db.scalar(select(Spot).limit(1))
    # Curators may run a single-spot calculation; batch remains admin-only.
    monkeypatch.setattr(
        "app.api.admin_weather._run_job_in_new_session", lambda job_id: None
    )
    first = client.post(f"/admin/weather/spots/{spot.id}/recalculate")
    second = client.post(f"/admin/weather/spots/{spot.id}/recalculate")
    assert first.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert (
        curator_client.post("/admin/weather/batch/recalculate?limit=1").status_code
        == 403
    )
