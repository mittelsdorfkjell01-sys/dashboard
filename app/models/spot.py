import uuid

from geoalchemy2 import Geography
from sqlalchemy import ForeignKey, Index, SmallInteger, String, Float, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Spot(Base, TimestampMixin):
    __tablename__ = "spots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    region_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regions.id", ondelete="CASCADE"),
        nullable=True,
    )

    location: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    # ERA5 grid cell descriptor (lat/lon/index) — populated in a later sprint.
    era5_cell: Mapped[dict | None] = mapped_column(JSONB)
    # Preferred weather model for this spot (e.g. "icon", "gfs"); nullable.
    model_pref: Mapped[str | None] = mapped_column(String(50))

    sports: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]")
    )
    water_type: Mapped[str | None] = mapped_column(String(30))   # ocean | sea | lake | lagoon
    bottom_type: Mapped[str | None] = mapped_column(String(30))  # sand | rock | reef | mixed
    level: Mapped[str | None] = mapped_column(String(30))        # beginner | intermediate | advanced | pro

    # Category axes (validated against app.admin.constants). Wasserart — distinct
    # from water_type: flach | chop | welle_klein | welle_gross | tiefes_wasser.
    water_character: Mapped[str | None] = mapped_column(String(30))
    # Fahrstil (multi-select): freeride | freestyle | big_air | wave_riding.
    style: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]")
    )
    # Facilities: {kind: {"available": bool, "note"?: str}}; a missing kind =
    # "unknown" (frontend hides it). Kinds: parking|shower|food|camping|school.
    facilities: Mapped[dict | None] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'draft'")
    )  # draft | published | archived
    confidence: Mapped[float | None] = mapped_column(Float)      # 0.0 .. 1.0
    # Manual override for the "Fertigstellen" traffic-light rank (red|yellow|
    # green). NULL = automatic (derived from readiness gaps). Set in the
    # overview list or the editor's "Betrieb & Veröffentlichung" panel.
    finish_rank: Mapped[str | None] = mapped_column(String(10))
    facing: Mapped[int | None] = mapped_column(SmallInteger)     # compass bearing 0..359

    editorial: Mapped[dict | None] = mapped_column(JSONB)
    climatology: Mapped[dict | None] = mapped_column(JSONB)
    overrides: Mapped[dict | None] = mapped_column(JSONB)
    image: Mapped[dict | None] = mapped_column(JSONB)

    region: Mapped["Region"] = relationship(  # noqa: F821
        back_populates="spots"
    )

    __table_args__ = (
        Index("ix_spots_location", "location", postgresql_using="gist"),
        Index("ix_spots_sports", "sports", postgresql_using="gin"),
        Index("ix_spots_style", "style", postgresql_using="gin"),
        Index("ix_spots_region_status", "region_id", "status"),
        Index("ix_spots_water_level", "water_type", "level"),
    )
