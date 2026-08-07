"""Admin media proxy: provider search behind our own auth.

Provider API keys live on the server and never reach the client bundle. That is
not only good hygiene here — the deployment's CSP allows ``connect-src 'self'``
plus MapTiler only, so a browser could not call a provider API even if it had a
key.

The router sits under ``/admin``, so it inherits the same role guard as the rest
of the back office and is absent entirely from the public deployment
(``ENABLE_ADMIN_API=false`` never mounts it).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_role
from app.db.session import get_db
from app.media import adopt as media_adopt
from app.media import gallery as media_gallery
from app.media import search as media_search
from app.media import worklist as media_worklist_module
from app.media.providers import NEARBY, PROVIDER_KEYS
from app.models import Region, Spot

router = APIRouter(
    prefix="/admin/media",
    tags=["admin-media"],
    dependencies=[Depends(require_role("admin", "curator"))],
)


@router.get("/search")
def search_media(
    db: Session = Depends(get_db),
    q: str = Query(default="", max_length=200),
    provider: str = Query(...),
    role: str = Query(default="hero", pattern="^(hero|gallery)$"),
    page: int = Query(default=1, ge=1, le=20),
    per_page: int = Query(default=24, ge=1, le=48),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=5.0, gt=0, le=50),
) -> dict:
    """One provider tab's results.

    Always 200 for provider-side problems — an unconfigured, throttled or
    unreachable source reports its state in ``status`` so the overlay can grey
    out that one tab. Only a malformed request is an error.
    """
    if provider not in PROVIDER_KEYS:
        raise HTTPException(status_code=422, detail=f"Unbekannte Quelle: {provider}")
    if provider != NEARBY and not q.strip():
        raise HTTPException(status_code=422, detail="Suchbegriff fehlt.")
    if provider == NEARBY and (lat is None or lon is None):
        raise HTTPException(
            status_code=422, detail="Für die Umkreissuche fehlen Koordinaten."
        )

    outcome = media_search.search(
        db,
        provider=provider,
        query=q.strip(),
        page=page,
        per_page=per_page,
        role=role,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
    )
    return outcome.as_payload()


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)) -> dict:
    """Availability and hourly budget per provider — the admin header's budget
    display reads this, so a shrinking Unsplash allowance is visible before it
    runs out."""
    return {"providers": media_search.provider_status(db)}


class FocalPoint(BaseModel):
    """Object-position percentages, matching what the renderer and the focal
    editor already speak."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class AdoptRequest(BaseModel):
    entity_type: str = Field(pattern="^(spot|region)$")
    entity_id: uuid.UUID
    role: str = Field(pattern="^(hero|gallery)$")
    provider: str = Field(min_length=1, max_length=30)
    external_id: str = Field(min_length=1, max_length=200)
    focal: FocalPoint | None = None


@router.post("/adopt")
def adopt_media(
    body: AdoptRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Take a provider photo into the catalogue.

    The request carries an identity, never a payload: everything about the photo
    is re-resolved from the provider here. A duplicate hero is refused with 409
    so the client can tell it apart from a validation problem.
    """
    try:
        outcome = media_adopt.adopt(
            db,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            role=body.role,
            provider=body.provider,
            external_id=body.external_id,
            focal=body.focal.model_dump() if body.focal else None,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    except media_adopt.DuplicateHeroError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "duplicate_hero", "message": str(exc), "usages": exc.usages},
        )
    except media_adopt.AdoptError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "entity_type": outcome.entity_type,
        "entity_id": str(outcome.entity_id),
        "role": outcome.role,
        "image": outcome.image,
        "gallery_image_id": (
            str(outcome.gallery_image_id) if outcome.gallery_image_id else None
        ),
        "demoted_hero": outcome.demoted_hero,
        "warnings": outcome.warnings,
    }


@router.post("/verify-sources")
def verify_sources(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Check stored image URLs and mark sources that have gone away.

    Operator-triggered on purpose: it makes an outbound request per image, and
    it is worth running before a content review rather than every night.
    """
    return media_adopt.verify_sources(db, limit=limit)


class ReorderRequest(BaseModel):
    entity_type: str = Field(pattern="^(spot|region)$")
    entity_id: uuid.UUID
    image_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


@router.get("/gallery/{entity_type}/{entity_id}")
def list_gallery(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Gallery images in operator order. Same endpoint for spots and regions."""
    try:
        rows = media_gallery.list_gallery(db, entity_type, entity_id)
    except media_gallery.GalleryError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"items": [media_gallery.as_payload(row) for row in rows]}


@router.patch("/gallery/order")
def reorder_gallery(body: ReorderRequest, db: Session = Depends(get_db)) -> dict:
    """Persist a drag-and-drop order."""
    try:
        rows = media_gallery.reorder(
            db, body.entity_type, body.entity_id, body.image_ids
        )
    except media_gallery.GalleryError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"items": [media_gallery.as_payload(row) for row in rows]}


@router.delete("/gallery/{image_id}", status_code=204)
def remove_gallery_image(image_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Take an image out of the gallery.

    Marked removed rather than deleted — community photos carry a consent
    record and a report history that a layout decision must not destroy.
    """
    try:
        media_gallery.remove(db, image_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden.")
    return Response(status_code=204)


@router.post("/gallery/{image_id}/promote")
def promote_gallery_image(image_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Make a gallery image the hero; the current hero moves into the gallery."""
    try:
        return media_gallery.promote_to_hero(db, image_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden.")
    except media_gallery.GalleryError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/worklist")
def media_worklist(
    db: Session = Depends(get_db),
    media: str | None = Query(default=None, pattern="^(no_hero|unverified|duplicate|dead)$"),
) -> dict:
    """Outstanding image work: per-state counts plus the affected regions.

    Spots come from the main spot list (which already filters and paginates);
    regions have no such list of their own, so they are returned here.
    """
    return {
        "summary": media_worklist_module.media_summary(db),
        "regions": media_worklist_module.region_worklist(db, media_filter=media),
    }


@router.get("/context/{entity_type}/{entity_id}")
def picker_context(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Everything the picker needs to open without the operator typing: the
    context line, coordinates for the radius search and the suggested queries.

    Built server-side because the suggestions are derived from stored entity
    data (name, region, country, sports) that the picker would otherwise have to
    re-assemble from several endpoints.
    """
    if entity_type == "spot":
        spot = db.get(Spot, entity_id)
        if spot is None:
            raise HTTPException(status_code=404, detail="Spot not found")
        region = db.get(Region, spot.region_id) if spot.region_id else None
        lat, lon = _coordinates(spot.location)
        return {
            "entity_type": "spot",
            "entity_id": str(spot.id),
            "title": spot.name,
            "subtitle": ", ".join(
                part for part in (region.name if region else None, region.country if region else None) if part
            ),
            "lat": lat,
            "lon": lon,
            "suggestions": _spot_suggestions(spot, region),
            "has_image": bool(spot.image),
        }

    if entity_type == "region":
        region = db.get(Region, entity_id)
        if region is None:
            raise HTTPException(status_code=404, detail="Region not found")
        lat, lon = _coordinates(region.center)
        return {
            "entity_type": "region",
            "entity_id": str(region.id),
            "title": region.name,
            "subtitle": region.country or "",
            "lat": lat,
            "lon": lon,
            "suggestions": _region_suggestions(region),
            "has_image": bool(region.image),
        }

    raise HTTPException(status_code=422, detail=f"Unbekannter Typ: {entity_type}")


def _coordinates(geography) -> tuple[float | None, float | None]:
    if geography is None:
        return None, None
    from geoalchemy2.shape import to_shape

    point = to_shape(geography)
    return point.y, point.x


# Sport terms in English: stock libraries are indexed in English, and a German
# query returns a fraction of the same catalogue.
_SPORT_TERMS = {
    "kitesurf": "kitesurfing",
    "wavekite": "kitesurfing waves",
    "windsurf": "windsurfing",
    "wing": "wing foiling",
    "surf": "surfing",
}


def _spot_suggestions(spot, region) -> list[str]:
    """Search chips for a spot: its own name first, then sport and place terms.

    The first chip is active when the overlay opens, so it must be the most
    specific one — the operator should not have to type anything.
    """
    region_name = region.name if region else None
    chips = [spot.name]
    sports = list(spot.sports or [])
    if region_name and sports:
        chips.append(f"{region_name} {_SPORT_TERMS.get(sports[0], sports[0])}")
    if region_name:
        chips.append(f"{region_name} beach")
    if region_name and region and region.country:
        chips.append(f"{region_name} coast")
    return _dedupe(chips)


def _region_suggestions(region) -> list[str]:
    """Regions get landscape terms rather than sport terms — a region hero shows
    the place, not somebody riding in it."""
    chips = [region.name, f"{region.name} coast", f"{region.name} coastline"]
    if region.country:
        chips.append(f"{region.name} landscape")
    return _dedupe(chips)


def _dedupe(chips: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for chip in chips:
        cleaned = " ".join((chip or "").split())
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            out.append(cleaned)
    return out
