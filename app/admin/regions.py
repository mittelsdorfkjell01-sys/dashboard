"""Region write workflow."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.admin.duplicates import (
    enforce_duplicates,
    find_region_duplicates,
    find_spot_duplicates,
)
from app.media.image_object import (
    CANONICAL_KEYS,
    build_image,
    normalize_focal,
    with_fields,
)
from app.names import available_slug, clean_display_name

logger = logging.getLogger(__name__)


def _point(lat: float, lon: float):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    return from_shape(Point(lon, lat), srid=4326)


def _bbox_polygon(bbox):
    """A [min_lon, min_lat, max_lon, max_lat] bbox → a closed rectangle polygon."""
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Polygon

    min_lon, min_lat, max_lon, max_lat = bbox
    ring = [
        (min_lon, min_lat), (max_lon, min_lat), (max_lon, max_lat),
        (min_lon, max_lat), (min_lon, min_lat),
    ]
    return from_shape(Polygon(ring), srid=4326)


def create_region(
    data: dict,
    *,
    db: Session,
    commit: bool = True,
    allow_duplicate: bool = False,
    actor: str | None = None,
) -> Any:
    """Create a region with optional centre + bounds and defaults template."""
    from app.models import Region

    center = None
    if data.get("lat") is not None and data.get("lon") is not None:
        center = _point(float(data["lat"]), float(data["lon"]))
    bounds = None
    bbox = data.get("bounds")
    if bbox and len(bbox) == 4:
        bounds = _bbox_polygon(bbox)
    duplicate_candidates = enforce_duplicates(
        "Region",
        find_region_duplicates(
            db,
            name=data["name"],
            country=data.get("country"),
            lat=data.get("lat"),
            lon=data.get("lon"),
            bounds=bounds,
        ),
        allow_likely=allow_duplicate,
    )
    region = Region(
        slug=available_slug(db, Region, data.get("slug") or data["name"]),
        name=clean_display_name(data["name"]),
        country=data.get("country"),
        center=center,
        bounds=bounds,
        description=data.get("description"),
        defaults=data.get("defaults") or {},
        season=data.get("season"),
        image=data.get("image"),
        status="draft",  # new regions start as draft → operator goes live
    )
    db.add(region)
    db.flush()
    if commit:
        db.commit()
        db.refresh(region)
    if duplicate_candidates:
        logger.warning(
            "region duplicate override by %s for %s against %s",
            actor,
            region.id,
            [item["id"] for item in duplicate_candidates],
        )
    return region


def assign_spot_to_region(
    spot_id, region_id, *, db: Session, allow_duplicate: bool = False
) -> Any:
    """Move a spot to a region, inheriting ``model_pref`` if unset."""
    from app.models import Region, Spot

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    from geoalchemy2.shape import to_shape

    point = to_shape(spot.location)
    enforce_duplicates(
        "Spot",
        find_spot_duplicates(
            db,
            name=spot.name,
            region_id=region.id,
            lat=float(point.y),
            lon=float(point.x),
            exclude_id=spot.id,
        ),
        allow_likely=allow_duplicate,
    )
    spot.region_id = region.id
    if not spot.model_pref and region.defaults:
        spot.model_pref = region.defaults.get("model_pref")
    db.commit()
    db.refresh(spot)
    return spot


def assign_spots_to_region(
    spot_ids, region_id, *, db: Session, allow_duplicate: bool = False
) -> int:
    """Move several spots to a region in one transaction (inheriting
    ``model_pref`` where unset). Returns the count moved. Raises LookupError if
    the region or any spot id is unknown — nothing is committed on error."""
    from sqlalchemy import select
    from app.models import Region, Spot

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    spots = db.scalars(select(Spot).where(Spot.id.in_(spot_ids))).all()
    found = {s.id for s in spots}
    missing = [sid for sid in spot_ids if sid not in found]
    if missing:
        raise LookupError(f"unknown spot {missing[0]}")
    moved = 0
    for spot in spots:
        if spot.region_id == region.id:
            continue
        from geoalchemy2.shape import to_shape

        point = to_shape(spot.location)
        enforce_duplicates(
            "Spot",
            find_spot_duplicates(
                db,
                name=spot.name,
                region_id=region.id,
                lat=float(point.y),
                lon=float(point.x),
                exclude_id=spot.id,
            ),
            allow_likely=allow_duplicate,
        )
        spot.region_id = region.id
        if not spot.model_pref and region.defaults:
            spot.model_pref = region.defaults.get("model_pref")
        moved += 1
    db.commit()
    return moved


def update_region_defaults(region_id, defaults: dict, *, db: Session) -> Any:
    """Merge into ``regions.defaults`` (the spot-creation template)."""
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    merged = dict(region.defaults or {})
    merged.update(defaults or {})
    region.defaults = merged
    db.commit()
    db.refresh(region)
    return region


def recompute_best_months(region_id, *, db: Session) -> Any:
    """"Berechnen"-Modus: derive best_months from the region's spots'
    climatology and store them with ``season.mode = 'auto'``."""
    from app.models import Region
    from app.scoring.region import compute_best_months

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    months = compute_best_months(list(region.spots), db=db)
    season = dict(region.season or {})
    season["best_months"] = months
    season["mode"] = "auto"
    region.season = season
    db.commit()
    db.refresh(region)
    return region


def set_region_status(region_id, status: str, *, db: Session) -> Any:
    """Publish (``published``) or unpublish (``draft``) a region."""
    from app.models import Region

    if status not in ("draft", "published"):
        raise ValueError(f"invalid region status: {status!r}")
    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    region.status = status
    db.commit()
    db.refresh(region)
    return region


def unassign_spots_from_region(
    spot_ids, *, db: Session, allow_duplicate: bool = False
) -> int:
    """Drag a spot out of every region → region-less (region_id NULL). It then
    surfaces at the top of the Übersicht until a region is picked. Returns the
    count changed; unknown ids are ignored (idempotent)."""
    from sqlalchemy import select
    from app.models import Spot

    spots = db.scalars(select(Spot).where(Spot.id.in_(spot_ids))).all()
    changed = 0
    for spot in spots:
        if spot.region_id is not None:
            from geoalchemy2.shape import to_shape

            point = to_shape(spot.location)
            enforce_duplicates(
                "Spot",
                find_spot_duplicates(
                    db,
                    name=spot.name,
                    region_id=None,
                    lat=float(point.y),
                    lon=float(point.x),
                    exclude_id=spot.id,
                ),
                allow_likely=allow_duplicate,
            )
            spot.region_id = None
            changed += 1
    db.commit()
    return changed


def update_region(
    region_id,
    data: dict,
    *,
    db: Session,
    allow_duplicate: bool = False,
    actor: str | None = None,
) -> Any:
    """Patch a region's editorial fields. Only keys present in ``data`` are
    applied; ``defaults`` is merged, ``season``/``name``/``description`` replaced."""
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    from geoalchemy2.shape import to_shape

    point = to_shape(region.center) if region.center is not None else None
    duplicate_candidates = enforce_duplicates(
        "Region",
        find_region_duplicates(
            db,
            name=data.get("name") or region.name,
            country=data.get("country", region.country),
            lat=float(point.y) if point is not None else None,
            lon=float(point.x) if point is not None else None,
            bounds=region.bounds,
            exclude_id=region.id,
        ),
        allow_likely=allow_duplicate,
    )
    if "name" in data and data["name"]:
        region.name = data["name"]
    if "country" in data:
        region.country = data["country"]
    if "description" in data:
        region.description = data["description"]
    if "season" in data:
        region.season = data["season"]
    if "defaults" in data and data["defaults"] is not None:
        merged = dict(region.defaults or {})
        merged.update(data["defaults"])
        region.defaults = merged
    db.commit()
    db.refresh(region)
    if duplicate_candidates:
        logger.warning(
            "region duplicate override by %s for %s against %s",
            actor,
            region.id,
            [item["id"] for item in duplicate_candidates],
        )
    return region


def delete_region(region_id, *, db: Session) -> None:
    """Delete a region — only when no spots are assigned to it. Raises
    LookupError if unknown, ValueError if it still has spots (the caller must
    move or delete them first)."""
    from sqlalchemy import func, select
    from app.models import Region, Spot

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    count = db.scalar(
        select(func.count()).select_from(Spot).where(Spot.region_id == region_id)
    )
    if count:
        raise ValueError(
            f"Region hat noch {count} Spot(s) — bitte zuerst verschieben oder löschen."
        )
    from app.media.lifecycle import collect_entity_urls, purge_entity_urls

    media_urls = collect_entity_urls(db, "region", region_id)
    db.delete(region)
    db.commit()
    purge_entity_urls(db, media_urls)


def set_region_image(region_id, image: dict, *, db: Session) -> Any:
    """Replace the region hero image.

    Normalised through the shared image builder, so a region image carries the
    same provenance as a spot image — one schema, one write path. Regions keep
    their lenient defaults for source/license (an operator pasting a URL owns
    the rights claim), unlike the spot route which demands all four upfront.
    """
    from app.models import Region

    if not (isinstance(image.get("url"), str) and image["url"].strip()):
        raise ValueError("Bild-URL ist erforderlich.")
    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    from app.media.lifecycle import demote_published_hero_rows

    payload = {key: image.get(key) for key in CANONICAL_KEYS}
    payload["source"] = payload.get("source") or "manual"
    payload["license"] = payload.get("license") or "own"
    payload["provider"] = payload.get("provider") or "manual"
    next_image = build_image(**payload)
    demote_published_hero_rows(db, "region", region.id, keep_url=next_image["url"])
    region.image = next_image
    db.commit()
    db.refresh(region)
    return region


def set_region_image_focal(region_id, x: float, y: float, *, db: Session) -> Any:
    """Store the region image's focal point (object-position %, 0..100)."""
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    if not (isinstance(region.image, dict) and region.image.get("url")):
        raise ValueError("Kein Bild zum Positionieren.")
    region.image = with_fields(region.image, focal=normalize_focal(x, y))
    db.commit()
    db.refresh(region)
    return region


def set_region_image_focal_mobile(
    region_id, x: float | None, y: float | None, *, db: Session
) -> Any:
    """Store the region image's mobile focal point, or clear it when x/y are None."""
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    if not (isinstance(region.image, dict) and region.image.get("url")):
        raise ValueError("Kein Bild zum Positionieren.")
    focal_mobile = normalize_focal(x, y) if x is not None and y is not None else None
    region.image = with_fields(region.image, focal_mobile=focal_mobile)
    db.commit()
    db.refresh(region)
    return region
