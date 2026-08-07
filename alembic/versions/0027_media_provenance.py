"""media provenance: image-object schema, usage index, picker infrastructure

Revision ID: 0027_media_provenance
Revises: 0026_remove_admin_totp
Create Date: 2026-08-06

Three things at once, because they form one data model:

1. ``spot_images`` becomes entity-generic (spot **or** region) and gains the
   provider columns plus a manual sort position. Regions had no gallery at all;
   a twin table would have meant two code paths for one feature.
2. ``media_usage`` records which provider photo sits where, so the picker can
   block a duplicate hero and warn on a duplicate gallery image.
3. ``media_search_cache`` + ``media_provider_budget`` back the Sprint 2 proxy.
   They live in Postgres because Redis is optional in this project (the live
   cache is fail-open by design) and absent from the Vercel deployment — a
   fail-open request budget could not hold Unsplash's 50/hour line.

The data step pads every existing ``image`` JSONB (spots and regions) up to the
canonical shape. Existing values always win: nothing is overwritten, only
missing keys are filled with ``unknown`` / ``hosted`` / centre-focal / NULL.
Mirrors ``app.media.image_object.upgrade_legacy``.

``downgrade()`` restores the four-field image object and the spot-only gallery.
That direction necessarily drops what the new columns hold — including any
region gallery rows, which have nowhere to go in the old schema.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_media_provenance"
down_revision: Union[str, None] = "0026_remove_admin_totp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Pads a legacy image object without overwriting anything already present.
_UPGRADE_IMAGE = """
    UPDATE {table} SET image = jsonb_build_object(
        'url',          image->'url',
        'source',       image->'source',
        'license',      image->'license',
        'license_url',  COALESCE(image->'license_url',  'null'::jsonb),
        'credit',       image->'credit',
        'credit_url',   COALESCE(image->'credit_url',   'null'::jsonb),
        'provider',     COALESCE(image->'provider',     '"unknown"'::jsonb),
        'external_id',  COALESCE(image->'external_id',  'null'::jsonb),
        'source_page',  COALESCE(image->'source_page',  'null'::jsonb),
        'retrieved_at', COALESCE(image->'retrieved_at', 'null'::jsonb),
        'delivery',     COALESCE(image->'delivery',     '"hosted"'::jsonb),
        'focal',        COALESCE(image->'focal',        '{{"x": 50, "y": 50}}'::jsonb),
        'width',        COALESCE(image->'width',        'null'::jsonb),
        'height',       COALESCE(image->'height',       'null'::jsonb),
        'geo_verified', COALESCE(image->'geo_verified', 'false'::jsonb),
        'role',         COALESCE(image->'role',         '"hero"'::jsonb),
        'source_status',     COALESCE(image->'source_status',     'null'::jsonb),
        'source_checked_at', COALESCE(image->'source_checked_at', 'null'::jsonb)
    )
    WHERE image IS NOT NULL AND jsonb_typeof(image) = 'object'
"""

_DOWNGRADE_IMAGE = """
    UPDATE {table} SET image = jsonb_strip_nulls(jsonb_build_object(
        'url',     image->'url',
        'source',  image->'source',
        'license', image->'license',
        'credit',  image->'credit',
        'focal',   image->'focal'
    ))
    WHERE image IS NOT NULL AND jsonb_typeof(image) = 'object'
"""


def upgrade() -> None:
    # --- 1. gallery: spot-only -> spot or region ---------------------------
    op.alter_column("spot_images", "spot_id", nullable=True)
    op.add_column(
        "spot_images",
        sa.Column("region_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_spot_images_region", "spot_images", "regions",
        ["region_id"], ["id"], ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_spot_images_entity",
        "spot_images",
        "(spot_id IS NOT NULL)::int + (region_id IS NOT NULL)::int = 1",
    )
    op.add_column("spot_images", sa.Column("provider", sa.String(30)))
    op.add_column("spot_images", sa.Column("external_id", sa.String(200)))
    op.add_column("spot_images", sa.Column("credit_url", sa.String(500)))
    op.add_column(
        "spot_images", sa.Column("retrieved_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "spot_images",
        sa.Column(
            "delivery", sa.String(20), nullable=False, server_default=sa.text("'hosted'")
        ),
    )
    op.add_column(
        "spot_images",
        sa.Column(
            "geo_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("spot_images", sa.Column("position", sa.Integer()))
    op.create_check_constraint(
        "ck_spot_images_delivery",
        "spot_images",
        "delivery IN ('hotlinked', 'hosted')",
    )
    op.create_index("ix_image_region_status", "spot_images", ["region_id", "status"])

    # Commons rows already carry a provider identity in everything but name.
    op.execute(
        "UPDATE spot_images SET provider = 'wikimedia' "
        "WHERE source = 'wikimedia_commons'"
    )
    op.execute(
        "UPDATE spot_images SET provider = 'community' WHERE source = 'user_upload'"
    )

    # --- 2. duplicate-usage index -----------------------------------------
    op.create_table(
        "media_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(200)),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ('spot', 'region')", name="ck_media_usage_entity_type"
        ),
        sa.CheckConstraint("role IN ('hero', 'gallery')", name="ck_media_usage_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial: NULL external_ids (uploads, legacy rows) never conflict in
    # Postgres, so an unqualified unique index would enforce nothing.
    op.create_index(
        "uq_media_usage_photo_placement",
        "media_usage",
        ["provider", "external_id", "entity_type", "entity_id", "role"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_index("ix_media_usage_entity", "media_usage", ["entity_type", "entity_id"])
    op.create_index("ix_media_usage_photo", "media_usage", ["provider", "external_id"])

    # --- 3. picker infrastructure (used from Sprint 2) ---------------------
    op.create_table(
        "media_search_cache",
        sa.Column("cache_key", sa.String(400), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_index("ix_media_search_cache_expires", "media_search_cache", ["expires_at"])

    op.create_table(
        "media_provider_budget",
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "request_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.CheckConstraint("request_count >= 0", name="ck_media_budget_count"),
        sa.PrimaryKeyConstraint("provider", "window_start"),
    )

    # --- 4. lift existing image objects to the canonical shape -------------
    op.execute(_UPGRADE_IMAGE.format(table="spots"))
    op.execute(_UPGRADE_IMAGE.format(table="regions"))


def downgrade() -> None:
    op.execute(_DOWNGRADE_IMAGE.format(table="spots"))
    op.execute(_DOWNGRADE_IMAGE.format(table="regions"))

    op.drop_table("media_provider_budget")
    op.drop_index("ix_media_search_cache_expires", table_name="media_search_cache")
    op.drop_table("media_search_cache")
    op.drop_index("ix_media_usage_photo", table_name="media_usage")
    op.drop_index("ix_media_usage_entity", table_name="media_usage")
    op.drop_index("uq_media_usage_photo_placement", table_name="media_usage")
    op.drop_table("media_usage")

    # Region gallery rows cannot exist in the old spot-only schema.
    op.execute("DELETE FROM spot_images WHERE region_id IS NOT NULL")
    op.drop_index("ix_image_region_status", table_name="spot_images")
    op.drop_constraint("ck_spot_images_delivery", "spot_images", type_="check")
    op.drop_constraint("ck_spot_images_entity", "spot_images", type_="check")
    op.drop_constraint("fk_spot_images_region", "spot_images", type_="foreignkey")
    op.drop_column("spot_images", "position")
    op.drop_column("spot_images", "geo_verified")
    op.drop_column("spot_images", "delivery")
    op.drop_column("spot_images", "retrieved_at")
    op.drop_column("spot_images", "credit_url")
    op.drop_column("spot_images", "external_id")
    op.drop_column("spot_images", "provider")
    op.drop_column("spot_images", "region_id")
    op.alter_column("spot_images", "spot_id", nullable=False)
