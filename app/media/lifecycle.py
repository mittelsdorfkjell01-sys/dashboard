"""Consistency and physical cleanup for catalogue image references.

Database rows retain consent, attribution and moderation history after removal;
hosted bytes are deleted once no active hero/gallery reference needs them.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Region, Spot, SpotImage

logger = logging.getLogger(__name__)

ACTIVE_ROW_STATUSES = ("pending", "approved", "published_hero")


def entity_for_row(db: Session, row: SpotImage):
    model = Spot if row.spot_id is not None else Region
    entity_id = row.spot_id or row.region_id
    return db.get(model, entity_id)


def mark_row_retired(db: Session, row: SpotImage, *, status: str) -> None:
    """Retire a row and clear a matching current hero in the same transaction."""
    if status not in ("rejected", "removed"):
        raise ValueError(f"unsupported retired image status: {status}")
    entity = entity_for_row(db, row)
    current = entity.image if entity is not None and isinstance(entity.image, dict) else None
    if current and current.get("url") == row.url:
        entity.image = None
    row.status = status
    row.position = None


def demote_published_hero_rows(
    db: Session, entity_type: str, entity_id, *, keep_url: str | None
) -> None:
    """Move stale published-hero rows back into the ordered gallery."""
    column = SpotImage.spot_id if entity_type == "spot" else SpotImage.region_id
    rows = list(
        db.scalars(
            select(SpotImage).where(
                column == entity_id,
                SpotImage.status == "published_hero",
                SpotImage.url != keep_url,
            )
        ).all()
    )
    if not rows:
        return
    highest = db.scalar(
        select(func.max(SpotImage.position)).where(column == entity_id)
    )
    next_position = int(highest or 0) + 1
    for row in rows:
        row.status = "approved"
        if row.position is None:
            row.position = next_position
            next_position += 1


def image_url_is_referenced(db: Session, url: str, *, exclude_image_id=None) -> bool:
    """Whether a URL is still used by a live gallery row or current hero."""
    from app.media.storage import canonical_image_url, responsive_variant_urls

    canonical_url = canonical_image_url(url)
    reference_urls = [canonical_url, *responsive_variant_urls(canonical_url)]
    query = select(SpotImage.id).where(
        SpotImage.url.in_(reference_urls),
        SpotImage.status.in_(ACTIVE_ROW_STATUSES),
    )
    if exclude_image_id is not None:
        query = query.where(SpotImage.id != exclude_image_id)
    if db.scalar(query.limit(1)) is not None:
        return True
    for model in (Spot, Region):
        if db.scalar(
            select(model.id)
            .where(model.image["url"].astext.in_(reference_urls))
            .limit(1)
        ) is not None:
            return True
    return False


def active_image_urls(db: Session) -> set[str]:
    """Snapshot all live media references for provider-side orphan audits."""
    from app.media.storage import canonical_image_url

    urls = {
        canonical_image_url(url)
        for url in db.scalars(
            select(SpotImage.url).where(
                SpotImage.status.in_(ACTIVE_ROW_STATUSES)
            )
        ).all()
    }
    raw_hero_urls = set(
        db.scalars(
            select(Spot.image["url"].astext).where(Spot.image.is_not(None))
        ).all()
    )
    raw_hero_urls.update(
        db.scalars(
            select(Region.image["url"].astext).where(Region.image.is_not(None))
        ).all()
    )
    urls.update(
        canonical_image_url(url)
        for url in raw_hero_urls
        if isinstance(url, str) and url
    )
    return urls


def purge_if_unreferenced(db: Session, url: str | None, *, exclude_image_id=None) -> bool:
    """Queue hosted bytes for a delayed, locked reference recheck and deletion."""
    if not url:
        return False
    try:
        from app.media.storage import canonical_image_url

        canonical_url = canonical_image_url(url)
        if image_url_is_referenced(
            db, canonical_url, exclude_image_id=exclude_image_id
        ):
            return False
        from app.media.gc import schedule_media_gc

        return schedule_media_gc(db, canonical_url)
    except Exception:
        # A failed reference query must fail closed: preserving an orphan is
        # cheaper than deleting bytes another row still uses. It also avoids
        # masking the original upload/commit exception in rollback paths.
        logger.exception("media reference check or cleanup failed for %s", url)
        return False
    return False


def collect_entity_urls(db: Session, entity_type: str, entity_id) -> set[str]:
    """Collect current-hero and row URLs before an entity cascade deletes them."""
    if entity_type == "spot":
        model, column = Spot, SpotImage.spot_id
    elif entity_type == "region":
        model, column = Region, SpotImage.region_id
    else:
        raise ValueError(f"unknown entity type: {entity_type}")
    entity = db.get(model, entity_id)
    urls = set(
        db.scalars(select(SpotImage.url).where(column == entity_id)).all()
    )
    if entity is not None and isinstance(entity.image, dict) and entity.image.get("url"):
        urls.add(entity.image["url"])
    return urls


def purge_entity_urls(db: Session, urls: set[str]) -> None:
    """Purge collected URLs after the entity deletion has committed."""
    for url in urls:
        purge_if_unreferenced(db, url)
