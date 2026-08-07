"""Media-picker infrastructure: the duplicate-usage index, the provider search
cache and the per-provider request budget.

All three live in Postgres rather than Redis. Redis is configured but optional
here — ``app.live.cache`` is deliberately fail-open (a dead cache is a miss),
and the Vercel deployment has no Redis instance at all. A budget counter that
fails open cannot stop an Unsplash overrun, and one that fails closed would
block the picker outright; Postgres is the one store every deployment mode
already depends on.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MediaUsage(Base, TimestampMixin):
    """Which provider photo is used where.

    The same Unsplash photo on a dozen spots destroys the catalogue's
    credibility, so the picker queries this index while searching and marks
    already-used results in the grid. ``external_id`` is the provider's own id,
    which is why rows without one (uploads, legacy images) cannot participate in
    duplicate detection and are excluded from the unique index.
    """

    __tablename__ = "media_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # spot | region
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # hero | gallery

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('spot', 'region')", name="ck_media_usage_entity_type"
        ),
        CheckConstraint("role IN ('hero', 'gallery')", name="ck_media_usage_role"),
        # Partial: in Postgres NULLs never conflict, so a plain unique index over
        # a nullable external_id would enforce nothing at all.
        Index(
            "uq_media_usage_photo_placement",
            "provider",
            "external_id",
            "entity_type",
            "entity_id",
            "role",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_media_usage_entity", "entity_type", "entity_id"),
        Index("ix_media_usage_photo", "provider", "external_id"),
    )


class MediaSearchCache(Base):
    """Normalised provider search responses, keyed by provider+query+page+role.

    Unsplash's demo tier allows 50 requests per hour, so this is a functional
    prerequisite rather than an optimisation: without it, opening the picker a
    dozen times exhausts the hour.
    """

    __tablename__ = "media_search_cache"

    cache_key: Mapped[str] = mapped_column(String(400), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (Index("ix_media_search_cache_expires", "expires_at"),)


class MediaProviderBudget(Base):
    """Upstream requests per provider and clock hour.

    Incremented with ``INSERT … ON CONFLICT DO UPDATE`` so concurrent function
    invocations cannot lose a count. One row per hour bucket; old rows are swept
    with the expired cache entries.
    """

    __tablename__ = "media_provider_budget"

    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint("request_count >= 0", name="ck_media_budget_count"),
    )


__all__ = ["MediaUsage", "MediaSearchCache", "MediaProviderBudget"]
