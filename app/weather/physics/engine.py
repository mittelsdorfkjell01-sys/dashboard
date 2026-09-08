from __future__ import annotations

import math
from dataclasses import dataclass

from app.weather.physics.blend import blended_factor
from app.weather.physics.coast import coastal_class
from app.weather.physics.limits import clamp_combined_factor, clamp_direction_change
from app.weather.physics.manual import select_sector
from app.weather.vectors import normalize_direction, uv_to_wind, wind_to_uv


@dataclass(frozen=True)
class AppliedWind:
    speed_ms: float
    direction_deg: float
    quality_tier: str
    coastal_classification: str | None
    correction_limited: bool
    # WP3/WP4: whether a non-neutral correction was actually applied, and the
    # auditable component that produced it. Trailing defaults keep the existing
    # positional neutral construction working.
    corrected: bool = False
    applied_component: dict | None = None


def _rotate_uv(u: float, v: float, offset_deg: float) -> tuple[float, float]:
    """Rotate a wind vector so its direction-from increases by ``offset_deg``."""
    if offset_deg == 0.0:
        return u, v
    radians = math.radians(offset_deg)
    cos, sin = math.cos(radians), math.sin(radians)
    return u * cos + v * sin, -u * sin + v * cos


def apply_local_physics(speed_ms: float, direction_deg: float, profile, *, blend: float = 1.0) -> AppliedWind:
    """Apply the active enabled sector correction; missing metadata degrades safely.

    Covers both the live and forecast paths (single call site per member). The
    magnitude/offset are applied in u/v space so a later direction rotation
    needs no restructuring; in phase 1 the offset is 0. ``blend`` (1.0 = full
    factor) scales the sector factor towards neutral for a member's model family
    so high-resolution members are not overcorrected. Station wind is never
    involved here.
    """
    if profile is None or not profile.active:
        return AppliedWind(speed_ms, normalize_direction(direction_deg), "coordinates", None, False)

    tier = profile.quality_tier
    classification = (
        coastal_class(direction_deg, profile.coastal_normal_deg)
        if profile.coastal_normal_deg is not None
        else None
    )
    advanced = tier == "advanced"
    sector = select_sector(direction_deg, getattr(profile, "sectors", None) or [])

    factor, offset = 1.0, 0.0
    component = None
    limited = False
    if sector is not None:
        effective = blended_factor(sector.speed_factor, blend)
        factor = clamp_combined_factor(effective, advanced)
        offset = clamp_direction_change(sector.direction_offset_deg, advanced)
        limited = factor != effective or offset != sector.direction_offset_deg
        component = {
            "component": "gwa_sector",
            "factor": round(factor, 4),
            "raw_factor": round(sector.speed_factor, 4),
            "blend": round(blend, 4),
            "offset": round(offset, 3),
            "sector": [sector.start_deg, sector.end_deg],
            "saturated": limited,
            "note": sector.note,
        }

    corrected = factor != 1.0 or offset != 0.0
    if corrected:
        u, v = wind_to_uv(speed_ms, direction_deg)
        u, v = _rotate_uv(u * factor, v * factor, offset)
        new_speed, new_direction = uv_to_wind(u, v)
        if new_direction is None:  # calm wind keeps its incoming bearing
            new_direction = normalize_direction(direction_deg)
    else:
        new_speed, new_direction = float(speed_ms), normalize_direction(direction_deg)

    return AppliedWind(
        speed_ms=max(0.0, new_speed),
        direction_deg=new_direction,
        quality_tier=tier if classification is not None or tier == "coordinates" else "coordinates",
        coastal_classification=classification,
        correction_limited=limited,
        corrected=corrected,
        applied_component=component,
    )
