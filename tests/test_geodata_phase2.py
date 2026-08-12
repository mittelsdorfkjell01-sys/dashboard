import numpy as np
import pytest
from app.forecast.copernicus_gate import preflight_gate
from app.forecast.shadow import (
    MetricRaster,
    RAY_OFFSETS,
    SECTOR_CENTERS,
    analyze_ray,
    analyze_sectors,
    coastline_normals,
    find_water_anchor,
)


def grid(size=801, pixel=300, water=True):
    w = (
        np.ones((size, size), dtype=np.uint8)
        if water
        else np.zeros((size, size), dtype=np.uint8)
    )
    return MetricRaster(
        w,
        np.full_like(w, 80),
        np.zeros_like(w, dtype=float),
        pixel,
        (size // 2, size // 2),
    )


def test_sector_geometry_is_meteorological_and_nine_inner_rays():
    assert SECTOR_CENTERS == (
        0,
        22.5,
        45,
        67.5,
        90,
        112.5,
        135,
        157.5,
        180,
        202.5,
        225,
        247.5,
        270,
        292.5,
        315,
        337.5,
    )
    assert (
        len(RAY_OFFSETS) == 9
        and RAY_OFFSETS[0] == pytest.approx(-9)
        and RAY_OFFSETS[-1] == pytest.approx(9)
    )
    g = grid(size=21, pixel=30)
    g.water[5, 10] = 0
    assert analyze_ray(g, 0, max_m=300)["first_certain_land_m"] == 150
    assert analyze_ray(g, 180, max_m=300)["first_certain_land_m"] is None


def test_open_fetch_is_right_censored_not_exact():
    result = analyze_ray(grid(), 0)
    assert result["censored"] is True and result["first_certain_land_m"] is None
    sectors = analyze_sectors(grid())
    assert len(sectors) == 16 and all(
        s["features"]["fetch"]["censored"] for s in sectors
    )


def test_more_water_and_nearer_higher_blocker_are_monotone():
    closed = grid(size=801)
    closed.water[300:, 400] = 0
    opened = grid(size=801)
    assert (
        analyze_ray(opened, 0)["longest_water_m"]
        >= analyze_ray(closed, 0)["longest_water_m"]
    )
    flat = grid(size=101, pixel=100)
    ridge = grid(size=101, pixel=100)
    ridge.elevation_m[40, 50] = 100
    assert (
        analyze_ray(ridge, 0, max_m=5000)["terrain"]["horizon_angle_deg"]
        > analyze_ray(flat, 0, max_m=5000)["terrain"]["horizon_angle_deg"]
    )


def test_water_anchor_tolerance_and_original_coordinate_unchanged():
    g = grid(size=31, pixel=30, water=False)
    g.water[15, 18] = 1
    anchor = find_water_anchor(g, 250)
    assert anchor["distance_m"] == 90 and g.center == (15, 15)
    assert find_water_anchor(g, 50)["status"] == "unavailable"


def test_lake_normal_and_river_not_applicable():
    g = grid(size=51, pixel=30, water=False)
    yy, xx = np.indices(g.water.shape)
    g.water[(yy - 25) ** 2 + (xx - 25) ** 2 < 100] = 2
    normal = coastline_normals(g, 2)
    assert normal["type"] == "lake_shore" and normal["status"] in {
        "valid",
        "conflicted",
    }
    assert coastline_normals(g, 3)["status"] == "not_applicable"


def test_nodata_does_not_become_land_or_height_and_double_counting_flag():
    g = grid(size=51, pixel=100)
    g.water[:] = 255
    g.elevation_m[:] = np.nan
    result = analyze_ray(g, 0, max_m=2000)
    assert result["coverage"] == 0 and result["terrain"]["horizon_angle_deg"] is None
    forest = grid(size=51, pixel=100)
    forest.landcover[:] = 10
    assert analyze_ray(forest, 0, max_m=2000)["roughness"]["possible_double_counting"]


def test_gate_has_terminal_credential_and_budget_states(monkeypatch):
    assert preflight_gate([], credentials=(None, None)).status == "blocked_credentials"
    bad = [{"product_instance": "COP-DEM_EEA-10-INSP", "size_bytes": 1}]
    assert preflight_gate(bad, credentials=("x", "y")).status == "blocked_license"
    unknown = [{"product_instance": "COP-DEM_GLO-30-DGED", "size_bytes": None}]
    assert preflight_gate(unknown, credentials=("x", "y")).status == "blocked_budget"


def test_shadow_engine_is_not_wired_into_public_publisher():
    import inspect
    from app.forecast import physics, publisher

    assert "forecast.shadow" not in inspect.getsource(publisher)
    assert "forecast.shadow" not in inspect.getsource(physics)
