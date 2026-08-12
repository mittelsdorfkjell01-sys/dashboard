"""Bounded, explainable automatic terrain adjustment applied per model."""

from __future__ import annotations
from dataclasses import dataclass
from app.forecast.contracts import NormalizedModelValue
from app.weather.vectors import wind_to_uv


@dataclass(frozen=True)
class CorrectionComponent:
    key: str
    factor: float
    confidence: float
    reason: str


@dataclass(frozen=True)
class CorrectedValue:
    raw: NormalizedModelValue
    speed_ms: float
    u_ms: float
    v_ms: float
    components: tuple[CorrectionComponent, ...]
    uncertainty_ms: float
    version: str = "swd-physics-v1"


def _sector(profile: dict, direction: float):
    sectors = profile.get("sectors") or []
    if not sectors:
        return None
    index = round(direction / (360 / len(sectors))) % len(sectors)
    return sectors[index]


def apply_automatic_physics(
    raw: NormalizedModelValue,
    profile: dict | None,
    *,
    model_elevation_m: float | None = None,
) -> CorrectedValue:
    if not profile or not profile.get("corrections_enabled"):
        return CorrectedValue(raw, raw.speed_ms, raw.u_ms, raw.v_ms, (), 0.8)
    components = []
    factor = 1.0
    uncertainty = 0.4
    spot_elevation = profile.get("elevation_m")
    if spot_elevation is not None and model_elevation_m is not None:
        delta = max(-1200, min(1200, float(spot_elevation) - model_elevation_m))
        elevation_factor = max(0.92, min(1.08, 1 + delta * 0.00004))
        factor *= elevation_factor
        components.append(
            CorrectionComponent(
                "elevation",
                elevation_factor,
                0.45,
                f"spot-model elevation delta {delta:.0f} m",
            )
        )
    sector = _sector(profile, raw.direction_deg)
    if sector and sector.get("terrain_shelter") is not None:
        shelter = max(0, min(1, float(sector["terrain_shelter"])))
        shelter_factor = 1 - 0.18 * shelter
        factor *= shelter_factor
        uncertainty += 0.25 * shelter
        components.append(
            CorrectionComponent(
                "terrain_shelter",
                shelter_factor,
                0.55,
                "bounded upwind terrain horizon",
            )
        )
    # Automatic total adjustment remains deliberately conservative until
    # measurement validation; thermal/nozzle modules do not alter the value.
    factor = max(0.78, min(1.18, factor))
    speed = max(0, raw.speed_ms * factor)
    u, v = wind_to_uv(speed, raw.direction_deg)
    return CorrectedValue(raw, speed, u, v, tuple(components), min(2, uncertainty))
