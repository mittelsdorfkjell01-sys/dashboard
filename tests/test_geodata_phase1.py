from pathlib import Path
import httpx
import numpy as np
import pytest

from app.forecast.geodata import (
    CopernicusDemAdapter,
    WORLDCOVER_CLASSES,
    WorldCoverAdapter,
    analysis_crs,
    tile_code,
)
from app.forecast.geodata_catalog import (
    DatasetDefinition,
    GEODATASETS,
    validate_catalog,
)
from app.forecast.raster_cache import RasterCache, RasterLimitExceeded, RunBudget


def test_catalog_pins_free_glo30_instance_and_legal_fields():
    validate_catalog()
    source = GEODATASETS["cop-dem-glo30"]
    assert source.product_instance == "COP-DEM_GLO-30-DGED"
    assert (
        "WorldDEM-30" in source.attribution and source.fallback_key == "cop-dem-glo90"
    )
    assert GEODATASETS["worldcover-2021"].licence_name == "CC BY 4.0"


def test_restrictive_or_incomplete_catalog_entry_is_rejected():
    base = GEODATASETS["cop-dem-glo30"].__dict__
    with pytest.raises(ValueError):
        DatasetDefinition(
            **{**base, "product_instance": "COP-DEM_EEA-10-INSP"}
        ).validate()
    with pytest.raises(ValueError):
        DatasetDefinition(**{**base, "attribution": ""}).validate()


def test_tiles_crs_high_latitude_and_dateline():
    assert tile_code(39.37, -9.34, 3) == "N39W012"
    assert tile_code(-0.1, 179.9, 3) == "S03E177"
    assert analysis_crs(85, 10) == "EPSG:3413"
    assert analysis_crs(-81, 10) == "EPSG:3031"


def test_worldcover_has_all_eleven_classes_and_metric_rings():
    assert len(WORLDCOVER_CLASSES) == 11
    classes = np.array([[10, 20, 30], [40, 50, 60], [70, 80, 100]])
    distances = np.array([[0, 100, 249], [250, 1000, 1999], [2000, 3000, 4999]])
    rings = WorldCoverAdapter.summarize_rings(classes, distances)
    assert len(rings["0-250m"]["original"]) == 11
    assert rings["250-2000m"]["groups"]["built_up"] == pytest.approx(1 / 3)


def test_dem_water_classes_metrics_and_metadata_validation():
    dem = np.arange(25, dtype=float).reshape(5, 5)
    water = np.zeros((5, 5), dtype=np.uint8)
    water[2, 2] = 2
    result = CopernicusDemAdapter.summarize(dem, water)
    assert result["surface"] == "lake" and result["distance_to_water_m"] == 0
    assert (
        CopernicusDemAdapter.validate_metadata(
            crs="EPSG:4326", vertical_datum="EPSG:3855", layers={"WBM", "HEM"}
        )
        == []
    )
    assert CopernicusDemAdapter.validate_metadata(
        crs="EPSG:4326", vertical_datum="EPSG:3855", layers={"WBM"}
    ) == ["quality_layer_missing"]
    with pytest.raises(ValueError):
        CopernicusDemAdapter.validate_metadata(
            crs="EPSG:3857", vertical_datum="EPSG:3855", layers=set()
        )


def test_cache_range_atomic_hit_dedupe_and_full_download_guard(tmp_path: Path):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert request.headers["range"] == "bytes=0-3"
        return httpx.Response(
            206,
            content=b"COG!",
            headers={"content-length": "4", "content-range": "bytes 0-3/99"},
        )

    cache = RasterCache(
        tmp_path, client=httpx.Client(transport=httpx.MockTransport(handler)), retries=0
    )
    budget = RunBudget(100, 10, 10)
    path, first = cache.fetch(
        "https://official.example/tile.tif",
        dataset="worldcover",
        version="v200",
        asset_key="tile",
        byte_range=(0, 3),
        budget=budget,
    )
    same, second = cache.fetch(
        "https://official.example/tile.tif",
        dataset="worldcover",
        version="v200",
        asset_key="tile",
        byte_range=(0, 3),
        budget=budget,
    )
    assert (
        path == same
        and first["cache_hit"] is False
        and second["cache_hit"] is True
        and calls == 1
    )
    assert not list(tmp_path.rglob("*.part-*"))


def test_cache_rejects_server_ignoring_range_and_byte_limits(tmp_path: Path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"whole-file")
        )
    )
    cache = RasterCache(tmp_path, client=client, retries=0)
    with pytest.raises(RasterLimitExceeded, match="ignored Range"):
        cache.fetch(
            "https://official.example/global.tif",
            dataset="x",
            version="1",
            asset_key="global",
            byte_range=(0, 3),
            budget=RunBudget(100, 100, 100),
        )
    with pytest.raises(RasterLimitExceeded, match="single asset"):
        RunBudget(100, 2, 100).consume(3)


def test_berlin_daily_limit_is_hard(tmp_path: Path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(206, content=b"1234")
        )
    )
    cache = RasterCache(tmp_path, client=client, retries=0, daily_limit_bytes=3)
    with pytest.raises(RasterLimitExceeded, match="daily download limit"):
        cache.fetch(
            "https://official.example/tile.tif",
            dataset="x",
            version="1",
            asset_key="x",
            byte_range=(0, 3),
            budget=RunBudget(10, 10, 10),
        )
    assert not list(tmp_path.rglob(".daily-bytes.json"))
