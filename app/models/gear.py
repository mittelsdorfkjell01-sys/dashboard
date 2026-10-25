"""Auditable product catalogue for rider gear."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class GearBrand(Base, TimestampMixin):
    __tablename__ = "gear_brands"

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    website_url: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class GearProduct(Base, TimestampMixin):
    __tablename__ = "gear_products"

    id: Mapped[uuid.UUID] = _uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_brands.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        UniqueConstraint("brand_id", "category", "model_name", name="uq_gear_product_identity"),
        CheckConstraint(
            "category IN ('kite','surfboard','kiteboard','bar','line_set','harness','wetsuit',"
            "'wing','windsurf','windsurf_sail','windsurf_board','foil','foil_component','pump','accessory')",
            name="ck_gear_products_category",
        ),
        Index("ix_gear_products_category", "category", "brand_id"),
    )


class GearProductVersion(Base, TimestampMixin):
    __tablename__ = "gear_product_versions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_products.id", ondelete="CASCADE"), nullable=False
    )
    season_label: Mapped[str] = mapped_column(String(80), nullable=False)
    model_year: Mapped[int | None] = mapped_column(Integer)
    identity_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'unverified'")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("product_id", "season_label", name="uq_gear_product_version"),
        CheckConstraint(
            "model_year IS NULL OR model_year >= 1900", name="ck_gear_product_versions_year"
        ),
        CheckConstraint(
            "identity_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_product_versions_status",
        ),
    )


class GearSizeVariant(Base, TimestampMixin):
    __tablename__ = "gear_size_variants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    product_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_product_versions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    unit: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        UniqueConstraint("product_version_id", "label", name="uq_gear_size_variant"),
        CheckConstraint(
            "numeric_value IS NULL OR numeric_value > 0", name="ck_gear_size_variants_value"
        ),
    )


class GearColorVariant(Base, TimestampMixin):
    __tablename__ = "gear_color_variants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    product_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_product_versions.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str | None] = mapped_column(String(160))
    palette: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("product_version_id", "code", name="uq_gear_color_variant"),
        CheckConstraint("jsonb_typeof(palette) = 'object'", name="ck_gear_color_variants_palette"),
    )


class GearSource(Base, TimestampMixin):
    __tablename__ = "gear_sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rights_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('manufacturer_page','manufacturer_manual','manufacturer_catalog','retailer','other')",
            name="ck_gear_sources_type",
        ),
    )


class GearClaim(Base, TimestampMixin):
    __tablename__ = "gear_claims"

    id: Mapped[uuid.UUID] = _uuid_pk()
    product_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_product_versions.id", ondelete="CASCADE"), nullable=False
    )
    size_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_size_variants.id", ondelete="CASCADE")
    )
    color_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_color_variants.id", ondelete="CASCADE")
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30))
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_sources.id", ondelete="RESTRICT"), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uncertainty_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("jsonb_typeof(value) = 'object'", name="ck_gear_claims_value"),
        CheckConstraint(
            "verification_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_claims_status",
        ),
        CheckConstraint(
            "NOT (size_variant_id IS NOT NULL AND color_variant_id IS NOT NULL)",
            name="ck_gear_claims_single_variant_scope",
        ),
        Index("ix_gear_claims_version_field", "product_version_id", "field_name"),
    )


class GearCompatibility(Base, TimestampMixin):
    __tablename__ = "gear_compatibilities"

    id: Mapped[uuid.UUID] = _uuid_pk()
    product_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_product_versions.id", ondelete="CASCADE"), nullable=False
    )
    target_category: Mapped[str] = mapped_column(String(40), nullable=False)
    target_product_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_product_versions.id", ondelete="CASCADE")
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    specification: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_sources.id", ondelete="RESTRICT"), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('requires','compatible','recommended','incompatible')",
            name="ck_gear_compatibilities_relation",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_compatibilities_status",
        ),
        CheckConstraint(
            "jsonb_typeof(specification) = 'object'",
            name="ck_gear_compatibilities_specification",
        ),
        Index(
            "ix_gear_compatibilities_product",
            "product_version_id", "target_category", "relation_type",
        ),
    )


class GearUseProfile(Base, TimestampMixin):
    __tablename__ = "gear_use_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    product_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_product_versions.id", ondelete="CASCADE"), nullable=False
    )
    size_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_size_variants.id", ondelete="CASCADE")
    )
    sport: Mapped[str] = mapped_column(String(30), nullable=False)
    discipline: Mapped[str] = mapped_column(String(30), nullable=False)
    condition: Mapped[str] = mapped_column(String(30), nullable=False)
    suitability: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_sources.id", ondelete="RESTRICT"), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "sport IN ('kitesurf','windsurf','wingfoil','surfing')",
            name="ck_gear_use_profiles_sport",
        ),
        CheckConstraint(
            "discipline IN ('all_round','freeride','big_air','wave','freestyle','foil','race','school')",
            name="ck_gear_use_profiles_discipline",
        ),
        CheckConstraint(
            "condition IN ('all_conditions','light_wind','moderate_wind','strong_wind','waves','flat_water','gusty')",
            name="ck_gear_use_profiles_condition",
        ),
        CheckConstraint(
            "suitability IN ('designed_for','suitable','limited','not_recommended')",
            name="ck_gear_use_profiles_suitability",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_use_profiles_status",
        ),
        Index(
            "ix_gear_use_profiles_product",
            "product_version_id", "sport", "discipline", "condition",
        ),
    )


class GearResearchCoverage(Base, TimestampMixin):
    __tablename__ = "gear_research_coverage"

    id: Mapped[uuid.UUID] = _uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gear_brands.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("2016"))
    latest_verified_season: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'planned'"))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("brand_id", "category", name="uq_gear_research_coverage"),
        CheckConstraint("start_year >= 1900", name="ck_gear_research_coverage_start_year"),
        CheckConstraint(
            "status IN ('planned','in_progress','pilot_complete','review_needed','complete')",
            name="ck_gear_research_coverage_status",
        ),
    )
