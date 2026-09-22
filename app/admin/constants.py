"""Shared admin constants.

Also the **single source of truth** for the controlled category vocabularies
(``LEVELS``, ``WATER_CHARACTERS``, ``STYLES``, ``FACILITY_KINDS``). Enum keys are
English/machine-readable and stable; German display labels live only in the
frontend (``frontend/src/lib/labels.ts``). Anything that needs to validate one of
these axes imports from here rather than keeping its own copy.
"""

from __future__ import annotations

from typing import Any, Iterable

# Sentinel a curator sets when a field genuinely does not apply; it counts as
# *fulfilled* for readiness (an explicit "not applicable", not a missing value).
NA = "n/a"

# Spot lifecycle. The column keeps the project's English vocabulary; "entwurf" and
# "live" in the prompt map to these.
STATUS_DRAFT = "draft"       # entwurf
STATUS_LIVE = "published"    # live
STATUS_ARCHIVED = "archived"


# --- controlled category vocabularies (single source of truth) -------------

# Rider level (ordered — low → high; ``similarity.character`` relies on order).
LEVELS: tuple[str, ...] = ("beginner", "advanced", "expert", "competition")

# Seabed / launch-ground composition. ``mixed`` is retained for historical
# records that did not identify the concrete components; it is mutually
# exclusive with concrete values when writing new data.
BOTTOM_TYPES: tuple[str, ...] = ("sand", "rock", "reef", "mixed")

# Water character ("Wasserart") — distinct from ``water_type`` (ocean/sea/lake).
WATER_CHARACTERS: tuple[str, ...] = (
    "flach", "chop", "welle_klein", "welle_gross", "tiefes_wasser",
)

# Water type ("Wassertyp") — the body of water. Previously a free-text column;
# now a controlled multi-select so the admin chips and validation agree.
WATER_TYPES: tuple[str, ...] = ("ocean", "sea", "lake", "lagoon")

# Riding style ("Fahrstil") — multi-select.
STYLES: tuple[str, ...] = (
    "freeride",
    "freestyle",
    "big_air",
    "wave_riding",
    "wavekite",
)

# Facility kinds — exactly these five.
FACILITY_KINDS: tuple[str, ...] = ("parking", "shower", "food", "camping", "school")

# Sports offered by a spot / attached to a rating. Wavekite is a riding style,
# derived from a spot supporting both kitesurfing and surfing.
SPORTS: tuple[str, ...] = ("kitesurf", "windsurf", "wing", "surf")

# --- sport variants (Windfoil / Kitefoil) ----------------------------------
# A *variant* is a selectable discipline within a parent sport, keyed
# ``"<sport>:<slug>"``. Only wind- and kitesurfing split; ``wing`` stays its own
# sport (Wingfoilen) and ``surf`` is deliberately not given a foil variant
# (Surf-Foil is not silently folded into another sport). The base variant
# (``:fin`` / ``:classic``) carries the historical, proven suitability; the foil
# variant starts ``unbekannt`` until an editor confirms it.
SPORT_VARIANTS: dict[str, tuple[str, ...]] = {
    "windsurf": ("windsurf:fin", "windsurf:foil"),
    "kitesurf": ("kitesurf:classic", "kitesurf:foil"),
}
# The proven base variant a sport's existing listing implies (migration seed).
SPORT_BASE_VARIANT: dict[str, str] = {
    "windsurf": "windsurf:fin",
    "kitesurf": "kitesurf:classic",
}
# The foil variant per sport — the one that must never inherit suitability.
SPORT_FOIL_VARIANT: dict[str, str] = {
    "windsurf": "windsurf:foil",
    "kitesurf": "kitesurf:foil",
}
VARIANT_KEYS: tuple[str, ...] = tuple(
    key for keys in SPORT_VARIANTS.values() for key in keys
)

# Per-spot, per-variant suitability. A missing entry means ``unbekannt`` (never
# a positive recommendation); ``unbekannt`` is stored explicitly only when an
# editor wants to record "looked at, still unknown".
SUITABILITY: tuple[str, ...] = ("geeignet", "eingeschraenkt", "ungeeignet", "unbekannt")
# Suitability values that make a variant show up as an offered/searchable option.
SUITABILITY_OFFERED: tuple[str, ...] = ("geeignet", "eingeschraenkt")

# Free-text fields inside a variant-condition block (stripped, ``n/a`` allowed).
_VARIANT_TEXT_FIELDS: tuple[str, ...] = (
    "tide", "entry", "launch_area", "hazards", "local_rules", "notes",
)

# --- UGC / moderation vocabularies (Sprint C) ------------------------------
# Rating/tip visibility after post-moderation.
MODERATION_STATUS: tuple[str, ...] = ("pending", "published", "rejected", "hidden")
# User image role and its lifecycle.
IMAGE_KIND: tuple[str, ...] = ("gallery", "hero_candidate")
IMAGE_STATUS: tuple[str, ...] = (
    "pending", "approved", "published_hero", "rejected", "removed",
)
# Why a user reported an image.
REPORT_REASON: tuple[str, ...] = ("copyright", "inappropriate", "wrong_spot", "other")
# New-spot proposal lifecycle.
SUBMISSION_STATUS: tuple[str, ...] = ("pending", "approved", "rejected", "merged")
# Images visible in the public gallery.
VISIBLE_IMAGE_STATUS: tuple[str, ...] = ("approved", "published_hero")


def is_na(value) -> bool:
    return isinstance(value, str) and value.strip().lower() == NA


def validate_sport(value: str) -> str:
    """A single sport key. Else ``ValueError``."""
    if value not in SPORTS:
        raise ValueError(f"invalid sport {value!r}; allowed: {list(SPORTS)}")
    return value


def validate_sports(values: Iterable[str] | None) -> list[str]:
    """Normalise a list of real sports (Wavekite is deliberately not one)."""
    return _validate_multi(values, SPORTS, "sports")


def validate_skill_level(value: str) -> str:
    """A single skill level (beginner, advanced or expert). Else ``ValueError``."""
    if value not in LEVELS:
        raise ValueError(f"invalid skill_level {value!r}; allowed: {list(LEVELS)}")
    return value


# --- enum validation -------------------------------------------------------

def validate_level(value: str | None) -> str | None:
    """A single ``level`` key, ``"n/a"``, or ``None`` (unknown). Else ``ValueError``."""
    if value is None or is_na(value):
        return value
    if value not in LEVELS:
        raise ValueError(f"invalid level {value!r}; allowed: {list(LEVELS)}")
    return value


def validate_water_character(value: str | None) -> str | None:
    """A single ``water_character`` key, ``"n/a"``, or ``None``. Else ``ValueError``."""
    if value is None or is_na(value):
        return value
    if value not in WATER_CHARACTERS:
        raise ValueError(
            f"invalid water_character {value!r}; allowed: {list(WATER_CHARACTERS)}"
        )
    return value


def _validate_multi(
    values: Iterable[str] | None, vocab: tuple[str, ...], axis: str
) -> list[str]:
    """Normalise a controlled multi-select: unique, order-preserved, all valid
    keys (the ``n/a`` sentinel is allowed as an explicit "not applicable")."""
    if not values:
        return []
    if isinstance(values, str):
        raise ValueError(f"{axis} must be a list of keys, not a string")
    out: list[str] = []
    for v in values:
        if not is_na(v) and v not in vocab:
            raise ValueError(f"invalid {axis} {v!r}; allowed: {list(vocab)}")
        if v not in out:
            out.append(v)
    return out


def validate_styles(values: Iterable[str] | None) -> list[str]:
    """Normalise a ``style`` multi-select: unique, order-preserved, all valid keys."""
    return _validate_multi(values, STYLES, "style")


def synchronize_wavekite_style(
    sports: Iterable[str] | None, styles: Iterable[str] | None
) -> tuple[list[str], list[str]]:
    """Keep the derived Wavekite style in lockstep with kitesurf + surf."""
    clean_sports = validate_sports(sports)
    clean_styles = [style for style in validate_styles(styles) if style != "wavekite"]
    if "kitesurf" in clean_sports and "surf" in clean_sports:
        clean_styles.append("wavekite")
    return clean_sports, clean_styles


def validate_levels(values: Iterable[str] | None) -> list[str]:
    """Normalise a ``level`` multi-select (three levels, or ``n/a``)."""
    return _validate_multi(values, LEVELS, "level")


def validate_bottom_types(values: Iterable[str] | None) -> list[str]:
    """Normalise the controlled ``bottom_type`` multi-select."""
    cleaned = _validate_multi(values, BOTTOM_TYPES, "bottom_type")
    if "mixed" in cleaned and len(cleaned) > 1:
        raise ValueError("bottom_type 'mixed' cannot be combined with concrete values")
    return cleaned


def validate_water_characters(values: Iterable[str] | None) -> list[str]:
    """Normalise a ``water_character`` multi-select."""
    return _validate_multi(values, WATER_CHARACTERS, "water_character")


def validate_water_types(values: Iterable[str] | None) -> list[str]:
    """Normalise a ``water_type`` multi-select (ocean/sea/lake/lagoon, or ``n/a``)."""
    return _validate_multi(values, WATER_TYPES, "water_type")


# --- sport-variant helpers -------------------------------------------------

def parent_sport(variant_key: str) -> str:
    """The parent sport of a variant key (``"windsurf:foil"`` -> ``"windsurf"``).

    A bare sport key is returned unchanged, so callers can treat sports and
    variants uniformly.
    """
    return variant_key.split(":", 1)[0]


def variant_keys_for_sports(sports: Iterable[str] | None) -> list[str]:
    """Variant keys selectable given a spot's sports (order-preserved)."""
    out: list[str] = []
    for sport in sports or []:
        for key in SPORT_VARIANTS.get(sport, ()):  # type: ignore[arg-type]
            if key not in out:
                out.append(key)
    return out


def _validate_wind_directions(value: Any) -> list[list[float]]:
    """Validate a list of ``[from, to]`` degree windows (0..360)."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("wind_directions must be a list of [from, to] pairs")
    windows: list[list[float]] = []
    for pair in value:
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or not all(isinstance(v, (int, float)) for v in pair)
        ):
            raise ValueError("each wind direction window must be a [from, to] pair")
        a, b = float(pair[0]), float(pair[1])
        if not (0 <= a <= 360 and 0 <= b <= 360):
            raise ValueError("wind direction degrees must be within 0..360")
        windows.append([a, b])
    return windows


def _validate_variant_block(key: str, spec: Any) -> dict:
    """Validate one variant-condition block. See :data:`SPORT_VARIANTS`."""
    if not isinstance(spec, dict):
        raise ValueError(f"variant {key!r} must be an object")
    out: dict[str, Any] = {}
    suitability = spec.get("suitability")
    if suitability is not None:
        if suitability not in SUITABILITY:
            raise ValueError(
                f"invalid suitability {suitability!r} for {key!r}; "
                f"allowed: {list(SUITABILITY)}"
            )
        out["suitability"] = suitability
    if "wind_directions" in spec:
        windows = _validate_wind_directions(spec.get("wind_directions"))
        if windows:
            out["wind_directions"] = windows
    depth = spec.get("usable_depth_m")
    if depth is not None and not is_na(depth):
        if not isinstance(depth, (int, float)) or depth < 0:
            raise ValueError(f"usable_depth_m for {key!r} must be a non-negative number")
        out["usable_depth_m"] = float(depth)
    elif is_na(depth):
        out["usable_depth_m"] = NA
    if "level" in spec:
        out["level"] = _validate_multi(spec.get("level"), LEVELS, f"{key} level")
    if "discipline" in spec:
        out["discipline"] = _validate_multi(spec.get("discipline"), STYLES, f"{key} discipline")
    for field in _VARIANT_TEXT_FIELDS:
        if field not in spec:
            continue
        text = spec.get(field)
        if text is None:
            continue
        if not isinstance(text, str):
            raise ValueError(f"variant {key!r} field {field!r} must be a string")
        text = text.strip()
        if text:
            out[field] = text
    return out


def validate_variant_conditions(value: dict | None) -> dict | None:
    """Validate the ``variant_conditions`` JSONB blob.

    Structure is ``{variant_key: {suitability, wind_directions, usable_depth_m,
    tide, entry, launch_area, hazards, local_rules, level, discipline, notes}}``.
    Only known variant keys are allowed; a *missing* variant means ``unbekannt``
    (never a positive recommendation), so we never inject defaults. Empty blocks
    are dropped; ``None``/empty stays ``None``.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("variant_conditions must be an object")
    cleaned: dict[str, dict] = {}
    for key, spec in value.items():
        if key not in VARIANT_KEYS:
            raise ValueError(
                f"invalid variant {key!r}; allowed: {list(VARIANT_KEYS)}"
            )
        block = _validate_variant_block(key, spec)
        if block:
            cleaned[key] = block
    return cleaned or None


def variant_suitability(variant_conditions: dict | None, variant_key: str) -> str:
    """Effective suitability for a variant — the stored value, else ``unbekannt``."""
    if isinstance(variant_conditions, dict):
        block = variant_conditions.get(variant_key)
        if isinstance(block, dict) and block.get("suitability") in SUITABILITY:
            return block["suitability"]
    return "unbekannt"


def offered_variants(variant_conditions: dict | None) -> list[str]:
    """Variant keys a spot actually offers (suitability geeignet/eingeschraenkt)."""
    if not isinstance(variant_conditions, dict):
        return []
    return [
        key
        for key in VARIANT_KEYS
        if variant_suitability(variant_conditions, key) in SUITABILITY_OFFERED
    ]


def variant_consistency_warnings(
    sports: Iterable[str] | None,
    variant_conditions: dict | None,
    *,
    water_character: Iterable[str] | None = None,
    level: Iterable[str] | None = None,
) -> list[str]:
    """Non-blocking editorial warnings about contradictory variant data.

    Surfaces (never blocks): a foil variant marked usable while the spot reads as
    flat/shallow with no usable depth recorded; a competition level claimed for a
    sport/variant that is not itself proven ``geeignet``.
    """
    warnings: list[str] = []
    conditions = variant_conditions if isinstance(variant_conditions, dict) else {}
    chars = set(water_character or [])
    shallow_place = bool(chars & {"flach"})
    for sport, foil_key in SPORT_FOIL_VARIANT.items():
        if sport not in set(sports or []):
            continue
        block = conditions.get(foil_key) if isinstance(conditions, dict) else None
        suit = variant_suitability(conditions, foil_key)
        if suit in SUITABILITY_OFFERED:
            depth = (block or {}).get("usable_depth_m")
            has_depth = isinstance(depth, (int, float))
            if shallow_place and not has_depth:
                warnings.append(
                    f"{foil_key}: als nutzbar markiert, aber der Ort gilt als "
                    f"Flachwasser und es ist keine nutzbare Tiefe erfasst — Foils "
                    f"brauchen mehr Tiefe als ein flacher Einstieg bietet."
                )
    # Competition status must attach to a proven discipline. If a variant claims
    # a competition level while its suitability isn't 'geeignet', flag it.
    for key, block in (conditions or {}).items():
        if not isinstance(block, dict):
            continue
        if "competition" in (block.get("level") or []) and block.get("suitability") != "geeignet":
            warnings.append(
                f"{key}: Wettkampf-Level gesetzt, aber die Eignung ist nicht "
                f"'geeignet' — Wettkampf-/Weltklasse-Status nur für belegte "
                f"Disziplinen vergeben."
            )
    return warnings


def validate_facilities(value: dict | None) -> dict | None:
    """Validate the ``facilities`` JSONB blob.

    Structure is ``{kind: {"available": bool, "note"?: str}}``. Only the five
    known kinds are allowed; a *missing* kind means "unknown" (shown as its own
    dimmed, non-strikethrough state on the spot page — distinct from
    ``available: false``, which is a demonstrable "not here"), so we never
    inject defaults. ``None``/empty stays ``None``.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("facilities must be an object")
    cleaned: dict[str, dict] = {}
    for kind, spec in value.items():
        if kind not in FACILITY_KINDS:
            raise ValueError(
                f"invalid facility {kind!r}; allowed: {list(FACILITY_KINDS)}"
            )
        if not isinstance(spec, dict) or "available" not in spec:
            raise ValueError(f"facility {kind!r} needs an 'available' boolean")
        entry: dict = {"available": bool(spec["available"])}
        note = spec.get("note")
        if note is not None:
            if not isinstance(note, str):
                raise ValueError(f"facility {kind!r} note must be a string")
            note = note.strip()
            if note:
                entry["note"] = note
        cleaned[kind] = entry
    return cleaned or None
