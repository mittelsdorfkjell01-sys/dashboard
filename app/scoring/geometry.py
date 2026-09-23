"""Small compass helpers shared by the gates (direction windows, onshore test)."""

from __future__ import annotations

import math
from typing import Literal


DirectionStatus = Literal["ok", "unusable", "unknown"]


def angular_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings (degrees), in [0, 180]."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def _in_window(deg: float, window: dict) -> bool:
    lo, hi = window["min"] % 360.0, window["max"] % 360.0
    deg = deg % 360.0
    if lo <= hi:
        return lo <= deg <= hi
    return deg >= lo or deg <= hi  # wraps through 0/360


def valid_windows(windows) -> list[dict]:
    """Keep only well-formed ``{"min","max"}`` window dicts.

    Curators may set the sentinel ``"n/a"`` (or leave junk) on
    ``usable_wind_directions``; treating that as *no constraint* rather than
    crashing keeps scoring/similarity robust.
    """
    if isinstance(windows, dict):
        windows = [windows]
    if not isinstance(windows, (list, tuple)):
        return []
    return [
        w
        for w in windows
        if isinstance(w, dict)
        and isinstance(w.get("min"), (int, float))
        and not isinstance(w.get("min"), bool)
        and isinstance(w.get("max"), (int, float))
        and not isinstance(w.get("max"), bool)
        and math.isfinite(float(w["min"]))
        and math.isfinite(float(w["max"]))
    ]


def direction_status(deg: float | None, windows) -> DirectionStatus:
    """Return the explicit relationship between a bearing and usable windows.

    ``unknown`` means either the bearing or the window definition is missing or
    invalid (including the editorial ``"n/a"`` sentinel). Callers may keep a
    legacy result usable, but must never award it the same best grade as ``ok``.
    """
    if (
        not isinstance(deg, (int, float))
        or isinstance(deg, bool)
        or not math.isfinite(float(deg))
    ):
        return "unknown"
    valid = valid_windows(windows)
    if not valid:
        return "unknown"
    return "ok" if any(_in_window(float(deg), w) for w in valid) else "unusable"


def direction_in_windows(deg: float | None, windows) -> bool:
    """Compatibility bool: only an explicitly unusable direction fails.

    Missing data remains passable for legacy callers, while
    :func:`direction_status` lets scoring cap that unknown case at ``mäßig``.
    """
    return direction_status(deg, windows) != "unusable"


def is_strong_onshore(
    wind_kt: float | None,
    wind_dir: float | None,
    facing: float | None,
    onshore_max_kt: float,
) -> bool:
    """Strong onshore = wind above the threshold blowing from the sea onto the beach.

    ``facing`` is the bearing the beach faces (toward the water); wind direction is
    the meteorological *from* bearing, so onshore means the wind comes from within
    90 deg of ``facing``.
    """
    if facing is None or wind_kt is None or wind_dir is None:
        return False
    if wind_kt <= onshore_max_kt:
        return False
    return angular_diff(wind_dir, facing) <= 90.0
