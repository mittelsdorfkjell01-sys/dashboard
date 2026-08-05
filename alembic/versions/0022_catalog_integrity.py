"""catalog integrity, moderation checks, and UGC ownership

Revision ID: 0022_catalog_integrity
Revises: 0021_session_versions
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_catalog_integrity"
down_revision: Union[str, None] = "0021_session_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _validated_check(table: str, name: str, expression: str) -> None:
    op.execute(
        sa.text(f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" CHECK ({expression}) NOT VALID')
    )
    op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))


def _ugc_fk(table: str, constraint: str) -> None:
    op.execute(
        sa.text(
            f'UPDATE "{table}" SET app_user_id = NULL '
            'WHERE app_user_id IS NOT NULL AND NOT EXISTS '
            f'(SELECT 1 FROM app_users u WHERE u.id = "{table}".app_user_id)'
        )
    )
    op.create_foreign_key(
        constraint, table, "app_users", ["app_user_id"], ["id"], ondelete="SET NULL"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("regions", sa.Column("normalized_name", sa.String(240), nullable=True))
    op.add_column("spots", sa.Column("normalized_name", sa.String(240), nullable=True))

    # PostgreSQL lower() is intentionally also the database-side canonical form
    # for migrated rows; new writes use the stricter NFKC/casefold application helper.
    for table in ("regions", "spots"):
        op.execute(
            sa.text(
                f"UPDATE {table} SET normalized_name = "
                "lower(unaccent(regexp_replace(btrim(name), '\\s+', ' ', 'g')))"
            )
        )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM regions GROUP BY normalized_name HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION 'Duplicate normalized region names must be resolved before migration';
          END IF;
          IF EXISTS (
            SELECT 1 FROM spots
            GROUP BY region_id, normalized_name
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION 'Duplicate normalized spot names per region must be resolved before migration';
          END IF;
        END $$;
        """
    )
    op.alter_column("regions", "normalized_name", existing_type=sa.String(240), nullable=False)
    op.alter_column("spots", "normalized_name", existing_type=sa.String(240), nullable=False)
    op.create_unique_constraint(
        "uq_regions_normalized_name", "regions", ["normalized_name"]
    )
    op.create_index(
        "uq_spots_region_normalized_name",
        "spots",
        ["region_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("region_id IS NOT NULL"),
    )
    op.create_index(
        "uq_spots_unassigned_normalized_name",
        "spots",
        ["normalized_name"],
        unique=True,
        postgresql_where=sa.text("region_id IS NULL"),
    )
    op.create_index(
        "ix_regions_normalized_name_trgm",
        "regions",
        ["normalized_name"],
        postgresql_using="gin",
        postgresql_ops={"normalized_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_spots_normalized_name_trgm",
        "spots",
        ["normalized_name"],
        postgresql_using="gin",
        postgresql_ops={"normalized_name": "gin_trgm_ops"},
    )

    op.drop_constraint("spots_region_id_fkey", "spots", type_="foreignkey")
    op.create_foreign_key(
        "spots_region_id_fkey",
        "spots",
        "regions",
        ["region_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    for table, constraint, index in (
        ("spot_ratings", "fk_spot_ratings_app_user", "ix_rating_app_user"),
        ("local_tips", "fk_local_tips_app_user", "ix_tip_app_user"),
        ("spot_submissions", "fk_spot_submissions_app_user", None),
        ("spot_images", "fk_spot_images_app_user", "ix_image_app_user"),
    ):
        _ugc_fk(table, constraint)
        if index:
            op.create_index(index, table, ["app_user_id"])

    op.create_index(
        "uq_submission_resulting_spot",
        "spot_submissions",
        ["resulting_spot_id"],
        unique=True,
        postgresql_where=sa.text("resulting_spot_id IS NOT NULL"),
    )

    for table, name, expression in (
        ("spots", "ck_spots_status", "status IN ('draft', 'published', 'archived')"),
        ("spots", "ck_spots_finish_rank", "finish_rank IS NULL OR finish_rank IN ('red', 'yellow', 'green')"),
        ("spots", "ck_spots_facing", "facing IS NULL OR (facing >= 0 AND facing <= 359)"),
        ("regions", "ck_regions_status", "status IN ('draft', 'published')"),
        ("admin_users", "ck_admin_users_role", "role IN ('admin', 'curator')"),
        ("board_tasks", "ck_board_tasks_status", "status IN ('open', 'done')"),
        ("spot_ratings", "ck_spot_ratings_status", "status IN ('pending', 'published', 'rejected', 'hidden')"),
        ("local_tips", "ck_local_tips_status", "status IN ('pending', 'published', 'rejected', 'hidden')"),
        ("spot_submissions", "ck_spot_submissions_status", "status IN ('pending', 'approved', 'rejected', 'merged')"),
        ("spot_images", "ck_spot_images_kind", "kind IN ('gallery', 'hero_candidate')"),
        ("spot_images", "ck_spot_images_status", "status IN ('pending', 'approved', 'published_hero', 'rejected', 'removed')"),
        ("spot_images", "ck_spot_images_report_count", "report_count >= 0"),
    ):
        _validated_check(table, name, expression)


def downgrade() -> None:
    for table, name in (
        ("spot_images", "ck_spot_images_report_count"),
        ("spot_images", "ck_spot_images_status"),
        ("spot_images", "ck_spot_images_kind"),
        ("spot_submissions", "ck_spot_submissions_status"),
        ("local_tips", "ck_local_tips_status"),
        ("spot_ratings", "ck_spot_ratings_status"),
        ("board_tasks", "ck_board_tasks_status"),
        ("admin_users", "ck_admin_users_role"),
        ("regions", "ck_regions_status"),
        ("spots", "ck_spots_facing"),
        ("spots", "ck_spots_finish_rank"),
        ("spots", "ck_spots_status"),
    ):
        op.drop_constraint(name, table, type_="check")

    op.drop_index("uq_submission_resulting_spot", table_name="spot_submissions")
    for table, constraint, index in (
        ("spot_images", "fk_spot_images_app_user", "ix_image_app_user"),
        ("spot_submissions", "fk_spot_submissions_app_user", None),
        ("local_tips", "fk_local_tips_app_user", "ix_tip_app_user"),
        ("spot_ratings", "fk_spot_ratings_app_user", "ix_rating_app_user"),
    ):
        if index:
            op.drop_index(index, table_name=table)
        op.drop_constraint(constraint, table, type_="foreignkey")

    op.drop_constraint("spots_region_id_fkey", "spots", type_="foreignkey")
    op.create_foreign_key(
        "spots_region_id_fkey",
        "spots",
        "regions",
        ["region_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("uq_spots_unassigned_normalized_name", table_name="spots")
    op.drop_index("uq_spots_region_normalized_name", table_name="spots")
    op.drop_index("ix_spots_normalized_name_trgm", table_name="spots")
    op.drop_index("ix_regions_normalized_name_trgm", table_name="regions")
    op.drop_constraint("uq_regions_normalized_name", "regions", type_="unique")
    op.drop_column("spots", "normalized_name")
    op.drop_column("regions", "normalized_name")
