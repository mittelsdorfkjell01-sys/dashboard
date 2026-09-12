"""Resolve optional profile data without making it a weather availability gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


QUALITY_TIERS = {"coordinates", "coastal", "extended", "advanced"}
# Legacy storage shares this relationship with the separate 16-bin wind-
# climatology direction selection. Those neutral rows are not forecast physics.
WIND_CLIMATOLOGY_V3_NOTE = "Windklimatologie V3"


def is_forecast_sector(sector) -> bool:
    return getattr(sector, "note", None) != WIND_CLIMATOLOGY_V3_NOTE


@dataclass(frozen=True)
class ResolvedWeatherProfile:
    active: bool = True
    quality_tier: str = "coastal"
    coastal_normal_deg: float | None = None
    reviewed_at: datetime | None = None
    sectors: tuple = field(default_factory=tuple)


def resolve_weather_profile(profile) -> ResolvedWeatherProfile | None:
    """Return safe local metadata or the non-persistent ``coordinates`` fallback.

    ``None`` is the canonical coordinates configuration. Incomplete/inactive
    profiles do not block weather. Enabled sector rows are already the explicit
    activation boundary, so they are preserved even when optional coastal
    metadata is incomplete. Disabled candidate rows never reach serving.

    Without an enabled sector, the previous conservative behaviour remains:
    complete profiles contribute only their coastal normal at the coastal tier,
    while coordinates/incomplete profiles resolve to ``None``.
    """
    if profile is None or not getattr(profile, "active", False):
        return None

    sectors = tuple(
        sector
        for sector in (getattr(profile, "sectors", None) or ())
        if getattr(sector, "enabled", False) and is_forecast_sector(sector)
    )
    raw_tier = getattr(profile, "quality_tier", "coordinates")
    quality_tier = raw_tier if raw_tier in QUALITY_TIERS else "coordinates"
    coastal_normal = getattr(profile, "coastal_normal_deg", None)

    # Activation is the governance gate for sector correction. It is independent
    # of timezone/elevation/coastal metadata, none of which is required to apply
    # an omnidirectional GWA factor.
    if sectors:
        return ResolvedWeatherProfile(
            quality_tier=quality_tier,
            coastal_normal_deg=(
                float(coastal_normal) if coastal_normal is not None else None
            ),
            reviewed_at=getattr(profile, "reviewed_at", None),
            sectors=sectors,
        )

    if quality_tier == "coordinates":
        return None
    required = (
        getattr(profile, "timezone", None),
        getattr(profile, "elevation_m", None),
        coastal_normal,
    )
    if any(value is None or value == "" for value in required):
        return None
    return ResolvedWeatherProfile(
        quality_tier="coastal",
        coastal_normal_deg=float(coastal_normal),
        reviewed_at=getattr(profile, "reviewed_at", None),
    )
