"""Resolve optional profile data without making it a weather availability gate."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolvedWeatherProfile:
    active: bool = True
    quality_tier: str = "coastal"
    coastal_normal_deg: float | None = None
    reviewed_at: None = None
    sectors: tuple = field(default_factory=tuple)


def resolve_weather_profile(profile) -> ResolvedWeatherProfile | None:
    """Return safe local metadata or the non-persistent ``coordinates`` fallback.

    ``None`` is the canonical coordinates configuration. Incomplete/inactive
    profiles do not block weather and do not leak partially trusted corrections.
    Advanced physics remains disabled; a complete advanced record therefore
    contributes only its reviewed coastal normal at the conservative coast tier.
    """
    if profile is None or not getattr(profile, "active", False):
        return None
    if getattr(profile, "quality_tier", "coordinates") == "coordinates":
        return None
    required = (
        getattr(profile, "timezone", None),
        getattr(profile, "elevation_m", None),
        getattr(profile, "coastal_normal_deg", None),
    )
    if any(value is None or value == "" for value in required):
        return None
    return ResolvedWeatherProfile(coastal_normal_deg=float(profile.coastal_normal_deg))
