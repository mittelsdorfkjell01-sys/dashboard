"""Experimental ICON-EU field processing used only by the phase-0 data spike."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np


WEB_MERCATOR_LIMIT = 20_037_508.342789244


@dataclass(frozen=True)
class RegularGrid:
    longitudes: np.ndarray
    latitudes: np.ndarray
    values: np.ndarray
    definition: dict[str, bool | int | float | str]

    @property
    def coordinate_checksum(self) -> str:
        digest = hashlib.sha256()
        digest.update(np.asarray(self.longitudes, dtype="<f8").tobytes())
        digest.update(np.asarray(self.latitudes, dtype="<f8").tobytes())
        return digest.hexdigest()


def normalize_global_axes(
    longitudes: np.ndarray, latitudes: np.ndarray, values: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ascending, strictly monotonic axes for a regular lat/lon grid.

    Global grids arrive in 0..360 order, so normalizing to -180..180 crosses
    the dateline and the columns have to be reordered.  A global grid also
    commonly repeats its wrap column (both 0 and 360, which normalize to the
    same longitude), and that duplicate breaks every consumer that assumes a
    uniform spacing: `project_xyz_tile` locates a source column as
    ``(lon - lon[0]) / mean(diff(lon))``, which is off by one beyond the
    duplicate, and if the repeated column carries the GRIB's missing value the
    result is a one-column hole at that longitude.  That is where the grey
    line between Britain and Norway came from on the GWAM wave map
    (2026-10-12).  The first occurrence wins; the duplicate is dropped.
    """
    longitudes = ((np.asarray(longitudes, dtype=np.float64) + 180.0) % 360.0) - 180.0
    latitudes = np.asarray(latitudes, dtype=np.float64)
    longitude_order = np.argsort(longitudes, kind="stable")
    longitudes = longitudes[longitude_order]
    values = values[:, longitude_order]
    unique = np.concatenate(([True], np.diff(longitudes) > 0))
    if not unique.all():
        longitudes = longitudes[unique]
        values = values[:, unique]
    latitude_order = np.argsort(latitudes, kind="stable")
    latitudes = latitudes[latitude_order]
    values = values[latitude_order, :]
    unique_rows = np.concatenate(([True], np.diff(latitudes) > 0))
    if not unique_rows.all():
        latitudes = latitudes[unique_rows]
        values = values[unique_rows, :]
    return longitudes, latitudes, values


def decode_regular_latlon(message: bytes) -> RegularGrid:
    """Decode one GRIB message and retain the native, reproducible grid definition."""
    try:
        from eccodes import codes_get, codes_get_array, codes_new_from_message, codes_release
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError("phase-0 requires the eccodes Python package") from exc

    handle = codes_new_from_message(message)
    try:
        ni, nj = int(codes_get(handle, "Ni")), int(codes_get(handle, "Nj"))
        grid_type = str(codes_get(handle, "gridType"))
        if grid_type != "regular_ll":
            raise ValueError(f"phase-0 expected regular_ll, received {grid_type}")
        values = np.asarray(codes_get_array(handle, "values"), dtype=np.float64)
        try:
            missing_value = float(codes_get(handle, "missingValue"))
            values[np.isclose(values, missing_value)] = np.nan
        except Exception:
            pass
        lats = np.asarray(codes_get_array(handle, "latitudes"), dtype=np.float64)
        lons = np.asarray(codes_get_array(handle, "longitudes"), dtype=np.float64)
        if values.size != ni * nj:
            raise ValueError("GRIB value count does not match Ni/Nj")
        values = values.reshape(nj, ni)
        latitudes = lats.reshape(nj, ni)[:, 0]
        longitudes = lons.reshape(nj, ni)[0, :]
        longitudes, latitudes, values = normalize_global_axes(
            longitudes, latitudes, values
        )
        definition = {
            key: codes_get(handle, key)
            for key in (
                "gridType",
                "Ni",
                "Nj",
                "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
                "latitudeOfLastGridPointInDegrees",
                "longitudeOfLastGridPointInDegrees",
                "iDirectionIncrementInDegrees",
                "jDirectionIncrementInDegrees",
                "iScansNegatively",
                "jScansPositively",
                "jPointsAreConsecutive",
            )
        }
    finally:
        codes_release(handle)

    if np.any(np.diff(longitudes) <= 0) or np.any(np.diff(latitudes) <= 0):
        raise ValueError("phase-0 requires monotone regular latitude/longitude axes")
    return RegularGrid(longitudes, latitudes, values, definition)


def assert_same_grid(left: RegularGrid, right: RegularGrid) -> None:
    if left.values.shape != right.values.shape:
        raise ValueError("u/v GRIB fields have different shapes")
    if not np.array_equal(left.longitudes, right.longitudes) or not np.array_equal(
        left.latitudes, right.latitudes
    ):
        raise ValueError("u/v GRIB fields do not share an identical grid")


def _tile_x(longitude: float, zoom: int) -> int:
    return min((1 << zoom) - 1, max(0, int((longitude + 180.0) / 360.0 * (1 << zoom))))


def _tile_y(latitude: float, zoom: int) -> int:
    latitude = min(85.05112878, max(-85.05112878, latitude))
    value = (1.0 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2.0
    return min((1 << zoom) - 1, max(0, int(value * (1 << zoom))))


def xyz_tiles_for_bounds(
    west: float, south: float, east: float, north: float, zoom: int
) -> list[tuple[int, int, int]]:
    return [
        (zoom, x, y)
        for y in range(_tile_y(north, zoom), _tile_y(south, zoom) + 1)
        for x in range(_tile_x(west, zoom), _tile_x(east, zoom) + 1)
    ]


def xyz_bounds_mercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    size = 2 * WEB_MERCATOR_LIMIT / (1 << z)
    west = -WEB_MERCATOR_LIMIT + x * size
    east = west + size
    north = WEB_MERCATOR_LIMIT - y * size
    south = north - size
    return west, south, east, north


def xyz_center_lonlat(z: int, x: int, y: int) -> tuple[float, float]:
    tiles = 1 << z
    longitude = (x + 0.5) / tiles * 360.0 - 180.0
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / tiles))))
    return longitude, latitude


def xyz_pixel_lonlat(
    z: int, x: int, y: int, *, pixel_x: float, pixel_y: float, tile_size: int
) -> tuple[float, float]:
    """Return lon/lat for a pixel coordinate relative to the unpadded XYZ tile."""
    tiles = 1 << z
    world_x = x + pixel_x / tile_size
    world_y = y + pixel_y / tile_size
    longitude = world_x / tiles * 360.0 - 180.0
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * world_y / tiles))))
    return longitude, latitude


def project_xyz_tile(
    grid: RegularGrid,
    *,
    z: int,
    x: int,
    y: int,
    tile_size: int,
    overlap: int,
) -> np.ndarray:
    """Sample a native regular-lat/lon component into an overlapped XYZ tile.

    Computing target coordinates directly keeps shared overlap pixels bitwise
    deterministic across neighbouring tiles. Per-tile GDAL reprojection may
    approximate the transform independently and produced >1 m/s seams on a
    real ICON-EU grid even though both pixels represented the same coordinate.
    """
    dx = float(np.diff(grid.longitudes).mean())
    dy = float(np.diff(grid.latitudes).mean())
    width = tile_size + overlap * 2
    pixels = np.arange(width, dtype=np.float64) - overlap + 0.5
    tiles = float(1 << z)
    world_x = x + pixels / tile_size
    world_y = y + pixels / tile_size
    longitudes = world_x / tiles * 360.0 - 180.0
    latitudes = np.degrees(np.arctan(np.sinh(np.pi * (1.0 - 2.0 * world_y / tiles))))

    source_x = (longitudes - float(grid.longitudes[0])) / dx
    source_y = (latitudes - float(grid.latitudes[0])) / dy
    x0 = np.floor(source_x).astype(np.int64)
    y0 = np.floor(source_y).astype(np.int64)
    x1 = x0 + 1
    y1 = y0 + 1
    valid_x = (x0 >= 0) & (x1 < grid.values.shape[1])
    valid_y = (y0 >= 0) & (y1 < grid.values.shape[0])
    safe_x0 = np.clip(x0, 0, grid.values.shape[1] - 1)
    safe_x1 = np.clip(x1, 0, grid.values.shape[1] - 1)
    safe_y0 = np.clip(y0, 0, grid.values.shape[0] - 1)
    safe_y1 = np.clip(y1, 0, grid.values.shape[0] - 1)
    wx = (source_x - x0)[None, :]
    wy = (source_y - y0)[:, None]
    values = np.asarray(grid.values, dtype=np.float64)
    v00 = values[safe_y0[:, None], safe_x0[None, :]]
    v10 = values[safe_y0[:, None], safe_x1[None, :]]
    v01 = values[safe_y1[:, None], safe_x0[None, :]]
    v11 = values[safe_y1[:, None], safe_x1[None, :]]
    interpolated = (
        v00 * (1.0 - wx) * (1.0 - wy)
        + v10 * wx * (1.0 - wy)
        + v01 * (1.0 - wx) * wy
        + v11 * wx * wy
    )
    destination = np.full((width, width), np.nan, dtype=np.float32)
    valid = valid_y[:, None] & valid_x[None, :] & np.isfinite(v00) & np.isfinite(v10) & np.isfinite(v01) & np.isfinite(v11)
    destination[valid] = interpolated[valid].astype(np.float32)
    return destination
