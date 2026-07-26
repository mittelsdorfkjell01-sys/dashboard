"""Community CRUD + validation (Sprint C).

Each ``create_*`` validates the controlled vocabulary, checks the target spot
exists, and commits. Reads only ever return *published* / visible rows — the
moderation status filtering lives here so every caller is consistent.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.constants import (
    REPORT_REASON,
    VISIBLE_IMAGE_STATUS,
    validate_skill_level,
    validate_sport,
)
from app.community.aggregate import rating_aggregate
from app.models import (
    ImageReport,
    LocalTip,
    Spot,
    SpotImage,
    SpotRating,
    SpotSubmission,
)

_ANON = "Anonym"


def _require_spot(db: Session, spot_id) -> Spot:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    return spot


def spot_exists(db: Session, spot_id) -> bool:
    return db.get(Spot, spot_id) is not None


def count_gallery_images(db: Session, spot_id) -> int:
    """Active (not removed/rejected) gallery images for a spot."""
    from sqlalchemy import func

    return int(
        db.scalar(
            select(func.count())
            .select_from(SpotImage)
            .where(
                SpotImage.spot_id == spot_id,
                SpotImage.kind == "gallery",
                SpotImage.status.notin_(("removed", "rejected")),
            )
        )
        or 0
    )


def _clean_name(name: str | None) -> str:
    return (name or "").strip() or _ANON


def _clean_email(email: str | None) -> str | None:
    email = (email or "").strip()
    return email or None


# --- ratings ---------------------------------------------------------------

def create_rating(
    db: Session,
    spot_id,
    *,
    stars: int,
    skill_level: str,
    sport: str,
    conditions: str,
    author_name: str | None,
    author_email: str | None = None,
    ip_hash: str | None = None,
) -> SpotRating:
    _require_spot(db, spot_id)
    if not isinstance(stars, int) or not (1 <= stars <= 5):
        raise ValueError("stars muss zwischen 1 und 5 liegen.")
    validate_skill_level(skill_level)
    validate_sport(sport)
    if not (conditions and conditions.strip()):
        raise ValueError("Bitte die gefahrenen Bedingungen beschreiben.")
    from app.community.filter import is_flagged

    rating = SpotRating(
        spot_id=spot_id,
        stars=stars,
        skill_level=skill_level,
        sport=sport,
        conditions=conditions.strip(),
        author_name=_clean_name(author_name),
        author_email=_clean_email(author_email),
        flagged=is_flagged(conditions, author_name),
        ip_hash=ip_hash,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def list_ratings(db: Session, spot_id) -> tuple[list[SpotRating], dict]:
    _require_spot(db, spot_id)
    rows = db.scalars(
        select(SpotRating)
        .where(SpotRating.spot_id == spot_id, SpotRating.status == "published")
        .order_by(SpotRating.created_at.desc())
    ).all()
    return list(rows), rating_aggregate(db, spot_id)


# --- tips ------------------------------------------------------------------

def create_tip(
    db: Session,
    spot_id,
    *,
    body: str,
    author_name: str | None,
    author_email: str | None = None,
    parent_id=None,
    ip_hash: str | None = None,
) -> LocalTip:
    _require_spot(db, spot_id)
    if not (body and body.strip()):
        raise ValueError("Der Tipp darf nicht leer sein.")
    if parent_id is not None:
        parent = db.get(LocalTip, parent_id)
        if parent is None or parent.spot_id != spot_id:
            raise ValueError("Der Kommentar, auf den geantwortet wird, existiert nicht.")
        # Single-level threads: a reply to a reply attaches to the top-level
        # comment instead of nesting deeper.
        if parent.parent_id is not None:
            parent_id = parent.parent_id
    from app.community.filter import is_flagged

    tip = LocalTip(
        spot_id=spot_id,
        body=body.strip(),
        author_name=_clean_name(author_name),
        author_email=_clean_email(author_email),
        parent_id=parent_id,
        flagged=is_flagged(body, author_name),
        ip_hash=ip_hash,
    )
    db.add(tip)
    db.commit()
    db.refresh(tip)
    return tip


def list_tips(db: Session, spot_id) -> list[LocalTip]:
    _require_spot(db, spot_id)
    return list(
        db.scalars(
            select(LocalTip)
            .where(LocalTip.spot_id == spot_id, LocalTip.status == "published")
            .order_by(LocalTip.created_at.desc())
        ).all()
    )


# --- submissions -----------------------------------------------------------

def create_submission(
    db: Session,
    *,
    payload: dict,
    submitter_name: str | None,
    submitter_email: str | None = None,
    ip_hash: str | None = None,
) -> SpotSubmission:
    """Validate the payload against the admin create schema but **do not** create a
    spot — only store the proposal as ``pending`` for later review (Sprint D)."""
    from pydantic import ValidationError

    from app.schemas.admin import SpotCreate

    try:
        SpotCreate.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Ungültiger Spot-Vorschlag: {exc.error_count()} Fehler.")

    sub = SpotSubmission(
        payload=payload,
        submitter_name=_clean_name(submitter_name),
        submitter_email=_clean_email(submitter_email),
        ip_hash=ip_hash,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# --- images ----------------------------------------------------------------

def create_image_record(
    db: Session,
    spot_id,
    *,
    url: str,
    kind: str,
    width: int,
    height: int,
    status: str,
    license_version: str,
    license_accepted_at: datetime,
    credit: str | None = None,
    submitter_email: str | None = None,
    ip_hash: str | None = None,
) -> SpotImage:
    image = SpotImage(
        spot_id=spot_id,
        url=url,
        kind=kind,
        width=width,
        height=height,
        source="user_upload",
        credit=(credit or "").strip() or None,
        submitter_email=_clean_email(submitter_email),
        license_version=license_version,
        license_accepted_at=license_accepted_at,
        status=status,
        ip_hash=ip_hash,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def create_commons_image_records(db: Session, spot_id, results: list[dict]) -> list[SpotImage]:
    """Store Wikimedia Commons geosearch hits as gallery images. ``kind`` is
    always ``gallery`` (Commons photos never become hero candidates) and
    ``status`` is ``approved`` outright — an admin explicitly triggered this
    fetch and can hide individual results afterwards, so there's no separate
    review queue for them. license_version/license_accepted_at stay ``None``:
    there was no upload-consent event to date, that's not what these track.

    Skips any result whose source_url is already stored for this spot, so the
    fetch endpoint is safe to call again (e.g. to pick up new Commons uploads)
    without duplicating existing rows.
    """
    _require_spot(db, spot_id)
    existing = set(
        db.scalars(
            select(SpotImage.source_url).where(
                SpotImage.spot_id == spot_id, SpotImage.source_url.isnot(None)
            )
        )
    )
    created: list[SpotImage] = []
    for r in results:
        if r["source_url"] in existing:
            continue
        image = SpotImage(
            spot_id=spot_id,
            url=r["url"],
            kind="gallery",
            width=r.get("width"),
            height=r.get("height"),
            source="wikimedia_commons",
            credit=r.get("credit"),
            license_name=r.get("license_name"),
            license_url=r.get("license_url"),
            source_url=r["source_url"],
            status="approved",
        )
        db.add(image)
        created.append(image)
    if created:
        db.commit()
        for image in created:
            db.refresh(image)
    return created


def list_images(db: Session, spot_id) -> list[SpotImage]:
    _require_spot(db, spot_id)
    return list(
        db.scalars(
            select(SpotImage)
            .where(
                SpotImage.spot_id == spot_id,
                SpotImage.status.in_(VISIBLE_IMAGE_STATUS),
            )
            .order_by(SpotImage.created_at.desc())
        ).all()
    )


def report_image(
    db: Session,
    image_id,
    *,
    reason: str,
    note: str | None = None,
    reporter_email: str | None = None,
    ip_hash: str | None = None,
) -> tuple[ImageReport, SpotImage]:
    image = db.get(SpotImage, image_id)
    if image is None:
        raise LookupError(f"unknown image {image_id}")
    if reason not in REPORT_REASON:
        raise ValueError(f"invalid reason {reason!r}; allowed: {list(REPORT_REASON)}")
    report = ImageReport(
        image_id=image_id,
        reason=reason,
        note=(note or "").strip() or None,
        reporter_email=_clean_email(reporter_email),
        ip_hash=ip_hash,
    )
    image.report_count = (image.report_count or 0) + 1
    db.add(report)
    db.commit()
    db.refresh(image)
    return report, image
