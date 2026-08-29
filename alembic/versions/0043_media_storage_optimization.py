"""compact image JSON and archive terminal moderation rows

Revision ID: 0043_media_storage_optimization
Revises: 0042_calibration_decisions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0043_media_storage_optimization"
down_revision = "0042_calibration_decisions"
branch_labels = None
depends_on = None


def _compact_image_json(table: str) -> None:
    op.execute(
        sa.text(
            f"UPDATE {table} SET image = jsonb_strip_nulls(image) "
            "WHERE image IS NOT NULL"
        )
    )
    defaults = (
        ("provider", "image->>'provider' = 'unknown'"),
        ("delivery", "image->>'delivery' = 'hosted'"),
        ("focal", "image->'focal' = '{\"x\": 50.0, \"y\": 50.0}'::jsonb"),
        ("rotation", "image->>'rotation' IN ('0', '0.0')"),
        ("geo_verified", "image->'geo_verified' = 'false'::jsonb"),
        ("role", "image->>'role' = 'hero'"),
        ("hero_reel", "image->'hero_reel' = 'false'::jsonb"),
    )
    for key, condition in defaults:
        op.execute(
            sa.text(
                f"UPDATE {table} SET image = image - '{key}' "
                f"WHERE image IS NOT NULL AND {condition}"
            )
        )


def upgrade():
    op.create_table(
        "spot_image_archives",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_type", sa.String(10), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("original_bytes", sa.Integer(), nullable=False),
        sa.Column("compressed_bytes", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_spot_image_archive_entity",
        "spot_image_archives",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_spot_image_archive_archived_at",
        "spot_image_archives",
        ["archived_at"],
    )
    op.create_index(
        "ix_image_terminal_retention",
        "spot_images",
        ["updated_at"],
        postgresql_where=sa.text("status IN ('rejected', 'removed')"),
    )
    for table in ("spots", "regions"):
        _compact_image_json(table)


def downgrade():
    defaults = """jsonb_build_object(
        'url', NULL, 'source', NULL, 'license', NULL, 'license_url', NULL,
        'credit', NULL, 'credit_url', NULL, 'provider', 'unknown',
        'external_id', NULL, 'source_page', NULL, 'retrieved_at', NULL,
        'delivery', 'hosted', 'focal', jsonb_build_object('x', 50.0, 'y', 50.0),
        'focal_mobile', NULL, 'rotation', 0.0, 'width', NULL, 'height', NULL,
        'geo_verified', false, 'role', 'hero', 'hero_reel', false,
        'source_status', NULL, 'source_checked_at', NULL
    )"""
    for table in ("spots", "regions"):
        op.execute(
            sa.text(
                f"UPDATE {table} SET image = ({defaults}) || image "
                "WHERE image IS NOT NULL"
            )
        )
    op.drop_index("ix_image_terminal_retention", table_name="spot_images")
    op.drop_index(
        "ix_spot_image_archive_archived_at", table_name="spot_image_archives"
    )
    op.drop_index(
        "ix_spot_image_archive_entity", table_name="spot_image_archives"
    )
    op.drop_table("spot_image_archives")
