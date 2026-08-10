from __future__ import annotations

from dataclasses import dataclass

from app.weather.physics.coast import coastal_class
from app.weather.physics.limits import clamp_combined_factor, clamp_direction_change
from app.weather.physics.manual import select_sector
from app.weather.vectors import normalize_direction


@dataclass(frozen=True)
class AppliedWind:
    speed_ms: float
    direction_deg: float
    quality_tier: str
    coastal_classification: str | None
    correction_limited: bool


def apply_local_physics(speed_ms: float, direction_deg: float, profile) -> AppliedWind:
    """Apply only reviewed corrections; missing metadata always degrades safely."""
    if profile is None or not profile.active:
        return AppliedWind(speed_ms, normalize_direction(direction_deg), "coordinates", None, False)

    tier = profile.quality_tier
    classification = (
        coastal_class(direction_deg, profile.coastal_normal_deg)
        if profile.coastal_normal_deg is not None
        else None
    )
    # Advanced/local speed corrections stay disabled until measurement-backed
    # formulas and factors have been validated. Profiles currently improve
    # classification only and can never activate sector multipliers.
    advanced = False
    factor = 1.0
    offset = 0.0
    limited_factor = clamp_combined_factor(factor, advanced)
    limited_offset = clamp_direction_change(offset, advanced)
    return AppliedWind(
        speed_ms=max(0.0, speed_ms * limited_factor),
        direction_deg=normalize_direction(direction_deg + limited_offset),
        quality_tier=tier if classification is not None or tier == "coordinates" else "coordinates",
        coastal_classification=classification,
        correction_limited=limited_factor != factor or limited_offset != offset,
    )
