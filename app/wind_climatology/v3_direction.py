"""Strict meteorological-from direction handling for V3."""

from __future__ import annotations

import math


def normalize_direction(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("wind direction must be finite")
    return value % 360.0


def canonical_windows(windows) -> list[dict[str, float]]:
    if isinstance(windows, dict):
        windows = [windows]
    if not isinstance(windows, (list, tuple)):
        return []
    result = []
    for window in windows:
        if not isinstance(window, dict):
            continue
        start = window.get("start_deg", window.get("min"))
        end = window.get("end_deg", window.get("max"))
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        result.append({"start_deg": normalize_direction(float(start)), "end_deg": normalize_direction(float(end))})
    return result


def direction_matches(value: float | None, windows: list[dict[str, float]]) -> bool:
    """Missing measurements never match; empty windows never mean all directions."""
    if value is None or not windows:
        return False
    direction = normalize_direction(value)
    for window in windows:
        start, end = window["start_deg"], window["end_deg"]
        if (start <= end and start <= direction <= end) or (start > end and (direction >= start or direction <= end)):
            return True
    return False


_COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass_point(deg: float) -> str:
    """16-point compass label for a meteorological-from bearing."""
    return _COMPASS_16[round(normalize_direction(deg) / 22.5) % 16]


def direction_label(windows: list[dict[str, float]]) -> str | None:
    """Human-readable summary of reviewed usable-direction windows, e.g. 'WSW bis NW'."""
    if not windows:
        return None
    parts = [f"{compass_point(window['start_deg'])} bis {compass_point(window['end_deg'])}" for window in windows]
    return " und ".join(parts)
