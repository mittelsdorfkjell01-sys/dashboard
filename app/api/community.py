"""Public community endpoints (Sprint C): ratings, tips, submissions, images.

All writes are rate-limited per IP (Redis) with a honeypot, store a salted
``ip_hash`` not the raw IP, and — for uploads — require accepting the versioned
image license. Reads return only published/visible rows and never expose emails.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.community import service
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.community.security import check_honeypot, ip_hash
from app.config import get_settings
from app.db.session import get_db
from app.media import (
    GALLERY_OUT_MAX_WIDTH,
    GALLERY_OUT_QUALITY,
    HERO_OUT_MAX_WIDTH,
    HERO_OUT_QUALITY,
    HeroImageError,
    IMAGE_LICENSE_VERSION,
    license_terms,
    reencode_image,
    save_spot_image,
    validate_gallery_image,
    validate_hero_image,
)

MAX_GALLERY_PER_SPOT = 15
from app.models import LocalTip, SpotImage, SpotRating

router = APIRouter(tags=["community"])

# Per-IP fixed-window limits: (max hits, window seconds). Module-level so tests
# can tighten them.
LIMITS: dict[str, tuple[int, int]] = {
    "rating": (10, 3600),
    "tip": (10, 3600),
    "submission": (5, 3600),
    "image": (10, 3600),
    "report": (30, 3600),
}


# --- read schemas (no emails leak) -----------------------------------------

class RatingOut(BaseModel):
    id: str
    stars: int
    skill_level: str
    sport: str
    conditions: str
    author_name: str
    created_at: str

    @classmethod
    def of(cls, r: SpotRating) -> "RatingOut":
        return cls(
            id=str(r.id), stars=r.stars, skill_level=r.skill_level, sport=r.sport,
            conditions=r.conditions, author_name=r.author_name,
            created_at=r.created_at.isoformat(),
        )


class TipOut(BaseModel):
    id: str
    body: str
    author_name: str
    created_at: str

    @classmethod
    def of(cls, t: LocalTip) -> "TipOut":
        return cls(
            id=str(t.id), body=t.body, author_name=t.author_name,
            created_at=t.created_at.isoformat(),
        )


class ImageOut(BaseModel):
    id: str
    url: str
    kind: str
    width: int | None
    height: int | None
    credit: str | None
    created_at: str
    source: str
    license_name: str | None
    license_url: str | None
    source_url: str | None

    @classmethod
    def of(cls, i: SpotImage) -> "ImageOut":
        return cls(
            id=str(i.id), url=i.url, kind=i.kind, width=i.width, height=i.height,
            credit=i.credit, created_at=i.created_at.isoformat(),
            source=i.source, license_name=i.license_name, license_url=i.license_url,
            source_url=i.source_url,
        )


# --- write schemas (with honeypot) -----------------------------------------

class RatingIn(BaseModel):
    stars: int
    skill_level: str
    sport: str
    conditions: str
    author_name: str | None = None
    author_email: str | None = None
    website: str | None = None  # honeypot — must stay empty


class TipIn(BaseModel):
    body: str
    author_name: str | None = None
    author_email: str | None = None
    website: str | None = None  # honeypot


class SubmissionIn(BaseModel):
    payload: dict
    submitter_name: str | None = None
    submitter_email: str | None = None
    website: str | None = None  # honeypot


class ReportIn(BaseModel):
    reason: str
    note: str | None = None
    reporter_email: str | None = None
    website: str | None = None  # honeypot


# --- license (for the upload form) -----------------------------------------

@router.get("/community/license")
def get_license() -> dict:
    """Versioned image-upload terms the client must display + have accepted."""
    return license_terms()


# --- ratings ---------------------------------------------------------------

@router.post("/spots/{spot_id}/ratings", status_code=201)
def post_rating(
    spot_id: uuid.UUID,
    body: RatingIn,
    request: Request,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> RatingOut:
    check_honeypot(body.website)
    enforce(limiter, request, "rating", limit=LIMITS["rating"][0], window=LIMITS["rating"][1])
    try:
        rating = service.create_rating(
            db, spot_id,
            stars=body.stars, skill_level=body.skill_level, sport=body.sport,
            conditions=body.conditions, author_name=body.author_name,
            author_email=body.author_email, ip_hash=ip_hash(request),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RatingOut.of(rating)


@router.get("/spots/{spot_id}/ratings")
def get_ratings(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        rows, aggregate = service.list_ratings(db, spot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    return {"items": [RatingOut.of(r) for r in rows], "aggregate": aggregate}


# --- tips ------------------------------------------------------------------

@router.post("/spots/{spot_id}/tips", status_code=201)
def post_tip(
    spot_id: uuid.UUID,
    body: TipIn,
    request: Request,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> TipOut:
    check_honeypot(body.website)
    enforce(limiter, request, "tip", limit=LIMITS["tip"][0], window=LIMITS["tip"][1])
    try:
        tip = service.create_tip(
            db, spot_id, body=body.body, author_name=body.author_name,
            author_email=body.author_email, ip_hash=ip_hash(request),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TipOut.of(tip)


@router.get("/spots/{spot_id}/tips")
def get_tips(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        rows = service.list_tips(db, spot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    return {"items": [TipOut.of(t) for t in rows]}


# --- submissions -----------------------------------------------------------

@router.post("/submissions", status_code=201)
def post_submission(
    body: SubmissionIn,
    request: Request,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    check_honeypot(body.website)
    enforce(limiter, request, "submission", limit=LIMITS["submission"][0], window=LIMITS["submission"][1])
    try:
        sub = service.create_submission(
            db, payload=body.payload, submitter_name=body.submitter_name,
            submitter_email=body.submitter_email, ip_hash=ip_hash(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": str(sub.id), "status": sub.status}


# --- images ----------------------------------------------------------------

@router.post("/spots/{spot_id}/images", status_code=201)
async def post_image(
    spot_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form(...),
    credit: str | None = Form(default=None),
    license_accept: bool = Form(default=False),
    website: str | None = Form(default=None),  # honeypot
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> ImageOut:
    check_honeypot(website)
    enforce(limiter, request, "image", limit=LIMITS["image"][0], window=LIMITS["image"][1])

    if kind not in ("gallery", "hero_candidate"):
        raise HTTPException(status_code=422, detail="Unbekannter Bildtyp.")
    if not license_accept:
        raise HTTPException(
            status_code=422, detail="Bitte den Lizenzbedingungen zustimmen."
        )
    if not service.spot_exists(db, spot_id):
        raise HTTPException(status_code=404, detail="Spot not found")
    if kind == "gallery" and service.count_gallery_images(db, spot_id) >= MAX_GALLERY_PER_SPOT:
        raise HTTPException(
            status_code=422,
            detail=f"Maximal {MAX_GALLERY_PER_SPOT} Galeriebilder pro Spot.",
        )

    data = await file.read()
    try:
        # Validate the original, then re-encode (downscale + AVIF/WebP) so a large
        # heavy upload is accepted but only a small optimised file is stored.
        if kind == "hero_candidate":
            validate_hero_image(data, file.content_type)
            out, ext, width, height = reencode_image(
                data, max_width=HERO_OUT_MAX_WIDTH, quality=HERO_OUT_QUALITY
            )
        else:
            validate_gallery_image(data, file.content_type)
            out, ext, width, height = reencode_image(
                data, max_width=GALLERY_OUT_MAX_WIDTH, quality=GALLERY_OUT_QUALITY
            )
    except HeroImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    settings = get_settings()
    image_id = uuid.uuid4()
    url = save_spot_image(
        spot_id, image_id, out, ext,
        media_dir=settings.media_dir, url_prefix=settings.media_url_prefix,
    )
    # gallery = post-moderation (visible now); hero_candidate = awaits approval.
    status = "approved" if kind == "gallery" else "pending"
    image = service.create_image_record(
        db, spot_id,
        url=url, kind=kind, width=width, height=height, status=status,
        license_version=IMAGE_LICENSE_VERSION, license_accepted_at=datetime.now(timezone.utc),
        credit=credit, ip_hash=ip_hash(request),
    )
    return ImageOut.of(image)


@router.get("/spots/{spot_id}/images")
def get_images(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        rows = service.list_images(db, spot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    return {"items": [ImageOut.of(i) for i in rows]}


@router.post("/images/{image_id}/report", status_code=201)
def post_report(
    image_id: uuid.UUID,
    body: ReportIn,
    request: Request,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    check_honeypot(body.website)
    enforce(limiter, request, "report", limit=LIMITS["report"][0], window=LIMITS["report"][1])
    try:
        _, image = service.report_image(
            db, image_id, reason=body.reason, note=body.note,
            reporter_email=body.reporter_email, ip_hash=ip_hash(request),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Image not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "image_id": str(image.id),
        "report_count": image.report_count,
        "takedown_contact": get_settings().takedown_contact_email,
    }
