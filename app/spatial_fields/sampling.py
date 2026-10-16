"""Shared spatial and temporal interpolation for published u/v fields."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

import numpy as np

from app.weather.vectors import uv_to_wind


@dataclass(frozen=True)
class WindSample:
    u_ms: float
    v_ms: float
    speed_ms: float
    direction_from_deg: float | None


def wind_sample(u_ms: float, v_ms: float) -> WindSample:
    speed, direction = uv_to_wind(float(u_ms), float(v_ms))
    return WindSample(float(u_ms), float(v_ms), speed, direction)


def _ascending_axis(
    coordinates: np.ndarray, values: np.ndarray, *, axis: int
) -> tuple[np.ndarray, np.ndarray]:
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.ndim != 1 or len(coords) < 2:
        raise ValueError("sampling axes must be one-dimensional with at least two values")
    deltas = np.diff(coords)
    if np.all(deltas > 0):
        return coords, values
    if np.all(deltas < 0):
        return coords[::-1], np.flip(values, axis=axis)
    raise ValueError("sampling axes must be strictly monotone")


def bilinear_uv(
    longitudes: np.ndarray,
    latitudes: np.ndarray,
    u_values: np.ndarray,
    v_values: np.ndarray,
    *,
    longitude: float,
    latitude: float,
    nodata: float | int | None = None,
) -> WindSample | None:
    """Sample rectilinear u/v values without ever interpolating angles.

    All four neighbours must be available.  Refusing partial interpolation is
    deliberate: filling across a land/coverage hole would manufacture a field.
    """

    u = np.asarray(u_values, dtype=np.float64)
    v = np.asarray(v_values, dtype=np.float64)
    if u.shape != v.shape:
        raise ValueError("u and v grids must have identical shapes")
    if u.ndim != 2:
        raise ValueError("u and v grids must be two-dimensional")
    lons, u = _ascending_axis(longitudes, u, axis=1)
    _, v = _ascending_axis(longitudes, v, axis=1)
    lats, u = _ascending_axis(latitudes, u, axis=0)
    _, v = _ascending_axis(latitudes, v, axis=0)
    if u.shape != (len(lats), len(lons)):
        raise ValueError("grid shape does not match latitude/longitude axes")
    if not (lons[0] <= longitude <= lons[-1] and lats[0] <= latitude <= lats[-1]):
        return None

    x1 = min(max(int(np.searchsorted(lons, longitude, side="right")), 1), len(lons) - 1)
    y1 = min(max(int(np.searchsorted(lats, latitude, side="right")), 1), len(lats) - 1)
    x0, y0 = x1 - 1, y1 - 1
    neighbours_u = np.array([u[y0, x0], u[y0, x1], u[y1, x0], u[y1, x1]])
    neighbours_v = np.array([v[y0, x0], v[y0, x1], v[y1, x0], v[y1, x1]])
    unavailable = ~np.isfinite(neighbours_u) | ~np.isfinite(neighbours_v)
    if nodata is not None:
        unavailable |= neighbours_u == nodata
        unavailable |= neighbours_v == nodata
    if unavailable.any():
        return None

    dx = 0.0 if lons[x1] == lons[x0] else (longitude - lons[x0]) / (lons[x1] - lons[x0])
    dy = 0.0 if lats[y1] == lats[y0] else (latitude - lats[y0]) / (lats[y1] - lats[y0])

    def interpolate(values: np.ndarray) -> float:
        bottom = values[y0, x0] * (1 - dx) + values[y0, x1] * dx
        top = values[y1, x0] * (1 - dx) + values[y1, x1] * dx
        return float(bottom * (1 - dy) + top * dy)

    return wind_sample(interpolate(u), interpolate(v))


def temporal_uv(
    lower: WindSample,
    upper: WindSample,
    *,
    lower_time: datetime,
    upper_time: datetime,
    target_time: datetime,
) -> WindSample:
    """Linearly interpolate vector components between two UTC instants."""

    for instant in (lower_time, upper_time, target_time):
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("temporal interpolation requires timezone-aware instants")
    if upper_time <= lower_time:
        raise ValueError("upper_time must be after lower_time")
    if not lower_time <= target_time <= upper_time:
        raise ValueError("target_time must be bracketed by lower_time and upper_time")
    alpha = (target_time - lower_time).total_seconds() / (
        upper_time - lower_time
    ).total_seconds()
    u_ms = lower.u_ms + (upper.u_ms - lower.u_ms) * alpha
    v_ms = lower.v_ms + (upper.v_ms - lower.v_ms) * alpha
    if not math.isfinite(u_ms) or not math.isfinite(v_ms):
        raise ValueError("interpolated wind vector must be finite")
    return wind_sample(u_ms, v_ms)
