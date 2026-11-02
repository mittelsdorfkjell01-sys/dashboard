"""Deterministic content-review warnings that do not invent domain facts."""

from __future__ import annotations

import re
from typing import Any


BEGINNER_TERMS = re.compile(
    r"\b(beginner|beginners|einsteiger\w*|anf[aä]nger\w*)\b",
    re.IGNORECASE,
)

# This signature was confirmed against the public record on 2026-10-29.  The
# audit flags the bad copy but deliberately does not manufacture replacement
# content.  An editor must either correct the sourced text or take it offline.
KNOWN_DESCRIPTION_CONFLICTS: dict[str, tuple[str, ...]] = {
    "peniche-supertubos": ("ria formosa", "tavira", "monte gordo"),
}


def content_consistency_warnings(spot: Any) -> list[str]:
    editorial = getattr(spot, "editorial", None) if not isinstance(spot, dict) else spot.get("editorial")
    editorial = editorial if isinstance(editorial, dict) else {}
    description = str(editorial.get("description") or "")
    levels = set(
        (getattr(spot, "level", None) if not isinstance(spot, dict) else spot.get("level"))
        or []
    )
    slug = str(
        (getattr(spot, "slug", None) if not isinstance(spot, dict) else spot.get("slug"))
        or ""
    )
    warnings: list[str] = []
    if BEGINNER_TERMS.search(description) and "beginner" not in levels:
        warnings.append("content.level.beginner_mentioned_but_not_structured")
    lowered = description.casefold()
    if any(term in lowered for term in KNOWN_DESCRIPTION_CONFLICTS.get(slug, ())):
        warnings.append("content.description.known_geography_conflict")
    return warnings
