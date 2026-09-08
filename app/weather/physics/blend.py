"""Per-model-family blend for GWA sector factors (overcorrection valve).

The sector factor is derived from a ~31 km reference (GWA/ERA5). High-resolution
members (AROME ~1.5 km, ICON-D2 ~2 km) already resolve some terrain, so applying
the full factor to them overcorrects. ``blend[family] in [0, 1]`` scales how much
of the factor a family receives: the effective factor is
``1 + blend * (speed_factor - 1)``. Default is 1.0 (full factor, unchanged
behaviour); WP1's per-family verification can dial a family down without a code
change (settings.wind_sector_blend, keyed by ModelFamily value).
"""

from __future__ import annotations

from app.weather.physics.limits import clamp


def family_blend(family, overrides: dict[str, float] | None = None) -> float:
    """Blend coefficient for a model family, clamped to [0, 1]; default 1.0."""
    value = (overrides or {}).get(str(family), 1.0)
    try:
        return clamp(float(value), 0.0, 1.0)
    except (TypeError, ValueError):
        return 1.0


def blended_factor(speed_factor: float, blend: float) -> float:
    """Scale a sector factor towards neutral by ``blend`` (1.0 = full factor)."""
    return 1.0 + blend * (float(speed_factor) - 1.0)
