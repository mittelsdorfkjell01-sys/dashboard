import numpy as np
import pytest

from app.spatial_fields.phase0 import (
    RegularGrid,
    assert_same_grid,
    normalize_global_axes,
    project_xyz_tile,
    xyz_center_lonlat,
    xyz_pixel_lonlat,
    xyz_tiles_for_bounds,
)


def grid(values: np.ndarray) -> RegularGrid:
    return RegularGrid(
        longitudes=np.array([-45.0, 0.0, 45.0]),
        latitudes=np.array([0.0, 30.0, 60.0]),
        values=values,
        definition={"gridType": "regular_ll"},
    )


def test_xyz_selection_and_center_are_deterministic() -> None:
    tiles = xyz_tiles_for_bounds(-23.5, 29.5, 45.0, 70.5, 4)
    assert len(tiles) == 20
    longitude, latitude = xyz_center_lonlat(4, 8, 5)
    assert longitude == pytest.approx(11.25)
    assert latitude == pytest.approx(48.9225, abs=0.001)
    assert xyz_pixel_lonlat(4, 8, 5, pixel_x=64, pixel_y=64, tile_size=128) == pytest.approx(
        (11.25, 48.9225), abs=0.001
    )


def test_projection_emits_overlap_and_preserves_a_constant_field() -> None:
    projected = project_xyz_tile(
        grid(np.full((3, 3), 7.5)),
        z=2,
        x=2,
        y=1,
        tile_size=32,
        overlap=1,
    )
    assert projected.shape == (34, 34)
    assert np.nanmedian(projected) == pytest.approx(7.5)


def test_adjacent_tiles_share_the_same_overlap_samples() -> None:
    values = np.tile(np.array([-3.0, 0.0, 3.0]), (3, 1))
    source = grid(values)
    left = project_xyz_tile(source, z=2, x=1, y=1, tile_size=32, overlap=1)
    right = project_xyz_tile(source, z=2, x=2, y=1, tile_size=32, overlap=1)
    finite = np.isfinite(left[:, -1]) & np.isfinite(right[:, 1])
    assert finite.any()
    assert left[finite, -1] == pytest.approx(right[finite, 1], abs=1e-5)


def test_icon_sized_nonlinear_grid_has_exact_shared_overlap_samples() -> None:
    longitudes = np.arange(-23.5, 62.5 + 0.0625, 0.0625)
    latitudes = np.arange(29.5, 70.5 + 0.0625, 0.0625)
    lon_mesh, lat_mesh = np.meshgrid(longitudes, latitudes)
    values = np.sin(lon_mesh * 0.7) * 8.0 + np.cos(lat_mesh * 1.1) * 5.0
    source = RegularGrid(
        longitudes=longitudes,
        latitudes=latitudes,
        values=values,
        definition={"gridType": "regular_ll"},
    )
    left = project_xyz_tile(source, z=4, x=9, y=5, tile_size=128, overlap=1)
    right = project_xyz_tile(source, z=4, x=10, y=5, tile_size=128, overlap=1)
    finite = np.isfinite(left[:, -1]) & np.isfinite(right[:, 1])
    assert finite.any()
    assert np.array_equal(left[finite, -1], right[finite, 1])


def test_uv_grids_must_be_identical() -> None:
    left = grid(np.zeros((3, 3)))
    right = RegularGrid(
        longitudes=np.array([-44.0, 0.0, 45.0]),
        latitudes=left.latitudes,
        values=left.values,
        definition=left.definition,
    )
    with pytest.raises(ValueError, match="identical grid"):
        assert_same_grid(left, right)


def test_global_axes_are_sorted_and_strictly_monotonic() -> None:
    # A global 0..360 grid that repeats its wrap column, the way DWD's GWAM
    # and other global products ship it: 0 and 360 are the same meridian.
    longitudes = np.array([0.0, 120.0, 240.0, 360.0])
    latitudes = np.array([0.0, 45.0])
    values = np.array([[1.0, 2.0, 3.0, np.nan], [5.0, 6.0, 7.0, np.nan]])

    lons, lats, out = normalize_global_axes(longitudes, latitudes, values)

    # Ascending, no duplicate meridian, and the column that survives is the
    # real one (0°), not the repeated wrap column full of missing values.
    assert lons.tolist() == [-120.0, 0.0, 120.0]
    assert lats.tolist() == [0.0, 45.0]
    assert out[0].tolist() == [3.0, 1.0, 2.0]
    assert np.isfinite(out).all()
    assert (np.diff(lons) > 0).all()


def test_global_axes_leave_a_regional_grid_alone() -> None:
    longitudes = np.array([-10.0, -5.0, 0.0, 5.0])
    latitudes = np.array([50.0, 55.0])
    values = np.arange(8, dtype=float).reshape(2, 4)

    lons, lats, out = normalize_global_axes(longitudes, latitudes, values)

    assert lons.tolist() == longitudes.tolist()
    assert lats.tolist() == latitudes.tolist()
    assert out.tolist() == values.tolist()
