"""Operator-facing notifications for the admin dashboard.

Distinct from ``Notification`` (which dispatches community *watch* alerts like
``good_window`` to users). These are things that need an operator's attention —
a new spot submission, a reported image, a flagged tip — surfaced as a badge in
the admin chrome. ``read_at`` NULL = unread.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AdminNotification(Base, TimestampMixin):
    __tablename__ = "admin_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # e.g. "submission" | "reported_image" | "flagged_tip" | "flagged_rating"
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="SET NULL")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
