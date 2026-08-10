"""Wind-vector helpers using the meteorological 'direction from' convention."""

from __future__ import annotations

import math
from collections.abc import Iterable


def normalize_direction(direction_degrees: float) -> float:
    """Normalize an angle to the half-open interval [0, 360)."""
    normalized = float(direction_degrees) % 360.0
    # Floating-point cancellation around north can otherwise leak a value such
    # as 359.99999999999994 although 0° and 360° are the same direction.
    if math.isclose(normalized, 360.0, abs_tol=1e-12):
        return 0.0
    return normalized


def wind_to_uv(speed_ms: float, direction_degrees: float) -> tuple[float, float]:
    """Convert speed/direction-from into eastward ``u`` and northward ``v``."""
    radians = math.radians(normalize_direction(direction_degrees))
    speed = float(speed_ms)
    return -speed * math.sin(radians), -speed * math.cos(radians)


def uv_to_wind(u_ms: float, v_ms: float) -> tuple[float, float | None]:
    """Convert vector components into speed and direction-from.

    Calm wind has no physically meaningful direction and therefore returns
    ``None`` instead of inventing north.
    """
    speed = math.hypot(float(u_ms), float(v_ms))
    if math.isclose(speed, 0.0, abs_tol=1e-12):
        return 0.0, None
    direction = math.degrees(math.atan2(-float(u_ms), -float(v_ms)))
    return speed, normalize_direction(direction)


def weighted_vector_mean(
    winds: Iterable[tuple[float, float, float]],
) -> tuple[float, float | None]:
    """Average ``(speed_ms, direction_degrees, weight)`` in vector space."""
    u_total = v_total = weight_total = 0.0
    for speed, direction, weight in winds:
        if weight < 0:
            raise ValueError("wind weights must be non-negative")
        if weight == 0:
            continue
        u, v = wind_to_uv(speed, direction)
        u_total += u * weight
        v_total += v * weight
        weight_total += weight
    if weight_total == 0:
        raise ValueError("at least one positive wind weight is required")
    return uv_to_wind(u_total / weight_total, v_total / weight_total)
