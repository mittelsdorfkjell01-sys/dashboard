"""User-generated-content models (Sprint C): ratings, local tips, spot
submissions, images and image reports.

Pseudonymous by design — each carries an ``author``/``submitter`` name and an
optional, non-public email. A nullable ``app_user_id`` links to a public account
and becomes NULL when that account is deleted. ``ip_hash``
holds a salted hash of the client IP for rate-limiting, never the raw address.

Post-moderation: ratings/tips default to ``published`` and are hidden reactively;
hero-candidate images default to ``pending`` and need an admin's approval.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class SpotRating(Base, TimestampMixin):
    __tablename__ = "spot_ratings"

    id: Mapped[uuid.UUID] = _pk()
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False
    )
    stars: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    skill_level: Mapped[str] = mapped_column(String(20), nullable=False)
    sport: Mapped[str] = mapped_column(String(20), nullable=False)
    # Required free text: which conditions were ridden (context for the stars).
    conditions: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)
    author_email: Mapped[str | None] = mapped_column(String(255))  # not public
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'published'")
    )
    flagged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("stars >= 1 AND stars <= 5", name="ck_rating_stars_1_5"),
        CheckConstraint(
            "status IN ('pending', 'published', 'rejected', 'hidden')",
            name="ck_spot_ratings_status",
        ),
        Index("ix_rating_spot", "spot_id"),
        Index("ix_rating_app_user", "app_user_id"),
    )


class LocalTip(Base, TimestampMixin):
    __tablename__ = "local_tips"

    id: Mapped[uuid.UUID] = _pk()
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)
    author_email: Mapped[str | None] = mapped_column(String(255))
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL")
    )
    # A reply points at the comment it answers (same table); top-level comments
    # have ``parent_id = NULL``. CASCADE so deleting a comment removes its
    # replies with it.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("local_tips.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'published'")
    )
    flagged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'published', 'rejected', 'hidden')",
            name="ck_local_tips_status",
        ),
        Index("ix_tip_spot", "spot_id"),
        Index("ix_tip_parent", "parent_id"),
        Index("ix_tip_app_user", "app_user_id"),
    )


class SpotSubmission(Base, TimestampMixin):
    """A user's proposal for a new spot. Stored as ``pending`` — never creates a
    spot until an admin approves it (Sprint D)."""

    __tablename__ = "spot_submissions"

    id: Mapped[uuid.UUID] = _pk()
    # Payload in the admin create_spot schema shape (validated, not applied).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    submitter_name: Mapped[str] = mapped_column(String(120), nullable=False)
    submitter_email: Mapped[str | None] = mapped_column(String(255))
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resulting_spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="SET NULL")
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'merged')",
            name="ck_spot_submissions_status",
        ),
        Index("ix_submission_status", "status"),
        Index("ix_submission_app_user", "app_user_id"),
        Index(
            "uq_submission_resulting_spot",
            "resulting_spot_id",
            unique=True,
            postgresql_where=text("resulting_spot_id IS NOT NULL"),
        ),
    )


class SpotImage(Base, TimestampMixin):
    """A gallery photo or hero candidate, attached to **either** a spot or a
    region. The versioned license the uploader accepted is stored inline for
    provenance.

    The table name predates regions: it started as the community upload store
    for spots, then took Wikimedia Commons results, and from Sprint 1 on it also
    carries the media picker's stock images for both entity types. Renaming it
    would cascade through moderation, reports, the account export and the
    community API for no functional gain, so the name stays and this docstring
    carries the correction.

    Exactly one of ``spot_id`` / ``region_id`` is set (enforced by
    ``ck_spot_images_entity``). Every pre-existing query filters on
    ``spot_id == …``, so region rows are invisible to the community paths
    without any change there.
    """

    __tablename__ = "spot_images"

    id: Mapped[uuid.UUID] = _pk()
    spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=True
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regions.id", ondelete="CASCADE"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # gallery | hero_candidate
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'user_upload'")
    )
    credit: Mapped[str | None] = mapped_column(String(200))  # name or IG handle
    submitter_email: Mapped[str | None] = mapped_column(String(255))
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL")
    )
    # Nullable: images auto-fetched from an external source (Wikimedia Commons)
    # were never "accepted" by an uploader — there's no consent event to date.
    license_version: Mapped[str | None] = mapped_column(String(20))
    license_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The photo's real license/attribution, as reported by the external source
    # (e.g. "CC BY-SA 4.0") — distinct from license_version/license_accepted_at
    # above, which track *our own upload consent flow* for user photos.
    license_name: Mapped[str | None] = mapped_column(String(80))
    license_url: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    # --- media-picker provenance (Sprint 1) --------------------------------
    # ``source`` above is the free-form display origin ("user_upload",
    # "wikimedia_commons"); ``provider`` is the machine slug that the picker and
    # the duplicate index key on. See app.media.image_object.PROVIDERS.
    provider: Mapped[str | None] = mapped_column(String(30))
    external_id: Mapped[str | None] = mapped_column(String(200))
    credit_url: Mapped[str | None] = mapped_column(String(500))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'hosted'")
    )
    geo_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Manual gallery order (drag-to-sort). NULL sorts last, then by created_at —
    # so existing rows keep their current newest-first behaviour until an
    # operator arranges them.
    position: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    report_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "kind IN ('gallery', 'hero_candidate')",
            name="ck_spot_images_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'published_hero', 'rejected', 'removed')",
            name="ck_spot_images_status",
        ),
        CheckConstraint("report_count >= 0", name="ck_spot_images_report_count"),
        CheckConstraint(
            "(spot_id IS NOT NULL)::int + (region_id IS NOT NULL)::int = 1",
            name="ck_spot_images_entity",
        ),
        CheckConstraint(
            "delivery IN ('hotlinked', 'hosted')", name="ck_spot_images_delivery"
        ),
        Index("ix_image_spot_status", "spot_id", "status"),
        Index("ix_image_region_status", "region_id", "status"),
        Index("ix_image_app_user", "app_user_id"),
    )


class ImageReport(Base, TimestampMixin):
    __tablename__ = "image_reports"

    id: Mapped[uuid.UUID] = _pk()
    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spot_images.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    reporter_email: Mapped[str | None] = mapped_column(String(255))
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (Index("ix_image_report_image", "image_id"),)
