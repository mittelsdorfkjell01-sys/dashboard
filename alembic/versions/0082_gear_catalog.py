"""add auditable gear catalogue and link rider gear

Revision ID: 0082_gear_catalog
Revises: 0081_spot_editorial_classification
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0082_gear_catalog"
down_revision = "0081_spot_editorial_classification"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column(
        "id", postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"), nullable=False,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


BRANDS = [
    ("10000000-0000-0000-0000-000000000001", "core", "CORE", "https://corekites.com/"),
    ("10000000-0000-0000-0000-000000000002", "duotone", "Duotone", "https://www.duotonesports.com/"),
    ("10000000-0000-0000-0000-000000000003", "north", "North", "https://www.northkb.com/"),
    ("10000000-0000-0000-0000-000000000004", "cabrinha", "Cabrinha", "https://www.cabrinha.com/"),
    ("10000000-0000-0000-0000-000000000005", "f-one", "F-One", "https://www.f-one.world/"),
    ("10000000-0000-0000-0000-000000000006", "ozone", "Ozone", "https://ozonekites.com/"),
    ("10000000-0000-0000-0000-000000000007", "naish", "Naish", "https://www.naish.com/"),
    ("10000000-0000-0000-0000-000000000008", "slingshot", "Slingshot", "https://slingshotsports.com/"),
    ("10000000-0000-0000-0000-000000000009", "airush", "Airush", "https://airush.com/"),
    ("10000000-0000-0000-0000-00000000000a", "eleveight", "Eleveight", "https://www.eleveightkites.com/"),
    ("10000000-0000-0000-0000-00000000000b", "reedin", "Reedin", "https://reedin.com/"),
    ("10000000-0000-0000-0000-00000000000c", "flysurfer", "Flysurfer", "https://flysurfer.com/"),
    ("10000000-0000-0000-0000-00000000000d", "harlem", "Harlem", "https://harlemkitesurfing.com/"),
]


def upgrade() -> None:
    op.drop_constraint("ck_gear_items_kind", "gear_items", type_="check")
    op.create_check_constraint(
        "ck_gear_items_kind",
        "gear_items",
        "kind IN ('kite','board','foil','surfboard','kiteboard','bar','harness','wetsuit','windsurf','foil_component')",
    )
    op.create_table(
        "gear_brands", _id(),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("website_url", sa.String(500)),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"), sa.UniqueConstraint("name"),
    )
    op.create_table(
        "gear_products", _id(),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("model_name", sa.String(160), nullable=False),
        sa.Column("subtype", sa.String(80)), *_timestamps(),
        sa.CheckConstraint(
            "category IN ('kite','surfboard','kiteboard','bar','harness','wetsuit','windsurf','foil_component')",
            name="ck_gear_products_category",
        ),
        sa.ForeignKeyConstraint(["brand_id"], ["gear_brands.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "category", "model_name", name="uq_gear_product_identity"),
    )
    op.create_index("ix_gear_products_category", "gear_products", ["category", "brand_id"])
    op.create_table(
        "gear_product_versions", _id(),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("season_label", sa.String(80), nullable=False),
        sa.Column("model_year", sa.Integer()),
        sa.Column("identity_status", sa.String(30), server_default="unverified", nullable=False),
        sa.Column("notes", sa.Text()), *_timestamps(),
        sa.CheckConstraint("model_year IS NULL OR model_year >= 1900", name="ck_gear_product_versions_year"),
        sa.CheckConstraint(
            "identity_status IN ('unverified','review','verified','conflict')",
            name="ck_gear_product_versions_status",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["gear_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "season_label", name="uq_gear_product_version"),
    )
    op.create_table(
        "gear_size_variants", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("numeric_value", sa.Numeric(8, 2)), sa.Column("unit", sa.String(20)),
        *_timestamps(),
        sa.CheckConstraint("numeric_value IS NULL OR numeric_value > 0", name="ck_gear_size_variants_value"),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_version_id", "label", name="uq_gear_size_variant"),
    )
    op.create_table(
        "gear_color_variants", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160)),
        sa.Column("palette", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("jsonb_typeof(palette) = 'object'", name="ck_gear_color_variants_palette"),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_version_id", "code", name="uq_gear_color_variant"),
    )
    op.create_table(
        "gear_sources", _id(),
        sa.Column("url", sa.String(1000), nullable=False), sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(160), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rights_note", sa.Text()), *_timestamps(),
        sa.CheckConstraint(
            "source_type IN ('manufacturer_page','manufacturer_manual','manufacturer_catalog','retailer','other')",
            name="ck_gear_sources_type",
        ),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("url"),
    )
    op.create_table(
        "gear_claims", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("size_variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("color_variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False), sa.Column("unit", sa.String(30)),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_status", sa.String(30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("uncertainty_note", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint("jsonb_typeof(value) = 'object'", name="ck_gear_claims_value"),
        sa.CheckConstraint(
            "verification_status IN ('unverified','review','verified','conflict')", name="ck_gear_claims_status"
        ),
        sa.CheckConstraint(
            "NOT (size_variant_id IS NOT NULL AND color_variant_id IS NOT NULL)",
            name="ck_gear_claims_single_variant_scope",
        ),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["size_variant_id"], ["gear_size_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["color_variant_id"], ["gear_color_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["gear_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gear_claims_version_field", "gear_claims", ["product_version_id", "field_name"])
    op.create_table(
        "gear_geometries", _id(),
        sa.Column("product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("size_variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("asset_path", sa.String(500), nullable=False),
        sa.Column("accuracy_status", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint("jsonb_typeof(parameters) = 'object'", name="ck_gear_geometries_parameters"),
        sa.CheckConstraint(
            "accuracy_status IN ('generic','data_based_unverified','reference_checked')",
            name="ck_gear_geometries_accuracy",
        ),
        sa.ForeignKeyConstraint(["product_version_id"], ["gear_product_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["size_variant_id"], ["gear_size_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["gear_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_version_id", "size_variant_id", "generator_version",
            name="uq_gear_geometry_version_size_generator",
        ),
    )
    op.create_table(
        "gear_research_coverage", _id(),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("start_year", sa.Integer(), server_default="2016", nullable=False),
        sa.Column("latest_verified_season", sa.String(80)),
        sa.Column("status", sa.String(30), server_default="planned", nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint("start_year >= 1900", name="ck_gear_research_coverage_start_year"),
        sa.CheckConstraint(
            "status IN ('planned','in_progress','pilot_complete','review_needed','complete')",
            name="ck_gear_research_coverage_status",
        ),
        sa.ForeignKeyConstraint(["brand_id"], ["gear_brands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "category", name="uq_gear_research_coverage"),
    )

    op.add_column("gear_items", sa.Column("catalog_size_variant_id", postgresql.UUID(as_uuid=True)))
    op.add_column("gear_items", sa.Column("catalog_color_variant_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_gear_items_catalog_size", "gear_items", "gear_size_variants",
        ["catalog_size_variant_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_gear_items_catalog_color", "gear_items", "gear_color_variants",
        ["catalog_color_variant_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_gear_items_catalog_size", "gear_items", ["catalog_size_variant_id"])

    _seed_catalog()


def _seed_catalog() -> None:
    checked = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    brand_table = sa.table(
        "gear_brands", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("slug"),
        sa.column("name"), sa.column("website_url"), sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(brand_table, [
        {"id": uuid.UUID(row[0]), "slug": row[1], "name": row[2], "website_url": row[3], "active": True}
        for row in BRANDS
    ])

    products = sa.table(
        "gear_products", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("brand_id", postgresql.UUID(as_uuid=True)), sa.column("category"),
        sa.column("model_name"), sa.column("subtype"),
    )
    op.bulk_insert(products, [
        {"id": uuid.UUID("20000000-0000-0000-0000-000000000001"), "brand_id": uuid.UUID(BRANDS[0][0]), "category": "kite", "model_name": "XR8", "subtype": None},
        {"id": uuid.UUID("20000000-0000-0000-0000-000000000002"), "brand_id": uuid.UUID(BRANDS[1][0]), "category": "kite", "model_name": "Neo", "subtype": "wave"},
        {"id": uuid.UUID("20000000-0000-0000-0000-000000000003"), "brand_id": uuid.UUID(BRANDS[4][0]), "category": "kite", "model_name": "Bandit", "subtype": "all-round"},
    ])
    versions = sa.table(
        "gear_product_versions", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("product_id", postgresql.UUID(as_uuid=True)), sa.column("season_label"),
        sa.column("model_year", sa.Integer()), sa.column("identity_status"), sa.column("notes"),
    )
    op.bulk_insert(versions, [
        {"id": uuid.UUID("30000000-0000-0000-0000-000000000001"), "product_id": uuid.UUID("20000000-0000-0000-0000-000000000001"), "season_label": "2023", "model_year": 2023, "identity_status": "verified", "notes": "Official CORE support roadmap identifies XR8 as a 2023 product."},
        {"id": uuid.UUID("30000000-0000-0000-0000-000000000002"), "product_id": uuid.UUID("20000000-0000-0000-0000-000000000002"), "season_label": "2026", "model_year": 2026, "identity_status": "verified", "notes": "Official product page names the 2026 season."},
        {"id": uuid.UUID("30000000-0000-0000-0000-000000000003"), "product_id": uuid.UUID("20000000-0000-0000-0000-000000000003"), "season_label": "Edition 18", "model_year": None, "identity_status": "verified", "notes": "The official page proves edition 18 but does not state a model year; no year is inferred."},
    ])
    sizes = sa.table(
        "gear_size_variants", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("product_version_id", postgresql.UUID(as_uuid=True)), sa.column("label"),
        sa.column("numeric_value", sa.Numeric()), sa.column("unit"),
    )
    op.bulk_insert(sizes, [
        {"id": uuid.UUID("40000000-0000-0000-0000-000000000001"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000001"), "label": "11 m²", "numeric_value": 11, "unit": "m²"},
        {"id": uuid.UUID("40000000-0000-0000-0000-000000000002"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000002"), "label": "11 m²", "numeric_value": 11, "unit": "m²"},
        {"id": uuid.UUID("40000000-0000-0000-0000-000000000003"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000003"), "label": "9 m²", "numeric_value": 9, "unit": "m²"},
    ])
    colors = sa.table(
        "gear_color_variants", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("product_version_id", postgresql.UUID(as_uuid=True)), sa.column("code"),
        sa.column("name"), sa.column("palette", postgresql.JSONB()),
    )
    op.bulk_insert(colors, [
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000001"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000003"), "code": "A", "name": "Lilac", "palette": {"primary": "lilac"}},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000002"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000003"), "code": "B", "name": "Flame", "palette": {"primary": "flame"}},
    ])
    sources = sa.table(
        "gear_sources", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("url"),
        sa.column("title"), sa.column("publisher"), sa.column("source_type"),
        sa.column("checked_at", sa.DateTime(timezone=True)), sa.column("rights_note"),
    )
    op.bulk_insert(sources, [
        {"id": uuid.UUID("60000000-0000-0000-0000-000000000001"), "url": "https://support.corekites.com/en/support/solutions/articles/136210-how-long-will-you-carry-parts-for-my-core-product-kite-bar-board-", "title": "CORE official end of support roadmap", "publisher": "CORE", "source_type": "manufacturer_page", "checked_at": checked, "rights_note": "Facts only; no manufacturer imagery copied."},
        {"id": uuid.UUID("60000000-0000-0000-0000-000000000002"), "url": "https://support.corekites.com/en/support/solutions/articles/4000007990-how-much-does-my-kite-and-kite-bag-weigh-", "title": "How much does my kite and kite bag weigh?", "publisher": "CORE", "source_type": "manufacturer_page", "checked_at": checked, "rights_note": "Facts only; no manufacturer imagery copied."},
        {"id": uuid.UUID("60000000-0000-0000-0000-000000000003"), "url": "https://www.duotonesports.com/en/products/duotone-neo-2026-44260-3004", "title": "Duotone Neo 2026", "publisher": "Duotone", "source_type": "manufacturer_page", "checked_at": checked, "rights_note": "Facts only; no manufacturer imagery copied."},
        {"id": uuid.UUID("60000000-0000-0000-0000-000000000004"), "url": "https://www.f-one.world/en/kite/kites/bandit-18.html", "title": "BANDIT Edition 18", "publisher": "F-One", "source_type": "manufacturer_page", "checked_at": checked, "rights_note": "Facts only; no manufacturer imagery copied."},
    ])
    claims = sa.table(
        "gear_claims", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("product_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("size_variant_id", postgresql.UUID(as_uuid=True)),
        sa.column("color_variant_id", postgresql.UUID(as_uuid=True)), sa.column("field_name"),
        sa.column("value", postgresql.JSONB()), sa.column("unit"),
        sa.column("source_id", postgresql.UUID(as_uuid=True)), sa.column("verification_status"),
        sa.column("verified_at", sa.DateTime(timezone=True)), sa.column("uncertainty_note"),
    )
    claim_rows = [
        (1, 1, None, None, "model_year", {"value": 2023}, None, 1, None),
        (2, 1, 1, None, "weight_without_bag", {"value": 3.5}, "kg", 2, None),
        (3, 2, None, None, "model_year", {"value": 2026}, None, 3, None),
        (4, 2, None, None, "intended_use", {"value": "wave"}, None, 3, None),
        (5, 2, 2, None, "available_size", {"value": 11}, "m²", 3, None),
        (6, 3, None, None, "edition", {"value": 18}, None, 4, "Edition is not treated as a calendar model year."),
        (7, 3, 3, None, "wind_range", {"min": 15, "max": 30}, "kn", 4, None),
        (8, 3, None, None, "strut_count", {"value": 3}, None, 4, None),
        (9, 3, None, None, "aspect_ratio", {"value": "medium"}, None, 4, None),
        (10, 3, None, 1, "colorway", {"code": "A", "name": "Lilac"}, None, 4, None),
        (11, 3, None, 2, "colorway", {"code": "B", "name": "Flame"}, None, 4, None),
    ]
    op.bulk_insert(claims, [{
        "id": uuid.UUID(f"70000000-0000-0000-0000-{idx:012d}"),
        "product_version_id": uuid.UUID(f"30000000-0000-0000-0000-{version:012d}"),
        "size_variant_id": uuid.UUID(f"40000000-0000-0000-0000-{size:012d}") if size else None,
        "color_variant_id": uuid.UUID(f"50000000-0000-0000-0000-{color:012d}") if color else None,
        "field_name": field, "value": value, "unit": unit,
        "source_id": uuid.UUID(f"60000000-0000-0000-0000-{source:012d}"),
        "verification_status": "verified", "verified_at": checked, "uncertainty_note": note,
    } for idx, version, size, color, field, value, unit, source, note in claim_rows])

    geometries = sa.table(
        "gear_geometries", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("product_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("size_variant_id", postgresql.UUID(as_uuid=True)), sa.column("generator_version"),
        sa.column("parameters", postgresql.JSONB()), sa.column("asset_path"),
        sa.column("accuracy_status"), sa.column("source_id", postgresql.UUID(as_uuid=True)),
        sa.column("verified_at", sa.DateTime(timezone=True)), sa.column("notes"),
    )
    op.bulk_insert(geometries, [
        {"id": uuid.UUID("80000000-0000-0000-0000-000000000001"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000001"), "size_variant_id": uuid.UUID("40000000-0000-0000-0000-000000000001"), "generator_version": "kite-svg-v1", "parameters": {"template": "inflatable", "arc": 0.72, "depth": 0.33, "struts": 5, "colors": ["#171717", "#f5f5f0"]}, "asset_path": "/gear/kites/core-xr8-2023-11.svg", "accuracy_status": "generic", "source_id": None, "verified_at": None, "notes": "Illustrative template only; outline and strut positions are not measured from the product."},
        {"id": uuid.UUID("80000000-0000-0000-0000-000000000002"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000002"), "size_variant_id": uuid.UUID("40000000-0000-0000-0000-000000000002"), "generator_version": "kite-svg-v1", "parameters": {"template": "inflatable", "arc": 0.78, "depth": 0.38, "struts": 3, "colors": ["#154d64", "#d7eee9"]}, "asset_path": "/gear/kites/duotone-neo-2026-11.svg", "accuracy_status": "generic", "source_id": None, "verified_at": None, "notes": "Illustrative template only; no reference geometry is claimed."},
        {"id": uuid.UUID("80000000-0000-0000-0000-000000000003"), "product_version_id": uuid.UUID("30000000-0000-0000-0000-000000000003"), "size_variant_id": uuid.UUID("40000000-0000-0000-0000-000000000003"), "generator_version": "kite-svg-v1", "parameters": {"template": "inflatable", "arc": 0.75, "depth": 0.36, "struts": 3, "colors": ["#6e5485", "#f0d9b5"]}, "asset_path": "/gear/kites/f-one-bandit-edition-18-9.svg", "accuracy_status": "data_based_unverified", "source_id": uuid.UUID("60000000-0000-0000-0000-000000000004"), "verified_at": None, "notes": "Strut count is sourced; outline and panel geometry remain generic and not reference-checked."},
    ])

    coverage = sa.table(
        "gear_research_coverage", sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("brand_id", postgresql.UUID(as_uuid=True)), sa.column("category"),
        sa.column("start_year", sa.Integer()), sa.column("latest_verified_season"),
        sa.column("status"), sa.column("checked_at", sa.DateTime(timezone=True)), sa.column("notes"),
    )
    seasons = {"core": "2023", "duotone": "2026", "f-one": "Edition 18"}
    op.bulk_insert(coverage, [{
        "id": uuid.UUID(f"90000000-0000-0000-0000-{index:012d}"),
        "brand_id": uuid.UUID(row[0]), "category": "kite", "start_year": 2016,
        "latest_verified_season": seasons.get(row[1]),
        "status": "pilot_complete" if row[1] in seasons else "planned",
        "checked_at": checked if row[1] in seasons else None,
        "notes": "Pilot only; gaps remain open for staged research." if row[1] in seasons else "Research from 2016 onward is not started; do not infer seasons.",
    } for index, row in enumerate(BRANDS, start=1)])


def downgrade() -> None:
    op.drop_index("ix_gear_items_catalog_size", table_name="gear_items")
    op.drop_constraint("fk_gear_items_catalog_color", "gear_items", type_="foreignkey")
    op.drop_constraint("fk_gear_items_catalog_size", "gear_items", type_="foreignkey")
    op.drop_column("gear_items", "catalog_color_variant_id")
    op.drop_column("gear_items", "catalog_size_variant_id")
    op.drop_table("gear_research_coverage")
    op.drop_table("gear_geometries")
    op.drop_index("ix_gear_claims_version_field", table_name="gear_claims")
    op.drop_table("gear_claims")
    op.drop_table("gear_sources")
    op.drop_table("gear_color_variants")
    op.drop_table("gear_size_variants")
    op.drop_table("gear_product_versions")
    op.drop_index("ix_gear_products_category", table_name="gear_products")
    op.drop_table("gear_products")
    op.drop_table("gear_brands")
    op.drop_constraint("ck_gear_items_kind", "gear_items", type_="check")
    op.create_check_constraint(
        "ck_gear_items_kind", "gear_items", "kind IN ('kite','board','foil')"
    )
