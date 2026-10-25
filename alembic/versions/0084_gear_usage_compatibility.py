"""replace gear drawings with compatibility and use profiles

Revision ID: 0084_gear_usage_compatibility
Revises: 0083_gear_svg_v2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0084_gear_usage_compatibility"
down_revision = "0083_gear_svg_v2"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column(
        "id", postgresql.UUID(as_uuid=True), primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.drop_table("gear_geometries")
    op.drop_constraint("ck_gear_products_category", "gear_products", type_="check")
    op.create_check_constraint(
        "ck_gear_products_category", "gear_products",
        "category IN ('kite','surfboard','kiteboard','bar','line_set','harness','wetsuit',"
        "'wing','windsurf','windsurf_sail','windsurf_board','foil','foil_component','pump','accessory')",
    )

    op.create_table(
        "gear_compatibilities", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_category", sa.String(40), nullable=False),
        sa.Column("target_product_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("relation_type", sa.String(30), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_status", sa.String(30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "relation_type IN ('requires','compatible','recommended','incompatible')",
            name="ck_gear_compatibilities_relation",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_compatibilities_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(specification) = 'object'",
            name="ck_gear_compatibilities_specification",
        ),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["gear_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_gear_compatibilities_product", "gear_compatibilities",
        ["product_version_id", "target_category", "relation_type"],
    )

    op.create_table(
        "gear_use_profiles", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("size_variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sport", sa.String(30), nullable=False),
        sa.Column("discipline", sa.String(30), nullable=False),
        sa.Column("condition", sa.String(30), nullable=False),
        sa.Column("suitability", sa.String(30), nullable=False),
        sa.Column("wind_min_kn", sa.Numeric(6, 2)),
        sa.Column("wind_max_kn", sa.Numeric(6, 2)),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_status", sa.String(30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "sport IN ('kitesurf','windsurf','wingfoil','surfing')",
            name="ck_gear_use_profiles_sport",
        ),
        sa.CheckConstraint(
            "discipline IN ('all_round','freeride','big_air','wave','freestyle','foil','race','school')",
            name="ck_gear_use_profiles_discipline",
        ),
        sa.CheckConstraint(
            "condition IN ('all_conditions','light_wind','moderate_wind','strong_wind','waves','flat_water','gusty')",
            name="ck_gear_use_profiles_condition",
        ),
        sa.CheckConstraint(
            "suitability IN ('designed_for','suitable','limited','not_recommended')",
            name="ck_gear_use_profiles_suitability",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_use_profiles_status",
        ),
        sa.CheckConstraint(
            "(wind_min_kn IS NULL AND wind_max_kn IS NULL) OR "
            "(wind_min_kn >= 0 AND wind_max_kn > wind_min_kn)",
            name="ck_gear_use_profiles_wind_range",
        ),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["size_variant_id"], ["gear_size_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["gear_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_gear_use_profiles_product", "gear_use_profiles",
        ["product_version_id", "sport", "discipline", "condition"],
    )


def downgrade() -> None:
    op.drop_index("ix_gear_use_profiles_product", table_name="gear_use_profiles")
    op.drop_table("gear_use_profiles")
    op.drop_index("ix_gear_compatibilities_product", table_name="gear_compatibilities")
    op.drop_table("gear_compatibilities")
    op.drop_constraint("ck_gear_products_category", "gear_products", type_="check")
    op.create_check_constraint(
        "ck_gear_products_category", "gear_products",
        "category IN ('kite','surfboard','kiteboard','bar','harness','wetsuit','windsurf','foil_component')",
    )
    op.create_table(
        "gear_geometries", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("size_variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("asset_path", sa.String(500), nullable=False),
        sa.Column("accuracy_status", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["size_variant_id"], ["gear_size_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["gear_sources.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "product_version_id", "size_variant_id", "generator_version",
            name="uq_gear_geometry_version_size_generator",
        ),
        sa.CheckConstraint("jsonb_typeof(parameters) = 'object'", name="ck_gear_geometries_parameters"),
        sa.CheckConstraint(
            "accuracy_status IN ('generic','data_based_unverified','reference_checked')",
            name="ck_gear_geometries_accuracy",
        ),
    )
