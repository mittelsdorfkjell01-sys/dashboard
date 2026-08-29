"""Gallery management for spots and regions: order, remove, promote to hero.

The rows live in ``spot_images`` (entity-generic since migration 0027), so a
region gallery and a spot gallery are the same code with a different column.

Ordering is explicit and manual. ``position`` NULL sorts last and falls back to
newest-first, which is what every existing row does until an operator arranges
one — so introducing the column changed nothing that was already on screen.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.media.image_object import build_image, is_placeholder, upgrade_legacy
from app.media.lifecycle import mark_row_retired, purge_if_unreferenced
from app.models import Region, Spot, SpotImage

VISIBLE = ("approved", "published_hero", "pending")


class GalleryError(ValueError):
    """Rejected gallery operation — maps to 422 with the operator-facing text."""


def _entity_column(entity_type: str):
    if entity_type == "spot":
        return SpotImage.spot_id
    if entity_type == "region":
        return SpotImage.region_id
    raise GalleryError(f"Unbekannter Typ: {entity_type}")


def _load_entity(db: Session, entity_type: str, entity_id) -> Any:
    model = Spot if entity_type == "spot" else Region
    entity = db.scalar(
        select(model).where(model.id == entity_id).with_for_update()
    )
    if entity is None:
        raise LookupError(f"unknown {entity_type} {entity_id}")
    return entity


def list_gallery(db: Session, entity_type: str, entity_id) -> list[SpotImage]:
    """Gallery rows in operator order: arranged first, then newest."""
    column = _entity_column(entity_type)
    return list(
        db.scalars(
            select(SpotImage)
            .where(column == entity_id, SpotImage.status.in_(VISIBLE))
            .order_by(
                SpotImage.position.asc().nullslast(),
                SpotImage.created_at.desc(),
            )
        ).all()
    )


def as_payload(row: SpotImage) -> dict:
    return {
        "id": str(row.id),
        "url": row.url,
        "kind": row.kind,
        "status": row.status,
        "position": row.position,
        "width": row.width,
        "height": row.height,
        "source": row.source,
        "provider": row.provider,
        "external_id": row.external_id,
        "delivery": row.delivery,
        "credit": row.credit,
        "credit_url": row.credit_url,
        "license_name": row.license_name,
        "license_url": row.license_url,
        "source_url": row.source_url,
        "geo_verified": row.geo_verified,
        "created_at": row.created_at.isoformat(),
    }


def reorder(db: Session, entity_type: str, entity_id, image_ids: list[uuid.UUID]) -> list[SpotImage]:
    """Apply a drag-and-drop order.

    Only ids that actually belong to this entity are accepted — a mis-sent id
    must not silently reposition somebody else's photo. Anything the client
    left out keeps its relative place after the listed ones.
    """
    rows = list_gallery(db, entity_type, entity_id)
    by_id = {row.id: row for row in rows}
    unknown = [str(i) for i in image_ids if i not in by_id]
    if unknown:
        raise GalleryError(f"Unbekannte Bild-IDs: {', '.join(unknown)}")

    for index, image_id in enumerate(image_ids):
        by_id[image_id].position = index + 1
    remaining = [row for row in rows if row.id not in set(image_ids)]
    for offset, row in enumerate(remaining):
        row.position = len(image_ids) + offset + 1
    db.commit()
    return list_gallery(db, entity_type, entity_id)


def remove(db: Session, image_id) -> None:
    """Take a gallery image out of circulation.

    Marked ``removed`` rather than deleted: community photos carry a consent
    record and a report history, and destroying that on a layout decision would
    lose the provenance this whole feature exists to keep.
    """
    row = db.get(SpotImage, image_id)
    if row is None:
        raise LookupError(f"unknown image {image_id}")
    url = row.url
    mark_row_retired(db, row, status="removed")
    db.commit()
    purge_if_unreferenced(db, url, exclude_image_id=row.id)


def promote_to_hero(db: Session, image_id) -> dict:
    """Make a gallery image the entity's hero, demoting the current one.

    The swap is symmetric with the adopt path: the outgoing hero lands in the
    gallery instead of being discarded.
    """
    row = db.get(SpotImage, image_id)
    if row is None:
        raise LookupError(f"unknown image {image_id}")
    if row.status not in VISIBLE:
        raise GalleryError(f"Bild kann aus Status {row.status} nicht veröffentlicht werden.")
    entity_type = "spot" if row.spot_id else "region"
    entity_id = row.spot_id or row.region_id
    entity = _load_entity(db, entity_type, entity_id)

    if not row.credit or not row.credit.strip():
        # Attribution is mandatory for a hero and the builder would refuse the
        # write anyway; failing here gives the operator a usable message.
        raise GalleryError(
            "Diesem Bild fehlt der Bildnachweis — bitte zuerst ergänzen."
        )

    image = build_image(
        url=row.url,
        source=row.source or (row.provider or "unknown"),
        license=row.license_name or row.license_version or "unbekannt",
        license_url=row.license_url,
        credit=row.credit,
        credit_url=row.credit_url,
        provider=row.provider if row.provider else "unknown",
        external_id=row.external_id,
        source_page=row.source_url,
        retrieved_at=row.retrieved_at.isoformat() if row.retrieved_at else None,
        delivery=row.delivery,
        width=row.width,
        height=row.height,
        geo_verified=row.geo_verified,
        role="hero",
    )

    from app.media.adopt import _gallery_row, _record_usage

    previous = upgrade_legacy(entity.image)
    if (
        previous
        and previous.get("url")
        and previous["url"] != image["url"]
        and not is_placeholder(previous)
    ):
        _gallery_row(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            image=previous,
        )
        if previous.get("provider") and previous.get("external_id"):
            _record_usage(
                db,
                provider=previous["provider"],
                external_id=previous["external_id"],
                entity_type=entity_type,
                entity_id=entity_id,
                role="gallery",
            )

    # A single entity has exactly one current hero row. This also repairs
    # legacy duplicate states the next time an operator promotes an image.
    column = _entity_column(entity_type)
    next_position = max(
        (item.position or 0) for item in list_gallery(db, entity_type, entity_id)
    ) + 1
    for other in db.scalars(
        select(SpotImage).where(
            column == entity_id,
            SpotImage.status == "published_hero",
            SpotImage.id != row.id,
        )
    ).all():
        other.status = "approved"
        if other.position is None:
            other.position = next_position
            next_position += 1

    entity.image = image
    row.status = "published_hero"
    row.position = None

    if row.provider and row.external_id:
        _record_usage(
            db,
            provider=row.provider,
            external_id=row.external_id,
            entity_type=entity_type,
            entity_id=entity_id,
            role="hero",
        )
    db.commit()
    return {"entity_type": entity_type, "entity_id": str(entity_id), "image": image}
