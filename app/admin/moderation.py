"""Moderation service (Sprint D): the review queue and the decision actions.

Every decision writes a :class:`app.models.ModerationAudit` row (actor = the
logged-in admin/curator's email) and commits. Approvals reuse the existing admin
write path — submissions become **draft** spots via ``admin_spots.create_spot``;
hero candidates are promoted via ``admin_spots.manage_spot_image`` — so nothing
goes live without passing the normal readiness/go-live flow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin import spots as admin_spots
from app.media import IMAGE_LICENSE_VERSION
from app.models import (
    ImageReport,
    LocalTip,
    ModerationAudit,
    SpotImage,
    SpotRating,
    SpotSubmission,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_moderation(
    db: Session, *, actor: str | None, action: str, target_type: str, target_id, note: str | None = None
) -> ModerationAudit:
    entry = ModerationAudit(
        actor=actor, action=action, target_type=target_type,
        target_id=target_id, note=note,
    )
    db.add(entry)
    db.flush()
    return entry


# --- queue -----------------------------------------------------------------

def review_counts(db: Session) -> dict[str, int]:
    """The five review-queue counters (also folded into ``/admin/overview``)."""
    def _count(stmt) -> int:
        return int(db.scalar(stmt) or 0)

    return {
        "submissions_pending": _count(
            select(func.count()).select_from(SpotSubmission).where(SpotSubmission.status == "pending")
        ),
        "hero_candidates_pending": _count(
            select(func.count()).select_from(SpotImage).where(
                SpotImage.kind == "hero_candidate", SpotImage.status == "pending"
            )
        ),
        "gallery_images_pending": _count(
            select(func.count()).select_from(SpotImage).where(
                SpotImage.kind == "gallery", SpotImage.status == "pending"
            )
        ),
        "reported_images": _count(
            select(func.count()).select_from(SpotImage).where(SpotImage.report_count > 0)
        ),
        "flagged_tips": _count(
            select(func.count()).select_from(LocalTip).where(LocalTip.flagged.is_(True))
        ),
        "flagged_ratings": _count(
            select(func.count()).select_from(SpotRating).where(SpotRating.flagged.is_(True))
        ),
    }


def list_spot_tips(db: Session, spot_id) -> list[dict]:
    """Every comment on a spot — regardless of status — for per-spot
    moderation. Chronological so the frontend can nest replies under their
    parent by ``parent_id``. Unlike the review queue this includes ``hidden``
    tips (so they can be restored) and is scoped to one spot.
    """
    tips = db.scalars(
        select(LocalTip)
        .where(LocalTip.spot_id == spot_id)
        .order_by(LocalTip.created_at.asc())
    ).all()
    return [_tip_view(t) for t in tips]


def review_queue(db: Session) -> dict[str, Any]:
    counts = review_counts(db)

    submissions = db.scalars(
        select(SpotSubmission)
        .where(SpotSubmission.status == "pending")
        .order_by(SpotSubmission.created_at.desc())
    ).all()
    hero_candidates = db.scalars(
        select(SpotImage)
        .where(SpotImage.kind == "hero_candidate", SpotImage.status == "pending")
        .order_by(SpotImage.created_at.desc())
    ).all()
    pending_gallery_images = db.scalars(
        select(SpotImage)
        .where(SpotImage.kind == "gallery", SpotImage.status == "pending")
        .order_by(SpotImage.created_at.desc())
    ).all()
    reported = db.scalars(
        select(SpotImage)
        .where(SpotImage.report_count > 0)
        .order_by(SpotImage.report_count.desc())
    ).all()
    # Include hidden rows so moderation decisions remain reversible in the same
    # workflow instead of requiring a spot-specific maintenance route.
    tips = db.scalars(
        select(LocalTip)
        .where(LocalTip.status.in_(("published", "hidden")))
        .order_by(LocalTip.flagged.desc(), LocalTip.created_at.desc())
        .limit(100)
    ).all()
    ratings = db.scalars(
        select(SpotRating)
        .where(SpotRating.status.in_(("published", "hidden")))
        .order_by(SpotRating.flagged.desc(), SpotRating.created_at.desc())
        .limit(100)
    ).all()

    return {
        "counts": counts,
        "submissions": [_submission_view(s) for s in submissions],
        "hero_candidates": [_image_view(i) for i in hero_candidates],
        "pending_gallery_images": [_image_view(i) for i in pending_gallery_images],
        "reported_images": [_image_view(i) for i in reported],
        "tips": [_tip_view(t) for t in tips],
        "ratings": [_rating_view(r) for r in ratings],
    }


def _submission_view(s: SpotSubmission) -> dict:
    return {
        "id": str(s.id),
        "name": (s.payload or {}).get("name"),
        "submitter_name": s.submitter_name,
        "status": s.status,
        "created_at": s.created_at.isoformat(),
        "payload": s.payload,
    }


def _image_view(i: SpotImage) -> dict:
    return {
        "id": str(i.id), "spot_id": str(i.spot_id), "url": i.url, "kind": i.kind,
        "credit": i.credit, "status": i.status, "report_count": i.report_count,
        "created_at": i.created_at.isoformat(),
    }


def _tip_view(t: LocalTip) -> dict:
    return {
        "id": str(t.id), "spot_id": str(t.spot_id), "body": t.body,
        "author_name": t.author_name, "title": t.title, "status": t.status, "flagged": t.flagged,
        "parent_id": str(t.parent_id) if t.parent_id else None,
        "created_at": t.created_at.isoformat(),
    }


def _rating_view(r: SpotRating) -> dict:
    return {
        "id": str(r.id), "spot_id": str(r.spot_id), "stars": r.stars,
        "conditions": r.conditions, "author_name": r.author_name,
        "status": r.status, "flagged": r.flagged,
        "created_at": r.created_at.isoformat(),
    }


# --- submissions -----------------------------------------------------------

class IncompleteSubmissionError(ValueError):
    """The proposal (plus any admin completion) is not yet a valid spot — e.g. a
    name-only account submission approved without region/coordinates. Carries a
    human message naming the missing/invalid fields (→ 422 at the API)."""


# Submission-payload field → operator-facing German label, for error messages.
_FIELD_LABELS = {
    "name": "Name",
    "region_id": "Region",
    "lat": "Breitengrad",
    "lon": "Längengrad",
    "sports": "Sportarten",
    "level": "Level",
    "water_character": "Wassercharakter",
    "style": "Stil",
    "facilities": "Ausstattung",
    "facing": "Ausrichtung",
}


def _incomplete_message(exc: Any) -> str:
    """Turn a pydantic ValidationError into 'Zum Anlegen fehlen oder sind
    ungültig: Region, Koordinaten.' rather than a raw error dump."""
    fields: list[str] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        key = str(loc[0]) if loc else ""
        label = _FIELD_LABELS.get(key, key or "Feld")
        if label not in fields:
            fields.append(label)
    joined = ", ".join(fields) if fields else "Pflichtangaben"
    return f"Zum Anlegen fehlen oder sind ungültig: {joined}."


def approve_submission(
    db: Session,
    submission_id,
    *,
    actor: str,
    client=None,
    completion: dict | None = None,
    allow_duplicate: bool = False,
) -> Any:
    """Create a **draft** spot from the proposal and link it back.

    ``completion`` lets an admin fill in fields the submitter did not provide
    (a name-only account proposal has just ``name``). It is merged **over** the
    stored payload, then the result must be a valid :class:`SpotCreate`; if not,
    an :class:`IncompleteSubmissionError` names what is still missing.
    """
    from pydantic import ValidationError

    from app.schemas.admin import SpotCreate

    sub = db.scalar(
        select(SpotSubmission)
        .where(SpotSubmission.id == submission_id)
        .with_for_update()
    )
    if sub is None:
        raise LookupError("submission not found")
    if sub.status != "pending":
        raise ValueError(f"submission already {sub.status}")

    merged = {**(sub.payload or {}), **(completion or {})}
    try:
        data = SpotCreate.model_validate(merged).to_data()
    except ValidationError as exc:
        raise IncompleteSubmissionError(_incomplete_message(exc)) from exc
    spot = admin_spots.create_spot(
        data,
        db=db,
        client=None,
        actor=actor,
        commit=False,
        allow_duplicate=allow_duplicate,
    )

    sub.status = "merged"
    sub.resulting_spot_id = spot.id
    sub.reviewed_by = actor
    sub.reviewed_at = _now()
    record_moderation(
        db, actor=actor, action="submission_approve",
        target_type="submission", target_id=sub.id, note=f"spot {spot.id}",
    )
    db.commit()
    db.refresh(spot)
    if client is not None:
        from app.admin.jobs import trigger_era5_job

        try:
            trigger_era5_job(spot.id, db=db, client=client)
        except Exception:
            db.rollback()
    return spot


def reject_submission(db: Session, submission_id, *, actor: str, note: str | None = None) -> None:
    sub = db.scalar(
        select(SpotSubmission)
        .where(SpotSubmission.id == submission_id)
        .with_for_update()
    )
    if sub is None:
        raise LookupError("submission not found")
    if sub.status != "pending":
        raise ValueError(f"submission already {sub.status}")
    sub.status = "rejected"
    sub.review_note = note
    sub.reviewed_by = actor
    sub.reviewed_at = _now()
    record_moderation(
        db, actor=actor, action="submission_reject",
        target_type="submission", target_id=sub.id, note=note,
    )
    db.commit()


# --- images ----------------------------------------------------------------

def _get_image(db: Session, image_id) -> SpotImage:
    img = db.scalar(
        select(SpotImage).where(SpotImage.id == image_id).with_for_update()
    )
    if img is None:
        raise LookupError("image not found")
    return img


def approve_image(db: Session, image_id, *, actor: str) -> SpotImage:
    """Approve a pending image. Hero candidates are promoted to the spot's
    hero image (see `approve_hero_image`); a plain pending gallery photo
    (uploaded via the standalone "add a photo" form, decoupled from the
    composer) is simply marked approved and becomes publicly visible."""
    img = _get_image(db, image_id)
    if img.status != "pending":
        raise ValueError(f"image cannot be approved from {img.status}")
    if img.kind == "hero_candidate":
        return approve_hero_image(db, image_id, actor=actor)
    img.status = "approved"
    img.reviewed_by = actor
    img.reviewed_at = _now()
    record_moderation(
        db, actor=actor, action="image_approve",
        target_type="image", target_id=img.id,
    )
    db.commit()
    db.refresh(img)
    return img


def approve_hero_image(db: Session, image_id, *, actor: str) -> SpotImage:
    """Promote a hero candidate to the spot's hero image (``spot.image`` JSONB)."""
    img = _get_image(db, image_id)
    if img.status != "pending":
        raise ValueError(f"hero image cannot be approved from {img.status}")
    admin_spots.manage_spot_image(
        img.spot_id,
        {
            "url": img.url,
            "source": "user_upload",
            "license": img.license_version or IMAGE_LICENSE_VERSION,
            "credit": (img.credit or "Community").strip() or "Community",
            # The uploader's photo lives in our own storage; provenance is the
            # consent record on this row, not an external provider.
            "provider": "community",
            "delivery": "hosted",
            "width": img.width,
            "height": img.height,
            "role": "hero",
        },
        db=db, actor=actor,
    )
    img.status = "published_hero"
    img.reviewed_by = actor
    img.reviewed_at = _now()
    record_moderation(
        db, actor=actor, action="image_approve",
        target_type="image", target_id=img.id,
    )
    db.commit()
    db.refresh(img)
    return img


def reject_image(db: Session, image_id, *, actor: str, note: str | None = None) -> SpotImage:
    img = _get_image(db, image_id)
    if img.status != "pending":
        raise ValueError(f"image cannot be rejected from {img.status}")
    img.status = "rejected"
    img.reviewed_by = actor
    img.reviewed_at = _now()
    record_moderation(
        db, actor=actor, action="image_reject",
        target_type="image", target_id=img.id, note=note,
    )
    db.commit()
    db.refresh(img)
    return img


def remove_image(db: Session, image_id, *, actor: str, note: str | None = None) -> SpotImage:
    img = _get_image(db, image_id)
    if img.status not in ("approved", "published_hero"):
        raise ValueError(f"image cannot be removed from {img.status}")
    img.status = "removed"
    img.reviewed_by = actor
    img.reviewed_at = _now()
    record_moderation(
        db, actor=actor, action="image_remove",
        target_type="image", target_id=img.id, note=note,
    )
    db.commit()
    db.refresh(img)
    return img


def dismiss_reports(db: Session, image_id, *, actor: str) -> SpotImage:
    img = _get_image(db, image_id)
    if img.report_count <= 0:
        raise ValueError("image has no reports")
    img.report_count = 0
    # clear the underlying report rows too
    for rep in db.scalars(select(ImageReport).where(ImageReport.image_id == img.id)).all():
        db.delete(rep)
    record_moderation(
        db, actor=actor, action="image_dismiss_reports",
        target_type="image", target_id=img.id,
    )
    db.commit()
    db.refresh(img)
    return img


# --- tips & ratings --------------------------------------------------------

def set_tip_status(db: Session, tip_id, status: str, *, actor: str) -> LocalTip:
    tip = db.scalar(select(LocalTip).where(LocalTip.id == tip_id).with_for_update())
    if tip is None:
        raise LookupError("tip not found")
    expected = "published" if status == "hidden" else "hidden"
    if tip.status != expected:
        raise ValueError(f"tip cannot change from {tip.status} to {status}")
    tip.status = status
    if status != "hidden":
        tip.flagged = False
    record_moderation(
        db, actor=actor, action=f"tip_{'hide' if status == 'hidden' else 'restore'}",
        target_type="tip", target_id=tip.id,
    )
    db.commit()
    db.refresh(tip)
    return tip


def set_rating_status(db: Session, rating_id, status: str, *, actor: str) -> SpotRating:
    rating = db.scalar(
        select(SpotRating).where(SpotRating.id == rating_id).with_for_update()
    )
    if rating is None:
        raise LookupError("rating not found")
    expected = "published" if status == "hidden" else "hidden"
    if rating.status != expected:
        raise ValueError(f"rating cannot change from {rating.status} to {status}")
    rating.status = status
    if status != "hidden":
        rating.flagged = False
    record_moderation(
        db, actor=actor, action=f"rating_{'hide' if status == 'hidden' else 'restore'}",
        target_type="rating", target_id=rating.id,
    )
    db.commit()
    db.refresh(rating)
    return rating
