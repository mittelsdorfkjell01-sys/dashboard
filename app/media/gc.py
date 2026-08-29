"""Race-safe, retryable garbage collection for hosted image objects."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.media import storage
from app.models import MediaGarbageCandidate, MediaGcState

_CONTENT_DIGEST_RE = re.compile(r"/images/[0-9a-f]{2}/([0-9a-f]{64})-responsive-")
_BLOB_MEDIA_PREFIXES = ("images/", "spots/", "regions/")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def media_lock_identity(value: str) -> str:
    """Use the content digest when present, otherwise the complete URL."""
    match = _CONTENT_DIGEST_RE.search(value)
    return match.group(1) if match else value


def _advisory_key(value: str) -> int:
    raw = hashlib.sha256(media_lock_identity(value).encode("utf-8")).digest()[:8]
    return int.from_bytes(raw, byteorder="big", signed=True)


def acquire_media_lock(db: Session, value: str) -> None:
    """Serialize one asset's storage mutation with its DB reference change."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": _advisory_key(value)},
    )


def acquire_image_set_lock(db: Session, encoded) -> None:
    from app.media.hero import image_set_digest

    acquire_media_lock(db, image_set_digest(encoded))


def register_media_reference(
    db: Session,
    url: str,
    *,
    require_exists: bool = False,
) -> str:
    """Cancel a pending deletion inside the transaction adding the reference."""
    if storage.is_owned_url(url):
        url = storage.canonical_image_url(url)
        acquire_media_lock(db, url)
        if require_exists and not storage.object_exists(url):
            raise ValueError("Das gespeicherte Bild ist nicht mehr vorhanden.")
        cancel_media_gc(db, url)
    return url


def cancel_media_gc(db: Session, url: str) -> bool:
    candidate = db.scalar(
        select(MediaGarbageCandidate).where(
            MediaGarbageCandidate.url_hash == _url_hash(url)
        )
    )
    if candidate is None:
        return False
    db.delete(candidate)
    return True


def schedule_media_gc(
    db: Session,
    url: str | None,
    *,
    reference_url: str | None = None,
    delete_set: bool = True,
    grace_hours: int | None = None,
    check_references: bool = True,
    commit: bool = True,
) -> bool:
    """Persist a delayed candidate, normally after a locked reference check.

    Provider audits may pass ``check_references=False`` after taking a bulk
    snapshot; collection always performs the authoritative locked recheck.
    """
    if not url or not storage.is_owned_url(url):
        return False
    reference_url = reference_url or url
    acquire_media_lock(db, reference_url)

    if check_references:
        # Local import avoids a lifecycle↔GC import cycle.
        from app.media.lifecycle import image_url_is_referenced

        if image_url_is_referenced(db, reference_url):
            cancel_media_gc(db, url)
            if commit:
                db.commit()
            return False

    settings = get_settings()
    delay = settings.media_gc_grace_hours if grace_hours is None else grace_hours
    due = datetime.now(timezone.utc) + timedelta(hours=max(1, delay))
    digest = _url_hash(url)
    candidate = db.scalar(
        select(MediaGarbageCandidate)
        .where(MediaGarbageCandidate.url_hash == digest)
        .with_for_update()
    )
    if candidate is None:
        candidate = MediaGarbageCandidate(
            url_hash=digest,
            url=url,
            reference_url=reference_url,
            delete_set=delete_set,
            not_before=due,
        )
        db.add(candidate)
    else:
        candidate.reference_url = reference_url
        candidate.delete_set = candidate.delete_set or delete_set
        if candidate.last_error is None:
            candidate.not_before = min(candidate.not_before, due)
    if commit:
        db.commit()
    return True


def collect_media_garbage(
    db: Session,
    *,
    limit: int | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Delete due candidates after a locked second reference check."""
    settings = get_settings()
    current = now or datetime.now(timezone.utc)
    batch_size = limit or settings.media_gc_batch_size
    ids = list(
        db.scalars(
            select(MediaGarbageCandidate.id)
            .where(MediaGarbageCandidate.not_before <= current)
            .order_by(
                MediaGarbageCandidate.not_before,
                MediaGarbageCandidate.created_at,
            )
            .limit(batch_size)
        ).all()
    )
    result = {"due": len(ids), "deleted": 0, "cancelled": 0, "failed": 0}

    from app.media.lifecycle import image_url_is_referenced

    for candidate_id in ids:
        # Every path that mutates an image follows this exact order. Reading the
        # URL first is harmless and prevents a collector/upload lock inversion.
        reference_url = db.scalar(
            select(MediaGarbageCandidate.reference_url).where(
                MediaGarbageCandidate.id == candidate_id
            )
        )
        if reference_url is None:
            db.rollback()
            continue
        acquire_media_lock(db, reference_url)
        candidate = db.scalar(
            select(MediaGarbageCandidate)
            .where(MediaGarbageCandidate.id == candidate_id)
            .with_for_update(skip_locked=True)
        )
        if candidate is None:
            db.rollback()
            continue
        if image_url_is_referenced(db, candidate.reference_url):
            db.delete(candidate)
            db.commit()
            result["cancelled"] += 1
            continue
        try:
            storage.delete_candidate_strict(
                candidate.url,
                delete_set=candidate.delete_set,
                media_dir=settings.media_dir,
                url_prefix=settings.media_url_prefix,
            )
        except Exception as exc:
            candidate.attempts += 1
            candidate.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            backoff_hours = min(24 * 7, 2 ** min(candidate.attempts, 10))
            candidate.not_before = current + timedelta(hours=backoff_hours)
            db.commit()
            result["failed"] += 1
            continue
        db.delete(candidate)
        db.commit()
        result["deleted"] += 1
    return result


def audit_blob_orphans(
    db: Session,
    *,
    limit: int | None = None,
    now: datetime | None = None,
) -> dict[str, int | bool]:
    """Scan one resumable Vercel Blob page and enqueue old unreferenced objects."""
    settings = get_settings()
    if settings.media_backend != "blob":
        return {"scanned": 0, "queued": 0, "has_more": False}
    acquire_media_lock(db, "media-gc-blob-scan")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        hours=settings.media_gc_grace_hours
    )
    from app.media.lifecycle import active_image_urls

    referenced_urls = active_image_urls(db)
    scanned = 0
    queued = 0
    has_more = False
    for prefix in _BLOB_MEDIA_PREFIXES:
        state_key = f"blob:{prefix.rstrip('/')}"
        state = db.get(MediaGcState, state_key)
        if state is None:
            state = MediaGcState(backend=state_key, cursor=None)
            db.add(state)
            db.flush()
        page = storage.list_blob_objects(
            prefix=prefix,
            limit=limit or settings.media_blob_scan_batch_size,
            cursor=state.cursor,
        )
        scanned += len(page["items"])
        has_more = has_more or bool(page.get("has_more"))
        # One canonical candidate represents its whole deterministic responsive
        # set, even if the provider page happens to contain only a derivative.
        canonical_urls = {
            storage.canonical_image_url(item["url"])
            for item in page["items"]
            if item["uploaded_at"] <= cutoff
            and storage.canonical_image_url(item["url"]) not in referenced_urls
        }
        for canonical_url in canonical_urls:
            if schedule_media_gc(
                db,
                canonical_url,
                reference_url=canonical_url,
                delete_set=True,
                grace_hours=1,
                check_references=False,
                commit=False,
            ):
                queued += 1
        state.cursor = page.get("cursor") if page.get("has_more") else None
    db.commit()
    return {
        "scanned": scanned,
        "queued": queued,
        "has_more": has_more,
    }
