"""Operator-notification service (admin dashboard badge).

Notifications are created from community events that need an operator's
attention (see ``notify`` callers in ``app.community.service``) and read/cleared
from the admin UI. ``read_at`` NULL = unread.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import AdminNotification


def notify(db: Session, *, type: str, message: str, spot_id=None) -> AdminNotification:
    """Record an operator notification. Best-effort — callers wrap it so a
    notification failure never blocks the underlying community write."""
    n = AdminNotification(type=type, message=message, spot_id=spot_id)
    db.add(n)
    db.flush()
    return n


def unread_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AdminNotification)
            .where(AdminNotification.read_at.is_(None))
        )
        or 0
    )


def list_recent(db: Session, *, limit: int = 30) -> list[AdminNotification]:
    """Newest first — unread naturally sort in with everything else; the UI
    styles unread by ``read_at``."""
    return list(
        db.scalars(
            select(AdminNotification)
            .order_by(AdminNotification.created_at.desc())
            .limit(limit)
        ).all()
    )


def mark_read(db: Session, notification_id) -> AdminNotification:
    n = db.get(AdminNotification, notification_id)
    if n is None:
        raise LookupError(f"unknown notification {notification_id}")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(n)
    return n


def mark_all_read(db: Session) -> int:
    result = db.execute(
        update(AdminNotification)
        .where(AdminNotification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount or 0


def view(n: AdminNotification) -> dict:
    return {
        "id": str(n.id),
        "type": n.type,
        "message": n.message,
        "spot_id": str(n.spot_id) if n.spot_id else None,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat(),
    }
