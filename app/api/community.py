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
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.community import service
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.community.security import check_honeypot, ip_hash
from app.config import get_settings
from app.db.session import get_db
from app.account.deps import current_account, optional_account
from app.models import AppUser, LocalTip, SpotImage, SpotRating
from app.media import (
    GALLERY_MAX_BYTES,
    GALLERY_OUT_MAX_WIDTH,
    GALLERY_OUT_QUALITY,
    HERO_MAX_BYTES,
    HERO_OUT_MAX_WIDTH,
    HERO_OUT_QUALITY,
    HeroImageError,
    PartialImageSetError,
    IMAGE_LICENSE_VERSION,
    license_terms,
    reencode_image_set,
    read_upload_limited,
    save_spot_image_set,
    validate_gallery_image,
    validate_hero_image,
)
from app.media.gc import (
    acquire_image_set_lock,
    register_media_reference,
    schedule_media_gc,
)
from app.media.lifecycle import purge_if_unreferenced

MAX_GALLERY_PER_SPOT = 15

router = APIRouter(tags=["community"])

# Per-IP fixed-window limits: (max hits, window seconds). Module-level so tests
# can tighten them.
LIMITS: dict[str, tuple[int, int]] = {
    "rating": (10, 3600),
    "tip": (10, 3600),
    "submission": (5, 3600),
    "image": (10, 3600),
    "report": (30, 3600),
    "upvote": (60, 3600),
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
    upvotes: int = 0
    viewer_upvoted: bool = False

    @classmethod
    def of(cls, r: SpotRating, vote: dict | None = None) -> "RatingOut":
        vote = vote or {}
        return cls(
            id=str(r.id), stars=r.stars, skill_level=r.skill_level, sport=r.sport,
            conditions=r.conditions, author_name=r.author_name,
            created_at=r.created_at.isoformat(),
            upvotes=vote.get("count", 0), viewer_upvoted=vote.get("viewer_upvoted", False),
        )


class TipOut(BaseModel):
    id: str
    body: str
    title: str | None = None
    author_name: str
    created_at: str
    parent_id: str | None = None
    upvotes: int = 0
    viewer_upvoted: bool = False

    @classmethod
    def of(cls, t: LocalTip, vote: dict | None = None) -> "TipOut":
        vote = vote or {}
        return cls(
            id=str(t.id), body=t.body, title=t.title, author_name=t.author_name,
            created_at=t.created_at.isoformat(),
            parent_id=str(t.parent_id) if t.parent_id else None,
            upvotes=vote.get("count", 0), viewer_upvoted=vote.get("viewer_upvoted", False),
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
    stars: int = Field(ge=1, le=5)
    skill_level: str = Field(min_length=1, max_length=20)
    sport: str = Field(min_length=1, max_length=20)
    conditions: str = Field(min_length=3, max_length=4_000)
    author_name: str | None = Field(default=None, max_length=120)
    author_email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


class TipIn(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)
    title: str | None = Field(default=None, max_length=120)
    author_name: str | None = Field(default=None, max_length=120)
    author_email: EmailStr | None = None
    parent_id: uuid.UUID | None = None  # set when this is a reply
    website: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


class SubmissionIn(BaseModel):
    payload: dict = Field(max_length=100)
    submitter_name: str | None = Field(default=None, max_length=120)
    submitter_email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


class ReportIn(BaseModel):
    reason: str = Field(min_length=1, max_length=30)
    note: str | None = Field(default=None, max_length=2_000)
    reporter_email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


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
    account: AppUser | None = Depends(optional_account),
) -> RatingOut:
    check_honeypot(body.website)
    enforce(limiter, request, "rating", limit=LIMITS["rating"][0], window=LIMITS["rating"][1])
    try:
        rating = service.create_rating(
            db, spot_id,
            stars=body.stars, skill_level=body.skill_level, sport=body.sport,
            conditions=body.conditions,
            author_name=account.display_name if account else "Anonym",
            author_email=account.email if account else None,
            app_user_id=account.id if account else None, ip_hash=ip_hash(request),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RatingOut.of(rating)


@router.get("/spots/{spot_id}/ratings")
def get_ratings(spot_id: uuid.UUID, db: Session = Depends(get_db), account: AppUser | None = Depends(optional_account)) -> dict:
    try:
        rows, aggregate = service.list_ratings(db, spot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    votes = service.upvote_states(db, "rating", [r.id for r in rows], account.id if account else None)
    return {"items": [RatingOut.of(r, votes.get(r.id)) for r in rows], "aggregate": aggregate}


# --- tips ------------------------------------------------------------------

@router.post("/spots/{spot_id}/tips", status_code=201)
def post_tip(
    spot_id: uuid.UUID,
    body: TipIn,
    request: Request,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
    account: AppUser | None = Depends(optional_account),
) -> TipOut:
    check_honeypot(body.website)
    enforce(limiter, request, "tip", limit=LIMITS["tip"][0], window=LIMITS["tip"][1])
    try:
        tip = service.create_tip(
            db, spot_id, body=body.body, title=body.title,
            author_name=account.display_name if account else "Anonym",
            author_email=account.email if account else None, parent_id=body.parent_id,
            app_user_id=account.id if account else None,
            ip_hash=ip_hash(request),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TipOut.of(tip)


@router.get("/spots/{spot_id}/tips")
def get_tips(spot_id: uuid.UUID, db: Session = Depends(get_db), account: AppUser | None = Depends(optional_account)) -> dict:
    try:
        rows = service.list_tips(db, spot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    votes = service.upvote_states(db, "tip", [t.id for t in rows], account.id if account else None)
    return {"items": [TipOut.of(t, votes.get(t.id)) for t in rows]}


@router.put("/community/comments/{kind}/{comment_id}/upvote")
def put_upvote(kind: str, comment_id: uuid.UUID, request: Request, db: Session = Depends(get_db), limiter: RateLimiter = Depends(get_rate_limiter), account: AppUser = Depends(current_account)) -> dict:
    if kind not in {"tip", "rating"}:
        raise HTTPException(status_code=404, detail="Kommentar nicht gefunden.")
    enforce(limiter, request, "upvote", limit=LIMITS["upvote"][0], window=LIMITS["upvote"][1])
    try:
        return service.set_upvote(db, kind, comment_id, account.id, True)
    except LookupError:
        raise HTTPException(status_code=404, detail="Kommentar nicht gefunden.")


@router.delete("/community/comments/{kind}/{comment_id}/upvote")
def delete_upvote(kind: str, comment_id: uuid.UUID, request: Request, db: Session = Depends(get_db), limiter: RateLimiter = Depends(get_rate_limiter), account: AppUser = Depends(current_account)) -> dict:
    if kind not in {"tip", "rating"}:
        raise HTTPException(status_code=404, detail="Kommentar nicht gefunden.")
    enforce(limiter, request, "upvote", limit=LIMITS["upvote"][0], window=LIMITS["upvote"][1])
    try:
        return service.set_upvote(db, kind, comment_id, account.id, False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Kommentar nicht gefunden.")


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
    review: bool = Form(default=False),
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

    try:
        data = await read_upload_limited(
            file,
            HERO_MAX_BYTES if kind == "hero_candidate" else GALLERY_MAX_BYTES,
        )
        # Validate the original, then re-encode (downscale + AVIF/WebP) so a large
        # heavy upload is accepted but only a small optimised file is stored.
        if kind == "hero_candidate":
            await run_in_threadpool(validate_hero_image, data, file.content_type)
            encoded = await run_in_threadpool(
                reencode_image_set,
                data, max_width=HERO_OUT_MAX_WIDTH, quality=HERO_OUT_QUALITY
            )
        else:
            await run_in_threadpool(validate_gallery_image, data, file.content_type)
            encoded = await run_in_threadpool(
                reencode_image_set,
                data, max_width=GALLERY_OUT_MAX_WIDTH, quality=GALLERY_OUT_QUALITY
            )
    except HeroImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    settings = get_settings()
    image_id = uuid.uuid4()
    acquire_image_set_lock(db, encoded)
    try:
        url = await run_in_threadpool(
            save_spot_image_set,
            spot_id, image_id, encoded,
            media_dir=settings.media_dir, url_prefix=settings.media_url_prefix,
        )
    except PartialImageSetError as exc:
        db.rollback()
        schedule_media_gc(db, exc.canonical_url)
        raise
    except Exception:
        db.rollback()
        raise
    register_media_reference(db, url)
    # gallery = post-moderation (visible now) unless the uploader explicitly
    # asked for review (the standalone "add a photo" form, decoupled from the
    # rating/tip composer); hero_candidate always awaits approval.
    status = "pending" if (kind == "hero_candidate" or review) else "approved"
    try:
        image = service.create_image_record(
            db, spot_id,
            url=url, kind=kind, width=encoded.width, height=encoded.height, status=status,
            license_version=IMAGE_LICENSE_VERSION,
            license_accepted_at=datetime.now(timezone.utc),
            credit=credit, ip_hash=ip_hash(request),
        )
    except Exception:
        db.rollback()
        purge_if_unreferenced(db, url)
        raise
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
