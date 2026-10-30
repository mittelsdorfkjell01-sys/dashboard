"""Editorial review state and field-level source workflow for spots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.audit import record_audit


CONTENT_STATUSES = {"unreviewed", "in_review", "verified", "review_due", "conflict"}
SOURCE_STATUSES = {"unreviewed", "verified", "rejected", "conflict"}

# A reviewed spot needs current evidence for each of these claims.  The age
# window is intentionally field-specific: local safety information needs a
# tighter recheck than stable identity/category facts.
REQUIRED_SOURCE_MAX_AGE_DAYS: dict[str, int] = {
    "location": 730,
    "sports": 730,
    "level": 730,
    "editorial.description": 730,
    "editorial.safety_notice": 365,
}
REVIEW_VALID_DAYS = 365


class ContentReviewError(ValueError):
    def __init__(self, gaps: list[str]):
        super().__init__("content review requirements are incomplete")
        self.gaps = gaps


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _field_present(spot: Any, field_path: str) -> bool:
    if field_path == "location":
        return getattr(spot, "location", None) is not None
    if field_path.startswith("editorial."):
        editorial = getattr(spot, "editorial", None) or {}
        value = editorial.get(field_path.split(".", 1)[1]) if isinstance(editorial, dict) else None
    else:
        value = getattr(spot, field_path, None)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None


def _source_current(source: Any, field_path: str, now: datetime) -> bool:
    checked_at = _utc(getattr(source, "checked_at", None))
    return bool(
        getattr(source, "verification_status", None) == "verified"
        and checked_at is not None
        and checked_at <= now + timedelta(minutes=5)
        and checked_at >= now - timedelta(days=REQUIRED_SOURCE_MAX_AGE_DAYS[field_path])
    )


def content_governance_checklist(spot: Any, *, now: datetime | None = None) -> list[dict]:
    """Return blocking review/source checks compatible with readiness items."""
    now = _utc(now) or datetime.now(timezone.utc)
    sources = list(getattr(spot, "content_sources", None) or [])
    items: list[dict] = []
    for field_path in REQUIRED_SOURCE_MAX_AGE_DAYS:
        present = _field_present(spot, field_path)
        current = any(
            source.field_path == field_path and _source_current(source, field_path, now)
            for source in sources
        )
        items.append({
            "field": f"content.field.{field_path}",
            "severity": "required",
            "ok": present,
            "na": False,
        })
        items.append({
            "field": f"content.source.{field_path}",
            "severity": "required",
            "ok": present and current,
            "na": False,
        })

    if getattr(spot, "editorial_classification", None):
        items.append({
            "field": "content.field.editorial.classification_reason",
            "severity": "required",
            "ok": _field_present(spot, "editorial.classification_reason"),
            "na": False,
        })
    reviewed_at = _utc(getattr(spot, "content_reviewed_at", None))
    review_due_at = _utc(getattr(spot, "content_review_due_at", None))
    status = getattr(spot, "content_status", None) or "unreviewed"
    items.extend([
        {
            "field": "content.sources.no_conflict",
            "severity": "required",
            "ok": not any(
                getattr(source, "verification_status", None) == "conflict"
                for source in sources
            ),
            "na": False,
        },
        {
            "field": "content.status.verified",
            "severity": "required",
            "ok": status == "verified",
            "na": False,
        },
        {
            "field": "content.reviewed_at",
            "severity": "required",
            "ok": reviewed_at is not None,
            "na": False,
        },
        {
            "field": "content.review_due",
            "severity": "required",
            "ok": review_due_at is not None and review_due_at > now,
            "na": False,
        },
    ])
    return items


def content_governance_warnings(spot: Any, *, now: datetime | None = None) -> list[str]:
    now = _utc(now) or datetime.now(timezone.utc)
    sources = list(getattr(spot, "content_sources", None) or [])
    warnings: list[str] = []
    if any(source.verification_status == "conflict" for source in sources):
        warnings.append("content.sources.conflict")
    if any(
        source.field_path in REQUIRED_SOURCE_MAX_AGE_DAYS
        and source.verification_status == "verified"
        and not _source_current(source, source.field_path, now)
        for source in sources
    ):
        warnings.append("content.sources.stale")
    return warnings


def content_attention_flags(spot: Any, *, now: datetime | None = None) -> dict[str, bool]:
    """Stable flags used by the admin work list and its filters."""
    from app.admin.readiness import image_ready

    now = _utc(now) or datetime.now(timezone.utc)
    sources = list(getattr(spot, "content_sources", None) or [])
    due_at = _utc(getattr(spot, "content_review_due_at", None))
    status = getattr(spot, "content_status", None) or "unreviewed"
    source_stale = any(
        source.field_path in REQUIRED_SOURCE_MAX_AGE_DAYS
        and source.verification_status == "verified"
        and not _source_current(source, source.field_path, now)
        for source in sources
    )
    conflict = status == "conflict" or any(
        source.verification_status == "conflict" for source in sources
    )
    incomplete = any(
        item["severity"] == "required" and not item["ok"]
        for item in content_governance_checklist(spot, now=now)
    )
    return {
        "incomplete": incomplete,
        "unreviewed": status == "unreviewed",
        "in_review": status == "in_review",
        "review_due": status == "review_due" or (due_at is not None and due_at <= now),
        "conflict": conflict,
        "stale": source_stale,
        "license": not image_ready(getattr(spot, "image", None)),
    }


def verification_prerequisite_gaps(spot: Any, *, now: datetime | None = None) -> list[str]:
    """Requirements checked before an editor may mark content verified."""
    from app.admin.readiness import image_ready

    gaps = [
        item["field"]
        for item in content_governance_checklist(spot, now=now)
        if not item["ok"]
        and item["field"] not in {
            "content.status.verified", "content.reviewed_at", "content.review_due"
        }
    ]
    if not image_ready(getattr(spot, "image", None)):
        gaps.append("image")
    return gaps


def mark_content_changed(spot: Any, *, fields: list[str] | set[str]) -> bool:
    """Invalidate a completed review after a claim-bearing field changes."""
    relevant = {
        "name", "region_id", "lat", "lon", "sports", "level", "editorial",
        "editorial_classification", "water_type", "bottom_type", "water_character",
        "variant_conditions", "image",
    }
    if not relevant.intersection(fields):
        return False
    if getattr(spot, "content_status", "unreviewed") == "verified":
        spot.content_status = "review_due"
        spot.content_review_due_at = datetime.now(timezone.utc)
        return True
    return False


def _source_state_changed(spot: Any, status: str) -> None:
    if status == "conflict":
        spot.content_status = "conflict"
        spot.content_review_due_at = datetime.now(timezone.utc)
    elif spot.content_status == "verified":
        spot.content_status = "review_due"
        spot.content_review_due_at = datetime.now(timezone.utc)
    elif spot.content_status == "unreviewed":
        spot.content_status = "in_review"


def create_source(spot_id, data: dict, *, db: Session, actor: str) -> Any:
    from app.models import Spot, SpotContentSource

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    checked_at = _utc(data["checked_at"])
    if checked_at is None or checked_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("Prüfdatum darf nicht in der Zukunft liegen.")
    status = data.get("verification_status", "unreviewed")
    source = SpotContentSource(
        spot_id=spot.id,
        field_path=data["field_path"],
        url=str(data["url"]),
        title=data["title"],
        publisher=data.get("publisher"),
        checked_at=checked_at,
        verification_status=status,
        note=data.get("note"),
        created_by=actor,
        reviewed_by=actor if status == "verified" else None,
    )
    db.add(source)
    _source_state_changed(spot, status)
    db.flush()
    record_audit(db, spot.id, "content_source_create", {
        "source_id": str(source.id), "field_path": source.field_path,
        "verification_status": source.verification_status,
    }, actor)
    db.commit()
    db.refresh(source)
    return source


def update_source(spot_id, source_id, data: dict, *, db: Session, actor: str) -> Any:
    from app.models import Spot, SpotContentSource

    spot = db.get(Spot, spot_id)
    source = db.get(SpotContentSource, source_id)
    if spot is None or source is None or source.spot_id != spot.id:
        raise LookupError("content source not found")
    if "checked_at" in data:
        checked_at = _utc(data["checked_at"])
        if checked_at is None or checked_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Prüfdatum darf nicht in der Zukunft liegen.")
        source.checked_at = checked_at
    for field in ("field_path", "url", "title", "publisher", "note"):
        if field in data:
            setattr(source, field, str(data[field]) if field == "url" else data[field])
    if "verification_status" in data:
        source.verification_status = data["verification_status"]
        source.reviewed_by = actor if source.verification_status == "verified" else None
    _source_state_changed(spot, source.verification_status)
    record_audit(db, spot.id, "content_source_update", {
        "source_id": str(source.id), "fields": sorted(data),
        "verification_status": source.verification_status,
    }, actor)
    db.commit()
    db.refresh(source)
    return source


def delete_source(spot_id, source_id, *, db: Session, actor: str) -> None:
    from app.models import Spot, SpotContentSource

    spot = db.get(Spot, spot_id)
    source = db.get(SpotContentSource, source_id)
    if spot is None or source is None or source.spot_id != spot.id:
        raise LookupError("content source not found")
    details = {"source_id": str(source.id), "field_path": source.field_path, "url": source.url}
    db.delete(source)
    _source_state_changed(spot, "unreviewed")
    record_audit(db, spot.id, "content_source_delete", details, actor)
    db.commit()


def set_content_status(spot_id, status: str, *, db: Session, actor: str) -> Any:
    from app.models import Spot

    if status not in CONTENT_STATUSES:
        raise ValueError("Unbekannter Content-Prüfstatus.")
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    previous = spot.content_status
    now = datetime.now(timezone.utc)
    if status == "verified":
        gaps = verification_prerequisite_gaps(spot, now=now)
        if gaps:
            raise ContentReviewError(gaps)
        spot.content_reviewed_at = now
        spot.content_reviewed_by = actor
        spot.content_review_due_at = now + timedelta(days=REVIEW_VALID_DAYS)
    elif status in {"review_due", "conflict"}:
        spot.content_review_due_at = now
    spot.content_status = status
    record_audit(db, spot.id, "content_review", {
        "from": previous, "to": status,
        "reviewed_at": spot.content_reviewed_at.isoformat() if status == "verified" else None,
    }, actor)
    db.commit()
    db.refresh(spot)
    return spot


def list_sources(spot_id, *, db: Session) -> list[Any]:
    from app.models import Spot, SpotContentSource

    if db.get(Spot, spot_id) is None:
        raise LookupError(f"unknown spot {spot_id}")
    return list(db.scalars(
        select(SpotContentSource)
        .where(SpotContentSource.spot_id == spot_id)
        .order_by(SpotContentSource.field_path, SpotContentSource.checked_at.desc())
    ).all())
