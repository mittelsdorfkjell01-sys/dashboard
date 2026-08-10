"""Non-operative physics readiness diagnostics for every spot.

No multiplier is produced here. The output makes missing geospatial inputs
explicit so future physics cannot silently invent local effects.
"""

from __future__ import annotations


def physics_shadow(spot, profile) -> dict:
    water_types = set(getattr(spot, "water_type", None) or [])
    raw = getattr(spot, "weather_profile", None)
    coastal_normal = getattr(raw, "coastal_normal_deg", None)
    elevation = getattr(raw, "elevation_m", None)
    roughness = getattr(raw, "roughness_length_m", None)
    land_ref = getattr(raw, "land_reference", None)
    water_ref = getattr(raw, "water_reference", None)
    grid_preference = "sea" if water_types.intersection({"ocean", "sea"}) else "nearest"
    missing = []
    for name, value in (
        ("coastal_normal_deg", coastal_normal), ("elevation_m", elevation),
        ("roughness_length_m", roughness), ("land_reference", land_ref), ("water_reference", water_ref),
    ):
        if value is None:
            missing.append(name)
    return {
        "mode": "shadow",
        "active_correction": False,
        "grid_preference": grid_preference,
        "metadata_quality": "reviewed" if profile is not None and not missing else "partial" if len(missing) < 5 else "coordinates",
        "available": {
            "coastal_normal_deg": coastal_normal,
            "elevation_m": elevation,
            "roughness_length_m": roughness,
            "land_reference": land_ref,
            "water_reference": water_ref,
        },
        "missing": missing,
        "planned_features": ["directional_fetch", "terrain_shelter", "roughness_transfer", "thermal_effect"],
    }
