"""Hard pass/fail gates. A failed gate means simply 'nein' — no hazard output.

``values`` is a flat dict of the conditions to test (live instant or a
climatology histogram cell). Missing optional fields don't fail a gate.
"""

from __future__ import annotations

import math

from app.scoring.geometry import angular_diff, direction_status, is_strong_onshore
from app.scoring.params import get_params


def _bearing(value) -> float | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        return None
    return float(value)


def _wind_gates(
    values: dict, editorial: dict, params: dict, profile: dict | None = None
) -> list[str]:
    reasons: list[str] = []
    personal = (profile or {}).get("personal_band") or {}
    band = params["wind"]
    minimum = personal.get("min_kt", band["min_kt"])
    maximum = personal.get("max_kt", band["max_kt"])
    w = values.get("wind_kt")
    if w is None or w < minimum:
        reasons.append("wind_too_light")
    elif w > maximum:
        reasons.append("wind_too_strong")
    gust = values.get("gust_kt")
    gust_tolerance = personal.get("gust_tolerance_kt")
    if (
        w is not None
        and gust is not None
        and gust_tolerance is not None
        and gust > w + gust_tolerance
    ):
        reasons.append("gust_too_strong")

    windows = editorial.get("usable_wind_directions", editorial.get("usable_directions"))
    status = direction_status(values.get("wind_dir"), windows)
    if status == "unusable":
        reasons.append("direction_unusable")
    elif status == "unknown":
        reasons.append("direction_unknown")

    if (profile or {}).get("level") == "beginner":
        wind_dir = _bearing(values.get("wind_dir"))
        facing = _bearing(editorial.get("facing"))
        if wind_dir is None or facing is None:
            reasons.append("offshore_unknown")
        elif (
            angular_diff(wind_dir, facing) >= 110.0
            and editorial.get("beginner_offshore_ok") is not True
        ):
            reasons.append("offshore_for_level")
    return reasons


def _wave_gates(values: dict, editorial: dict, params: dict) -> list[str]:
    reasons: list[str] = []
    band = params["swell"]
    h = values.get("swell_m")
    if h is None or h < band["min_m"]:
        reasons.append("swell_too_small")
    elif h > band["max_m"]:
        reasons.append("swell_too_big")

    p = values.get("period_s")
    if p is not None and p < band["period_min_s"]:
        reasons.append("period_too_short")

    windows = editorial.get("usable_swell_directions", editorial.get("swell_window"))
    status = direction_status(values.get("swell_dir"), windows)
    if status == "unusable":
        reasons.append("swell_direction_unusable")
    elif status == "unknown":
        reasons.append("direction_unknown")

    # ``editorial.tide`` may be a structured dict (dependence + window) or just a
    # free-text note ("mid", "n/a"); only the structured form drives the gate.
    tide = editorial.get("tide") or params.get("tide") or {}
    if isinstance(tide, dict) and tide.get("dependence"):
        tv, window = values.get("tide"), tide.get("window")
        valid_window = (
            isinstance(window, (list, tuple))
            and len(window) == 2
            and all(
                isinstance(v, (int, float))
                and not isinstance(v, bool)
                and math.isfinite(float(v))
                for v in window
            )
            and 0.0 <= float(window[0]) <= float(window[1]) <= 1.0
        )
        if tv is None or not valid_window:
            reasons.append("tide_unknown")
        elif not (window[0] <= tv <= window[1]):
            reasons.append("tide_out_of_window")

    if is_strong_onshore(
        values.get("wind_kt"),
        values.get("wind_dir"),
        editorial.get("facing"),
        params.get("onshore_wind_max_kt", 999.0),
    ):
        reasons.append("strong_onshore")
    return reasons


def apply_gates(
    values: dict,
    editorial: dict | None,
    sport: str,
    params: dict | None = None,
    profile: dict | None = None,
) -> tuple[bool, list[str]]:
    """Return ``(passed, fail_reasons)`` for the hard feasibility gates.

    Kite/wind: daylight, usable direction, strength within ``[min, max]``.
    Surf: swell direction window, height ``[min, max]``, period >= min, tide window
    (if tide-dependent), and no strong onshore wind.
    """
    params = params or get_params(sport)
    editorial = editorial or {}
    reasons: list[str] = []

    if params.get("daylight_required") and values.get("daylight") is False:
        reasons.append("night")

    if params["sport_type"] == "wind":
        reasons += _wind_gates(values, editorial, params, profile)
    else:
        reasons += _wave_gates(values, editorial, params)

    informational = {"direction_unknown", "offshore_unknown", "tide_unknown"}
    return (not any(reason not in informational for reason in reasons), reasons)
