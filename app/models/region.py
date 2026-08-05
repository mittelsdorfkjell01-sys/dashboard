import uuid

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base, TimestampMixin
from app.names import clean_display_name, normalize_name


class Region(Base, TimestampMixin):
    __tablename__ = "regions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(240), unique=True, nullable=False
    )
    country: Mapped[str | None] = mapped_column(String(2))  # ISO 3166-1 alpha-2
    # draft = hidden from public listings; published = live. Existing rows keep
    # showing (server_default 'published'); new regions are created as draft.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'published'")
    )

    center: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    bounds: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326, spatial_index=False)
    )

    description: Mapped[str | None] = mapped_column(Text)
    image: Mapped[dict | None] = mapped_column(JSONB)
    season: Mapped[dict | None] = mapped_column(JSONB)
    defaults: Mapped[dict | None] = mapped_column(JSONB)

    spots: Mapped[list["Spot"]] = relationship(back_populates="region")  # noqa: F821

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="ck_regions_status"),
        Index("ix_regions_center", "center", postgresql_using="gist"),
        Index(
            "ix_regions_normalized_name_trgm",
            "normalized_name",
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        ),
    )

    @validates("name")
    def _set_name(self, _key: str, value: str) -> str:
        cleaned = clean_display_name(value)
        self.normalized_name = normalize_name(cleaned)
        return cleaned
