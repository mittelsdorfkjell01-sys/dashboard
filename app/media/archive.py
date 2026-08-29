"""Retention and compressed evidence snapshots for retired image rows."""

from __future__ import annotations

import hashlib
import json
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ImageReport,
    ModerationAudit,
    SpotImage,
    SpotImageArchive,
)

TERMINAL_IMAGE_STATUSES = ("rejected", "removed")

# Deliberately excludes submitter_email, app_user_id and ip_hash. Those fields
# have no long-term licence value and are governed by the shorter UGC privacy
# retention window.
IMAGE_EVIDENCE_FIELDS = (
    "id",
    "spot_id",
    "region_id",
    "url",
    "kind",
    "width",
    "height",
    "source",
    "credit",
    "license_version",
    "license_accepted_at",
    "license_name",
    "license_url",
    "source_url",
    "provider",
    "external_id",
    "credit_url",
    "retrieved_at",
    "delivery",
    "geo_verified",
    "position",
    "status",
    "report_count",
    "reviewed_by",
    "reviewed_at",
    "created_at",
    "updated_at",
)
REPORT_EVIDENCE_FIELDS = ("id", "reason", "note", "created_at", "updated_at")
AUDIT_EVIDENCE_FIELDS = ("id", "actor", "action", "note", "created_at")


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _snapshot_fields(item: Any, fields: Iterable[str]) -> dict[str, Any]:
    snapshot = {
        field: _json_value(getattr(item, field, None)) for field in fields
    }
    return {field: value for field, value in snapshot.items() if value is not None}


def encode_archive_payload(
    image: SpotImage,
    reports: Iterable[ImageReport] = (),
    audits: Iterable[ModerationAudit] = (),
) -> tuple[bytes, str, int]:
    """Return zlib payload, raw JSON SHA-256 and uncompressed byte count."""
    snapshot = {
        "version": 1,
        "image": _snapshot_fields(image, IMAGE_EVIDENCE_FIELDS),
        "reports": [
            _snapshot_fields(report, REPORT_EVIDENCE_FIELDS) for report in reports
        ],
        "moderation": [
            _snapshot_fields(audit, AUDIT_EVIDENCE_FIELDS) for audit in audits
        ],
    }
    raw = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return zlib.compress(raw, level=9), hashlib.sha256(raw).hexdigest(), len(raw)


def decode_archive_payload(archive: SpotImageArchive) -> dict[str, Any]:
    raw = zlib.decompress(archive.payload)
    if hashlib.sha256(raw).hexdigest() != archive.payload_sha256:
        raise ValueError(f"archive checksum mismatch: {archive.id}")
    return json.loads(raw)


def archive_retired_images(
    db: Session,
    *,
    retention_days: int = 180,
    limit: int = 250,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Archive a bounded batch of old rejected/removed image rows."""
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    if limit < 1:
        raise ValueError("limit must be positive")
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=retention_days)
    retired_at = SpotImage.updated_at
    statement = (
        select(SpotImage)
        .where(
            SpotImage.status.in_(TERMINAL_IMAGE_STATUSES),
            retired_at < cutoff,
        )
        .order_by(retired_at, SpotImage.id)
        .limit(limit)
    )
    if not dry_run:
        statement = statement.with_for_update(skip_locked=True)
    rows = list(db.scalars(statement).all())

    result = {
        "eligible": len(rows),
        "archived": 0,
        "skipped": 0,
        "original_bytes": 0,
        "compressed_bytes": 0,
    }
    for image in rows:
        if db.get(SpotImageArchive, image.id) is not None:
            result["skipped"] += 1
            continue
        reports = db.scalars(
            select(ImageReport)
            .where(ImageReport.image_id == image.id)
            .order_by(ImageReport.created_at, ImageReport.id)
        ).all()
        audits = db.scalars(
            select(ModerationAudit)
            .where(
                ModerationAudit.target_type == "image",
                ModerationAudit.target_id == image.id,
            )
            .order_by(ModerationAudit.created_at, ModerationAudit.id)
        ).all()
        payload, checksum, original_bytes = encode_archive_payload(
            image, reports, audits
        )
        result["original_bytes"] += original_bytes
        result["compressed_bytes"] += len(payload)
        if dry_run:
            continue
        entity_id = image.spot_id or image.region_id
        db.add(
            SpotImageArchive(
                id=image.id,
                entity_type="spot" if image.spot_id else "region",
                entity_id=entity_id,
                status=image.status,
                created_at=image.created_at,
                payload=payload,
                payload_sha256=checksum,
                original_bytes=original_bytes,
                compressed_bytes=len(payload),
            )
        )
        db.delete(image)
        result["archived"] += 1
    if not dry_run:
        db.commit()
    return result


def archive_view(db: Session, image_id) -> dict[str, Any] | None:
    archive = db.get(SpotImageArchive, image_id)
    if archive is None:
        return None
    return {
        "id": str(archive.id),
        "entity_type": archive.entity_type,
        "entity_id": str(archive.entity_id),
        "status": archive.status,
        "created_at": archive.created_at.isoformat(),
        "archived_at": archive.archived_at.isoformat(),
        "original_bytes": archive.original_bytes,
        "compressed_bytes": archive.compressed_bytes,
        "payload_sha256": archive.payload_sha256,
        "snapshot": decode_archive_payload(archive),
    }
