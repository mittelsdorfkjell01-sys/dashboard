"""Helpers for turning a Spot into evaluation inputs (editorial + sport)."""

from __future__ import annotations

from typing import Any


def spot_editorial(spot: Any) -> dict:
    """Editorial dict for a spot, with the spot's ``facing`` folded in.

    ``facing`` (a column) drives the onshore-wind gate, but editorial may already
    carry its own; editorial wins.
    """
    ed = dict(getattr(spot, "editorial", None) or {})
    if "facing" not in ed and getattr(spot, "facing", None) is not None:
        ed["facing"] = spot.facing
    return ed


def primary_sport(spot: Any, sport: str | None = None) -> str | None:
    """Explicit sport, else the spot's first listed sport."""
    if sport:
        return sport
    sports = getattr(spot, "sports", None) or []
    return sports[0] if sports else None


def scoring_sport(sport_or_variant: str | None) -> str | None:
    """Map a sport/variant key to the sport whose scoring params apply.

    Base variants (``windsurf:fin`` / ``kitesurf:classic``) score like their
    parent sport; a bare sport maps to itself. Foil variants have **no** proven
    parameters and return ``None`` — the caller must treat that as "nicht
    ausreichend bewertet" rather than inventing thresholds.
    """
    from app.admin.constants import SPORT_FOIL_VARIANT, parent_sport

    if not sport_or_variant:
        return None
    if sport_or_variant in SPORT_FOIL_VARIANT.values():
        return None
    return parent_sport(sport_or_variant)


def variant_editorial(spot: Any, variant: str | None) -> dict:
    """Editorial for a spot, overlaid with a variant's own conditions.

    Starts from :func:`spot_editorial` (shared place data) and, when ``variant``
    names a stored block in ``spots.variant_conditions``, overrides the gate
    inputs with the variant's specifics: ``wind_directions`` →
    ``usable_wind_directions``, plus ``usable_depth_m``/``tide`` when present. So
    the gates see the variant's own wind window without any signature change.
    """
    ed = spot_editorial(spot)
    if not variant:
        return ed
    conditions = getattr(spot, "variant_conditions", None)
    block = conditions.get(variant) if isinstance(conditions, dict) else None
    if not isinstance(block, dict):
        return ed
    merged = dict(ed)
    if block.get("wind_directions"):
        merged["usable_wind_directions"] = block["wind_directions"]
    if block.get("usable_depth_m") is not None:
        merged["usable_depth_m"] = block["usable_depth_m"]
    if block.get("tide") is not None:
        merged["tide"] = block["tide"]
    return merged


def variant_is_offered(spot: Any, variant: str | None) -> bool:
    """Whether a variant is at least ``eingeschraenkt`` for this spot.

    ``unbekannt``/``ungeeignet`` (or a missing block) are never a positive
    recommendation, so a variant-scoped score must not rank them as usable.
    """
    if not variant:
        return True
    from app.admin.constants import SUITABILITY_OFFERED, variant_suitability

    return variant_suitability(
        getattr(spot, "variant_conditions", None), variant
    ) in SUITABILITY_OFFERED


def range_midpoint(editorial: dict, key: str) -> float | None:
    """Midpoint of a ``[min, max]`` editorial range (e.g. ``wind_range``,
    ``wave_height_range``), rounded to 1 decimal. ``None`` when the key is
    absent or malformed — callers must not invent a value."""
    value = editorial.get(key)
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(v, (int, float)) for v in value)
    ):
        return round((float(value[0]) + float(value[1])) / 2, 1)
    return None


def typical_figures(spot: Any) -> tuple[float | None, float | None]:
    """(typical_wind_kt, typical_wave_height_m) for a spot — exactly one of
    the two is populated, chosen by the spot's primary sport's ``sport_type``
    ("wind" sports get a wind figure, "surf" gets a wave-height figure).
    ``(None, None)`` when the sport is unknown or the matching editorial range
    isn't set. Shared by the tile list endpoints and the similar-spots brief
    so every spot-card data source agrees."""
    from app.scoring.params import SCORING_PARAMS_V1

    editorial = spot.editorial if isinstance(getattr(spot, "editorial", None), dict) else None
    if not editorial:
        return None, None
    sport = primary_sport(spot)
    params = SCORING_PARAMS_V1.get(sport) if sport else None
    if params is None:
        return None, None
    if params["sport_type"] == "wave":
        return None, range_midpoint(editorial, "wave_height_range")
    return range_midpoint(editorial, "wind_range"), None
