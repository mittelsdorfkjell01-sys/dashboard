"""Team notes / announcements for the operator back office.

Short messages an admin/moderator posts for the team; rendered as tiles on the
admin overview. Not user-facing.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamNote(Base):
    __tablename__ = "team_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    author: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Board priority: "normal" (default) | "important". Important notes get a red
    # stroke and sort to the top of the overview board.
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'normal'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
