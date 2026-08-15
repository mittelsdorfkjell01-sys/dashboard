"""Shared admin constants.

Also the **single source of truth** for the controlled category vocabularies
(``LEVELS``, ``WATER_CHARACTERS``, ``STYLES``, ``FACILITY_KINDS``). Enum keys are
English/machine-readable and stable; German display labels live only in the
frontend (``frontend/src/lib/labels.ts``). Anything that needs to validate one of
these axes imports from here rather than keeping its own copy.
"""

from __future__ import annotations

from typing import Iterable

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
