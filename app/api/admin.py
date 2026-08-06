"""Admin write endpoints (Sprint 8). Optionally gated by the ADMIN_KEY header."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.admin import dashboard as admin_dashboard
from app.admin import notifications as admin_notifications
from app.admin import regions as admin_regions
from app.admin import spots as admin_spots
from app.admin import team as admin_team
from app.admin.deps import get_commons_client, get_extract_client, get_stock_client
from app.admin.jobs import get_job_status, trigger_era5_job
from app.auth.deps import Principal, current_user, get_actor, require_role
from app.admin.duplicates import (
    ExactDuplicateError,
    LikelyDuplicateError,
    duplicate_detail,
    enforce_duplicates,
    find_region_duplicates,
)
from app.admin.readiness import validate_spot_readiness
from app.config import get_settings
from app.db.session import get_db
from app.api.community import ImageOut
from app.search.deps import get_geocoder
from app.media import (
    HERO_MAX_BYTES,
    HERO_OUT_MAX_WIDTH,
    HeroImageError,
    delete_url,
    reencode_image,
    read_upload_limited,
    save_hero_image,
    validate_hero_image,
)
from app.models import Region, Spot
from app.schemas import RegionRead, SpotRead, SpotSummary
from app.schemas.admin import (
    AssignRegionRequest,
    BulkAssignRegionRequest,
    BulkUnassignRegionRequest,
    FinishRankRequest,
    ImageAttributionRequest,
    ImageRequest,
    OverrideRequest,
    RegionCreate,
    RegionDefaultsUpdate,
    RegionImageRequest,
    RegionUpdate,
    RevertRequest,
    SpotCreate,
    SpotUpdate,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("admin", "curator"))],
)


def _as_utc(dt: datetime) -> datetime:
    """Normalise to a timezone-aware instant so a naive DB value and an ISO
    string parsed by the client compare correctly."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _guard_version(db: Session, model, obj_id, expected: datetime | None) -> None:
    """Optimistic lock for the admin PATCH routes (this is a multi-operator
    tool). ``expected`` is the ``updated_at`` the client loaded; when present it
    must still match the row, otherwise a concurrent edit would be silently
    clobbered. ``None`` means "force" — the client already chose to overwrite.

    Raises 404 if the row is gone, 409 (with the fresh ``updated_at``) on a
    stale write. No auto-merge — the caller decides reload vs. overwrite.
    """
    if expected is None:
        return
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    if _as_utc(obj.updated_at) != _as_utc(expected):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_write",
                "message": (
                    "Der Datensatz wurde inzwischen von jemand anderem "
                    "geändert."
                ),
                "current_updated_at": _as_utc(obj.updated_at).isoformat(),
            },
        )


def _maybe_autoprocess_era5(background: BackgroundTasks, spot_id, client) -> None:
    """Schedule background climatology processing when ERA5_AUTOPROCESS is on."""
    settings = get_settings()
    if settings.era5_autoprocess:
        from app.admin import era5_worker

        background.add_task(
            era5_worker.process_one, spot_id, client=client, raw_dir=settings.era5_raw_dir
        )


def _catalog_conflict(db: Session, exc: IntegrityError) -> HTTPException:
    db.rollback()
    return HTTPException(
        status_code=409,
        detail="Name oder Slug ist bereits vergeben. Bitte den bestehenden Eintrag prüfen.",
    )


def _allow_duplicate(requested: bool, principal: Principal) -> bool:
    if requested and principal.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Nur Administratoren dürfen eine mögliche Dublette bestätigen.",
        )
    return requested


def _duplicate_conflict(exc: ExactDuplicateError | LikelyDuplicateError, principal: Principal):
    return HTTPException(
        status_code=409,
        detail=duplicate_detail(exc, role=principal.role),
    )


# --- dashboard (Sprint B) --------------------------------------------------

@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    """KPIs for the admin home: spot status counts, regions, readiness gaps,
    recently edited, and non-live spots still missing fields."""
    return admin_dashboard.overview(db)


@router.get("/map-spots")
def map_spots(
    db: Session = Depends(get_db),
    west: float | None = Query(default=None, ge=-180, le=180),
    south: float | None = Query(default=None, ge=-90, le=90),
    east: float | None = Query(default=None, ge=-180, le=180),
    north: float | None = Query(default=None, ge=-90, le=90),
    limit: int = Query(default=5000, ge=1, le=5000),
) -> list[dict]:
    """Coordinate-only map records, optionally restricted to the viewport."""
    values = (west, south, east, north)
    if any(value is not None for value in values) and not all(
        value is not None for value in values
    ):
        raise HTTPException(status_code=422, detail="Viewport-Grenzen müssen vollständig sein.")
    bounds = values if all(value is not None for value in values) else None
    if bounds is not None and (bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise HTTPException(status_code=422, detail="Viewport-Grenzen sind ungültig.")
    return admin_dashboard.map_spots(db, bounds=bounds, limit=limit)


@router.get("/spots")
def list_spots(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    region_id: uuid.UUID | None = Query(default=None),
    sport: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Free-text on name/slug"),
    sort: str = Query(default="name"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    exclude_status: str | None = Query(
        default=None, description="Hide spots with this status (e.g. 'archived')"
    ),
) -> dict:
    """Filtered, paginated spot list for the admin table (with total count)."""
    rows, total = admin_dashboard.list_spots(
        db, status=status, region_id=region_id, sport=sport, q=q,
        sort=sort, limit=limit, offset=offset, exclude_status=exclude_status,
    )
    return {
        "items": [SpotSummary.from_orm_spot(s).model_dump(mode="json") for s in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/regions")
def list_regions(db: Session = Depends(get_db)) -> list[dict]:
    """Regions with per-status spot counts for the admin regions view."""
    return [
        {
            "region": RegionRead.from_orm_region(entry["region"]).model_dump(mode="json"),
            "spot_counts": entry["spot_counts"],
        }
        for entry in admin_dashboard.list_regions_with_counts(db)
    ]


@router.get("/regions/{region_id}/record", response_model=RegionRead)
def get_region_record(region_id: uuid.UUID, db: Session = Depends(get_db)) -> RegionRead:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionRead.from_orm_region(region)


# --- spots -----------------------------------------------------------------

@router.post("/spots", response_model=SpotRead, status_code=201)
def create_spot(
    body: SpotCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    client=Depends(get_extract_client),
    actor: str = Depends(get_actor),
    principal: Principal = Depends(current_user),
):
    try:
        spot = admin_spots.create_spot(
            body.to_data(),
            db=db,
            client=client,
            actor=actor,
            allow_duplicate=_allow_duplicate(body.allow_duplicate, principal),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        raise _duplicate_conflict(exc, principal)
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    _maybe_autoprocess_era5(background, spot.id, client)
    return SpotRead.from_orm_spot(spot)


@router.patch("/spots/{spot_id}", response_model=SpotRead)
def update_spot(
    spot_id: uuid.UUID,
    body: SpotUpdate,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
    principal: Principal = Depends(current_user),
):
    """Patch a spot: editorial (merged) + structural/category columns. Only the
    fields present in the request are applied. Invalid enum values → 422.
    Optimistic lock: send ``expected_updated_at`` → 409 on a stale write."""
    _guard_version(db, Spot, spot_id, body.expected_updated_at)
    try:
        spot = admin_spots.update_spot(
            spot_id,
            body.to_data(),
            db=db,
            actor=actor,
            allow_duplicate=_allow_duplicate(body.allow_duplicate, principal),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        raise _duplicate_conflict(exc, principal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return SpotRead.from_orm_spot(spot)


@router.patch("/spots/{spot_id}/finish-rank", response_model=SpotRead)
def set_finish_rank(
    spot_id: uuid.UUID,
    body: FinishRankRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
):
    """Set/clear the manual Fertigstellen rank (red|yellow|green, or null=auto)."""
    try:
        spot = admin_spots.set_finish_rank(spot_id, body.rank, db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SpotRead.from_orm_spot(spot)


@router.post("/spots/{spot_id}/override")
def override(
    spot_id: uuid.UUID,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> dict:
    try:
        admin_spots.override_auto_field(
            spot_id, body.field, body.value, db=db, actor=actor
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return admin_spots.spot_effective_view(spot_id, db=db)


@router.post("/spots/{spot_id}/revert")
def revert(
    spot_id: uuid.UUID,
    body: RevertRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> dict:
    try:
        admin_spots.revert_override(
            spot_id, body.field, db=db, actor=actor
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return admin_spots.spot_effective_view(spot_id, db=db)


@router.post("/spots/{spot_id}/image", response_model=SpotRead)
def set_image(
    spot_id: uuid.UUID,
    body: ImageRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
):
    try:
        spot = admin_spots.manage_spot_image(
            spot_id, body.to_image(), db=db, actor=actor
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SpotRead.from_orm_spot(spot)


@router.post("/spots/{spot_id}/image/attribution", response_model=SpotRead)
def set_image_attribution(
    spot_id: uuid.UUID,
    body: ImageAttributionRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
):
    """Edit the current hero image's credit/license/source without re-uploading
    (url + focal preserved)."""
    try:
        spot = admin_spots.update_image_attribution(
            spot_id,
            credit=body.credit,
            license=body.license,
            source=body.source,
            db=db,
            actor=actor,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SpotRead.from_orm_spot(spot)


@router.post("/spots/{spot_id}/image/upload", response_model=SpotRead)
async def upload_image(
    spot_id: uuid.UUID,
    file: UploadFile = File(...),
    credit: str = Form(..., description="Bild-Credit / Urheber (Pflicht)"),
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
):
    """Upload a hero image (multipart). Re-validates the frontend HERO_REQ rules
    server-side, stores the file under ``media_dir`` and records it as the spot's
    image with ``source='upload'``, ``license='own'`` and the given credit."""
    if not (credit and credit.strip()):
        raise HTTPException(status_code=422, detail="Bild-Credit ist erforderlich.")
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")

    try:
        data = await read_upload_limited(file, HERO_MAX_BYTES)
        # Admin operators may upload below-minimum-resolution heroes (the client
        # shows a blur warning); format and landscape are still enforced.
        await run_in_threadpool(
            validate_hero_image, data, file.content_type, allow_below_min=True
        )
        out, ext, _, _ = await run_in_threadpool(
            reencode_image, data, max_width=HERO_OUT_MAX_WIDTH
        )
    except HeroImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    settings = get_settings()
    old_url = (spot.image or {}).get("url") if isinstance(spot.image, dict) else None
    url = await run_in_threadpool(
        save_hero_image,
        spot_id, out, ext,
        media_dir=settings.media_dir, url_prefix=settings.media_url_prefix,
    )
    try:
        spot = admin_spots.manage_spot_image(
            spot_id,
            {"url": url, "source": "upload", "license": "own", "credit": credit.strip()},
            db=db, actor=actor,
        )
    except Exception:
        db.rollback()
        delete_url(url, media_dir=settings.media_dir, url_prefix=settings.media_url_prefix)
        raise
    if old_url != url:
        delete_url(old_url, media_dir=settings.media_dir, url_prefix=settings.media_url_prefix)
    return SpotRead.from_orm_spot(spot)


class FocalRequest(BaseModel):
    x: float
    y: float


@router.post("/spots/{spot_id}/image/focal", response_model=SpotRead)
def set_spot_image_focal(
    spot_id: uuid.UUID,
    body: FocalRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
):
    try:
        spot = admin_spots.set_image_focal(spot_id, body.x, body.y, db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SpotRead.from_orm_spot(spot)


@router.get("/spots/{spot_id}")
def effective_view(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return admin_spots.spot_effective_view(spot_id, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")


@router.get("/spots/{spot_id}/record", response_model=SpotRead)
def get_spot_record(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> SpotRead:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    return SpotRead.from_orm_spot(spot)


@router.get("/spots/{spot_id}/readiness")
def readiness(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return validate_spot_readiness(spot_id, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")


@router.post("/spots/{spot_id}/live")
def go_live(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
    client=Depends(get_extract_client),
) -> dict:
    # Go-live is always allowed now; the response carries `ready`/`gaps` so the
    # UI can show a non-blocking disclaimer.
    try:
        result = admin_spots.set_spot_live(spot_id, db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")

    # Compute the climatology on go-live when it isn't ready yet. Done
    # SYNCHRONOUSLY and in memory (era5_worker.compute_now): on serverless the
    # FastAPI background task doesn't run reliably and pyarrow isn't bundled, so
    # the old fire-and-forget path never actually produced a climatology. A
    # queued job is still recorded first as a visible fallback. Best-effort —
    # compute_now never raises and go-live already succeeded above.
    if "climatology" in (result.get("gaps") or []):
        try:
            trigger_era5_job(spot_id, db=db, client=client)
        except Exception:
            db.rollback()
        from app.admin import era5_worker

        outcome, _ = era5_worker.compute_now(spot_id, client=client)
        if outcome == "ok":
            # Reflect the freshly derived climatology in the response (compute_now
            # committed it in its own session, so the request session is stale).
            gaps = [g for g in (result.get("gaps") or []) if g != "climatology"]
            result["gaps"] = gaps
            result["ready"] = len(gaps) == 0

    return result


@router.post("/spots/{spot_id}/unpublish")
def unpublish_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> dict:
    """Take a published spot offline again (back to draft)."""
    try:
        return admin_spots.set_spot_status(spot_id, "draft", db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/spots/{spot_id}/archive")
def archive_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> dict:
    """Archive a spot (removed from listings, reversible via reactivate)."""
    try:
        return admin_spots.set_spot_status(spot_id, "archived", db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/spots/{spot_id}/reactivate")
def reactivate_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> dict:
    """Reactivate an archived spot — moves it back into the draft workflow."""
    try:
        return admin_spots.reactivate_spot(spot_id, db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")


@router.delete("/spots/{spot_id}", status_code=204)
def delete_spot(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> Response:
    """Permanently delete a spot and its dependent rows (irreversible)."""
    try:
        admin_spots.delete_spot(spot_id, db=db, actor=actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    return Response(status_code=204)


@router.post("/spots/{spot_id}/era5")
def trigger_era5(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    client=Depends(get_extract_client),
) -> dict:
    try:
        trigger_era5_job(spot_id, db=db, client=client)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    # Compute synchronously and in memory (serverless-safe); see go_live.
    from app.admin import era5_worker

    era5_worker.compute_now(spot_id, client=client)
    return get_job_status(spot_id, db=db)


@router.post("/era5/process-queue")
def process_era5_queue(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    client=Depends(get_extract_client),
) -> dict:
    """Kick off background processing of all queued ERA5 jobs (button B). Returns
    immediately with the number of queued spots scheduled."""
    from app.admin import era5_worker

    n = era5_worker.count_queued(db)
    background.add_task(
        era5_worker.process_queue, client=client, raw_dir=get_settings().era5_raw_dir
    )
    return {"queued": n, "scheduled": True}


@router.get("/spots/{spot_id}/era5")
def era5_status(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    status = get_job_status(spot_id, db=db)
    if status is None:
        raise HTTPException(status_code=404, detail="No ERA5 job for spot")
    return status


@router.post("/spots/{spot_id}/assign-region", response_model=SpotRead)
def assign_region(
    spot_id: uuid.UUID,
    body: AssignRegionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    try:
        spot = admin_regions.assign_spot_to_region(
            spot_id,
            body.region_id,
            db=db,
            allow_duplicate=_allow_duplicate(body.allow_duplicate, principal),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        raise _duplicate_conflict(exc, principal)
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return SpotRead.from_orm_spot(spot)


@router.post("/spots/bulk-assign-region")
def bulk_assign_region(
    body: BulkAssignRegionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
) -> dict:
    """Move several spots to a region at once (both directions — the caller
    picks the target). All-or-nothing: an unknown id rolls the batch back."""
    try:
        moved = admin_regions.assign_spots_to_region(
            body.spot_ids,
            body.region_id,
            db=db,
            allow_duplicate=_allow_duplicate(body.allow_duplicate, principal),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        db.rollback()
        raise _duplicate_conflict(exc, principal)
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return {"moved": moved}


@router.post("/spots/bulk-unassign-region")
def bulk_unassign_region(
    body: BulkUnassignRegionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
) -> dict:
    """Make spots region-less (drag out of a region without a target). They then
    show at the top of the Übersicht until a region is assigned."""
    try:
        changed = admin_regions.unassign_spots_from_region(
            body.spot_ids,
            db=db,
            allow_duplicate=_allow_duplicate(body.allow_duplicate, principal),
        )
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        db.rollback()
        raise _duplicate_conflict(exc, principal)
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return {"changed": changed}


# --- regions ---------------------------------------------------------------

@router.get("/geocode")
def geocode(q: str = Query(..., min_length=2), geocoder=Depends(get_geocoder)) -> list[dict]:
    """Look up coordinates for a place/region name (Open-Meteo geocoder)."""
    try:
        results = geocoder.geocode(q)
    except Exception:
        raise HTTPException(status_code=502, detail="Geocoder nicht erreichbar.")
    return [
        {
            "name": r.name,
            "lat": r.lat,
            "lon": r.lon,
            "country": r.country,
            "feature_code": r.feature_code,
        }
        for r in results[:5]
    ]


@router.post("/regions", response_model=RegionRead, status_code=201)
def create_region(
    body: RegionCreate,
    db: Session = Depends(get_db),
    geocoder=Depends(get_geocoder),
    actor: str = Depends(get_actor),
    principal: Principal = Depends(current_user),
):
    data = body.to_data()
    allow_duplicate = _allow_duplicate(body.allow_duplicate, principal)
    try:
        # Name+country works even when neither the request nor an existing
        # region has coordinates. The service repeats this after geocoding to
        # add distance and bounds-overlap signals.
        enforce_duplicates(
            "Region",
            find_region_duplicates(
                db,
                name=body.name,
                country=body.country,
                lat=body.lat,
                lon=body.lon,
            ),
            allow_likely=allow_duplicate,
        )
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        raise _duplicate_conflict(exc, principal)
    # A region is an area — the operator gives a name, we resolve the centre +
    # bounding box automatically (Open-Meteo geocoder) instead of typing lat/lon.
    if data.get("lat") is None or data.get("lon") is None:
        from app.search.geocode import classify_geocode

        query = ", ".join(x for x in [body.name, body.country] if x)
        try:
            hit = classify_geocode(query, geocoder=geocoder)
        except Exception:
            hit = None
        if hit is None:
            raise HTTPException(
                status_code=422,
                detail=f'Keine Koordinaten für „{body.name}" gefunden — bitte den Namen präzisieren.',
            )
        data["lat"] = hit["point"]["lat"]
        data["lon"] = hit["point"]["lon"]
        if hit.get("bounds"):
            b = hit["bounds"]
            data["bounds"] = [b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"]]
    try:
        region = admin_regions.create_region(
            data,
            db=db,
            allow_duplicate=allow_duplicate,
            actor=actor,
        )
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        raise _duplicate_conflict(exc, principal)
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return RegionRead.from_orm_region(region)


@router.patch("/regions/{region_id}/defaults", response_model=RegionRead)
def update_defaults(
    region_id: uuid.UUID, body: RegionDefaultsUpdate, db: Session = Depends(get_db)
):
    try:
        region = admin_regions.update_region_defaults(region_id, body.defaults, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return RegionRead.from_orm_region(region)


@router.post("/regions/{region_id}/stock-image", response_model=RegionRead)
def region_stock_image(
    region_id: uuid.UUID,
    db: Session = Depends(get_db),
    client=Depends(get_stock_client),
):
    try:
        region = admin_regions.set_region_stock_image(region_id, db=db, client=client)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionRead.from_orm_region(region)


@router.post("/spots/{spot_id}/commons-images/fetch")
def fetch_commons_images(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    client=Depends(get_commons_client),
) -> dict:
    """Geosearch Wikimedia Commons around the spot and store newly-licensed
    hits as gallery images. Safe to call again later — already-stored source
    URLs are skipped, so it only ever adds what's new."""
    try:
        created = admin_spots.fetch_commons_images(spot_id, db=db, client=client)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    return {"items": [ImageOut.of(i) for i in created]}


@router.patch("/regions/{region_id}", response_model=RegionRead)
def update_region(
    region_id: uuid.UUID,
    body: RegionUpdate,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
    principal: Principal = Depends(current_user),
):
    """Edit a region: description, season (Windmonate), defaults, name.
    Optimistic lock: send ``expected_updated_at`` → 409 on a stale write."""
    _guard_version(db, Region, region_id, body.expected_updated_at)
    try:
        region = admin_regions.update_region(
            region_id,
            body.to_data(),
            db=db,
            allow_duplicate=_allow_duplicate(body.allow_duplicate, principal),
            actor=actor,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    except (ExactDuplicateError, LikelyDuplicateError) as exc:
        raise _duplicate_conflict(exc, principal)
    except IntegrityError as exc:
        raise _catalog_conflict(db, exc)
    return RegionRead.from_orm_region(region)


@router.post("/regions/{region_id}/compute-months", response_model=RegionRead)
def compute_region_months(region_id: uuid.UUID, db: Session = Depends(get_db)):
    """Recompute the region's best months from its spots' climatology (the
    Windmonate 'Berechnen' toggle)."""
    try:
        region = admin_regions.recompute_best_months(region_id, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionRead.from_orm_region(region)


@router.post("/regions/{region_id}/publish", response_model=RegionRead)
def publish_region(region_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        region = admin_regions.set_region_status(region_id, "published", db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionRead.from_orm_region(region)


@router.post("/regions/{region_id}/unpublish", response_model=RegionRead)
def unpublish_region(region_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        region = admin_regions.set_region_status(region_id, "draft", db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionRead.from_orm_region(region)


@router.delete("/regions/{region_id}", status_code=204)
def delete_region(region_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a region — only when no spots are assigned (409 otherwise)."""
    try:
        admin_regions.delete_region(region_id, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return Response(status_code=204)


@router.post("/regions/{region_id}/image", response_model=RegionRead)
def set_region_image(
    region_id: uuid.UUID, body: RegionImageRequest, db: Session = Depends(get_db)
):
    """Set the region hero image manually (by URL + credit)."""
    try:
        region = admin_regions.set_region_image(region_id, body.to_image(), db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RegionRead.from_orm_region(region)


@router.post("/regions/{region_id}/image/focal", response_model=RegionRead)
def set_region_image_focal(
    region_id: uuid.UUID, body: FocalRequest, db: Session = Depends(get_db)
):
    try:
        region = admin_regions.set_region_image_focal(region_id, body.x, body.y, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Region not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RegionRead.from_orm_region(region)


@router.post("/regions/{region_id}/image/upload", response_model=RegionRead)
async def upload_region_image(
    region_id: uuid.UUID,
    file: UploadFile = File(...),
    credit: str = Form(..., description="Bild-Credit / Urheber (Pflicht)"),
    db: Session = Depends(get_db),
):
    """Upload a region hero image (multipart), re-validating the hero rules."""
    from app.models import Region

    if not (credit and credit.strip()):
        raise HTTPException(status_code=422, detail="Bild-Credit ist erforderlich.")
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    try:
        data = await read_upload_limited(file, HERO_MAX_BYTES)
        await run_in_threadpool(validate_hero_image, data, file.content_type)
        out, ext, _, _ = await run_in_threadpool(
            reencode_image, data, max_width=HERO_OUT_MAX_WIDTH
        )
    except HeroImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    settings = get_settings()
    from app.media import save_region_hero_image

    old_url = (region.image or {}).get("url") if isinstance(region.image, dict) else None
    url = await run_in_threadpool(
        save_region_hero_image,
        region_id, out, ext,
        media_dir=settings.media_dir, url_prefix=settings.media_url_prefix,
    )
    try:
        region = admin_regions.set_region_image(
            region_id,
            {"url": url, "source": "upload", "license": "own", "credit": credit.strip()},
            db=db,
        )
    except Exception:
        db.rollback()
        delete_url(url, media_dir=settings.media_dir, url_prefix=settings.media_url_prefix)
        raise
    if old_url != url:
        delete_url(old_url, media_dir=settings.media_dir, url_prefix=settings.media_url_prefix)
    return RegionRead.from_orm_region(region)


# --- team notes + activity (admin overview / users) ------------------------

class TeamNoteIn(BaseModel):
    body: str
    priority: str | None = None


class TeamNotePatch(BaseModel):
    body: str | None = None
    priority: str | None = None


@router.get("/team-notes")
def list_team_notes(db: Session = Depends(get_db)) -> list[dict]:
    return admin_team.list_notes(db)


@router.post("/team-notes", status_code=201)
def create_team_note(
    body: TeamNoteIn,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
) -> dict:
    try:
        note = admin_team.create_note(
            db, author=actor, body=body.body, priority=body.priority
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return admin_team.note_view(note)


@router.patch("/team-notes/{note_id}")
def update_team_note(
    note_id: uuid.UUID,
    body: TeamNotePatch,
    db: Session = Depends(get_db),
) -> dict:
    try:
        note = admin_team.update_note(
            db, note_id, body=body.body, priority=body.priority
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if note is None:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden.")
    return admin_team.note_view(note)


@router.delete("/team-notes/{note_id}", status_code=204)
def delete_team_note(note_id: uuid.UUID, db: Session = Depends(get_db)):
    from fastapi import Response

    if not admin_team.delete_note(db, note_id):
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden.")
    return Response(status_code=204)


@router.get("/activity")
def activity(
    db: Session = Depends(get_db), q: str | None = Query(default=None)
) -> list[dict]:
    """Recent real changes (spot + moderation audits), newest first. ``q``
    searches actor name/email, target (e.g. spot name) and label."""
    return admin_team.activity(db, q=q)


# --- operator notifications (badge) ----------------------------------------

@router.get("/notifications")
def list_notifications(db: Session = Depends(get_db)) -> dict:
    items = [admin_notifications.view(n) for n in admin_notifications.list_recent(db)]
    return {"items": items, "unread": admin_notifications.unread_count(db)}


@router.get("/notifications/unread-count")
def notifications_unread_count(db: Session = Depends(get_db)) -> dict:
    """Cheap endpoint for the badge's minute polling."""
    return {"count": admin_notifications.unread_count(db)}


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        n = admin_notifications.mark_read(db, notification_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Benachrichtigung nicht gefunden.")
    return admin_notifications.view(n)


@router.post("/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db)) -> dict:
    return {"marked": admin_notifications.mark_all_read(db)}


# --- board tasks (kanban) --------------------------------------------------

class TaskIn(BaseModel):
    title: str
    body: str | None = None


class TaskPatch(BaseModel):
    status: str | None = None
    title: str | None = None
    body: str | None = None


@router.get("/board/tasks")
def list_board_tasks(db: Session = Depends(get_db)) -> list[dict]:
    return admin_team.list_tasks(db)


@router.post("/board/tasks", status_code=201)
def create_board_task(
    body: TaskIn, db: Session = Depends(get_db), actor: str = Depends(get_actor)
) -> dict:
    try:
        task = admin_team.create_task(db, title=body.title, body=body.body, author=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return admin_team._task_view(task)


@router.patch("/board/tasks/{task_id}")
def update_board_task(
    task_id: uuid.UUID, body: TaskPatch, db: Session = Depends(get_db)
) -> dict:
    task = admin_team.update_task(
        db, task_id, status=body.status, title=body.title, body=body.body
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return admin_team._task_view(task)


@router.delete("/board/tasks/{task_id}", status_code=204)
def delete_board_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    from fastapi import Response

    if not admin_team.delete_task(db, task_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return Response(status_code=204)
