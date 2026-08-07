"""Media work list: which spots and regions still need attention.

"Spots ohne Hero" is a content roadmap, not an error report — it is the list an
operator works through, so it lives next to the filters for the other three
image problems rather than in a separate corner of the admin.

The four filters answer four different questions:
  no_hero    — nothing to show at all (includes seed placeholders, which look
               like an image but are not one)
  unverified — the photo may not show this place; found by name, not coordinates
  duplicate  — the same provider photo is used on more than one entry
  dead       — the source URL stopped answering when it was last checked
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.media.image_object import is_placeholder
from app.models import MediaUsage, Region, Spot

MEDIA_FILTERS = ("no_hero", "unverified", "duplicate", "dead")


def _has_no_hero(image: Any) -> bool:
    if not isinstance(image, dict) or not image.get("url"):
        return True
    # A seed placeholder is the absence of an image wearing an image's clothes.
    return is_placeholder(image)


def duplicate_photo_keys(db: Session) -> set[tuple[str, str]]:
    """(provider, external_id) pairs used by more than one entity.

    One query for the whole page rather than a lookup per row — the picker
    already pays for this index, the work list should not pay again.
    """
    rows = db.execute(
        select(MediaUsage.provider, MediaUsage.external_id)
        .where(MediaUsage.external_id.isnot(None))
        .group_by(MediaUsage.provider, MediaUsage.external_id)
        .having(func.count(func.distinct(MediaUsage.entity_id)) > 1)
    ).all()
    return {(provider, external_id) for provider, external_id in rows}


def image_flags(image: Any, duplicates: set[tuple[str, str]]) -> dict[str, bool]:
    """The four media states of one image object."""
    no_hero = _has_no_hero(image)
    if not isinstance(image, dict):
        image = {}
    key = (image.get("provider"), image.get("external_id"))
    return {
        "no_hero": no_hero,
        # An image nobody has yet is not "unverified" — it is simply missing,
        # and reporting both would double-count the same spot in two filters.
        "unverified": not no_hero and not image.get("geo_verified"),
        "duplicate": bool(key[1]) and key in duplicates,
        "dead": image.get("source_status") == "dead",
    }


def matches(flags: dict[str, bool], media_filter: str | None) -> bool:
    if not media_filter:
        return True
    return bool(flags.get(media_filter))


def region_worklist(db: Session, *, media_filter: str | None = None) -> list[dict]:
    """Regions with their media flags — the same four states as spots."""
    duplicates = duplicate_photo_keys(db)
    out = []
    for region in db.scalars(select(Region).order_by(Region.name.asc())).all():
        flags = image_flags(region.image, duplicates)
        if not matches(flags, media_filter):
            continue
        out.append(
            {
                "id": str(region.id),
                "name": region.name,
                "country": region.country,
                "flags": flags,
            }
        )
    return out


def media_summary(db: Session) -> dict[str, int]:
    """Counts for the admin overview — how much image work is outstanding."""
    duplicates = duplicate_photo_keys(db)
    counts = {key: 0 for key in MEDIA_FILTERS}
    for image in db.scalars(select(Spot.image)).all():
        for key, value in image_flags(image, duplicates).items():
            if value:
                counts[key] += 1
    return counts
