"""Kanban board tasks for the admin overview.

A tiny to-do the operator drags between "open" and "done". Not user-facing.
"""

import uuid

from sqlalchemy import CheckConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BoardTask(Base, TimestampMixin):
    __tablename__ = "board_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'open'")
    )  # open | done
    author: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        CheckConstraint("status IN ('open', 'done')", name="ck_board_tasks_status"),
    )
