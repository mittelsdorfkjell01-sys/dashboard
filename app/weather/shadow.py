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
        "active_correction": bool(
            profile is not None
            and getattr(profile, "active", False)
            and any(
                getattr(sector, "enabled", False)
                and (
                    abs(float(getattr(sector, "speed_factor", 1.0)) - 1.0) > 1e-9
                    or abs(float(getattr(sector, "direction_offset_deg", 0.0))) > 1e-9
                )
                for sector in (getattr(profile, "sectors", None) or ())
            )
        ),
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
