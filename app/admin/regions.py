"""Region write workflow + region stock images."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.admin.stock import StockImageClient


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return base or uuid.uuid4().hex[:8]


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


def create_region(data: dict, *, db: Session) -> Any:
    """Create a region with optional centre + bounds and defaults template."""
    from app.models import Region

    center = None
    if data.get("lat") is not None and data.get("lon") is not None:
        center = _point(float(data["lat"]), float(data["lon"]))
    bounds = None
    bbox = data.get("bounds")
    if bbox and len(bbox) == 4:
        bounds = _bbox_polygon(bbox)
    region = Region(
        slug=data.get("slug") or _slugify(data["name"]),
        name=data["name"],
        country=data.get("country"),
        center=center,
        bounds=bounds,
        description=data.get("description"),
        defaults=data.get("defaults") or {},
        season=data.get("season"),
        image=data.get("image"),
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


def assign_spot_to_region(spot_id, region_id, *, db: Session) -> Any:
    """Move a spot to a region, inheriting ``model_pref`` if unset."""
    from app.models import Region, Spot

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    spot.region_id = region.id
    if not spot.model_pref and region.defaults:
        spot.model_pref = region.defaults.get("model_pref")
    db.commit()
    db.refresh(spot)
    return spot


def assign_spots_to_region(spot_ids, region_id, *, db: Session) -> int:
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


def unassign_spots_from_region(spot_ids, *, db: Session) -> int:
    """Drag a spot out of every region → region-less (region_id NULL). It then
    surfaces at the top of the Übersicht until a region is picked. Returns the
    count changed; unknown ids are ignored (idempotent)."""
    from sqlalchemy import select
    from app.models import Spot

    spots = db.scalars(select(Spot).where(Spot.id.in_(spot_ids))).all()
    changed = 0
    for spot in spots:
        if spot.region_id is not None:
            spot.region_id = None
            changed += 1
    db.commit()
    return changed


def update_region(region_id, data: dict, *, db: Session) -> Any:
    """Patch a region's editorial fields. Only keys present in ``data`` are
    applied; ``defaults`` is merged, ``season``/``name``/``description`` replaced."""
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
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
    db.delete(region)
    db.commit()


def set_region_image(region_id, image: dict, *, db: Session) -> Any:
    """Set the region hero image (url required; source/license/credit tracked)."""
    from app.models import Region

    if not (isinstance(image.get("url"), str) and image["url"].strip()):
        raise ValueError("Bild-URL ist erforderlich.")
    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    region.image = {
        "url": image["url"].strip(),
        "source": (image.get("source") or "manual").strip() or "manual",
        "license": (image.get("license") or "own").strip() or "own",
        "credit": (image.get("credit") or "").strip(),
    }
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
    focal = {"x": max(0.0, min(100.0, float(x))), "y": max(0.0, min(100.0, float(y)))}
    region.image = {**region.image, "focal": focal}
    db.commit()
    db.refresh(region)
    return region


def fetch_region_stock_image(region_name: str, *, client: StockImageClient) -> dict | None:
    """Look up a credited stock image for a region (license + credit included)."""
    return client.search(region_name)


def set_region_stock_image(
    region_id, *, db: Session, client: StockImageClient
) -> Any:
    """Fetch and store a stock image for a region by its name."""
    from app.models import Region

    region = db.get(Region, region_id)
    if region is None:
        raise LookupError(f"unknown region {region_id}")
    image = fetch_region_stock_image(region.name, client=client)
    if image is not None:
        region.image = image
        db.commit()
        db.refresh(region)
    return region
