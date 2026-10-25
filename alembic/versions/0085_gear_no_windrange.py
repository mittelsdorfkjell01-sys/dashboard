"""remove numeric wind ranges from gear data

Revision ID: 0085_gear_no_windrange
Revises: 0084_gear_usage_compatibility
"""

from alembic import op
import sqlalchemy as sa


revision = "0085_gear_no_windrange"
down_revision = "0084_gear_usage_compatibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Gear suitability remains qualitative (for example strong_wind). Numeric
    # size wind ranges are intentionally not part of this catalogue contract.
    op.execute("DELETE FROM gear_claims WHERE field_name = 'wind_range'")
    op.drop_constraint(
        "ck_gear_use_profiles_wind_range", "gear_use_profiles", type_="check"
    )
    op.drop_column("gear_use_profiles", "wind_max_kn")
    op.drop_column("gear_use_profiles", "wind_min_kn")


def downgrade() -> None:
    op.add_column("gear_use_profiles", sa.Column("wind_min_kn", sa.Numeric(6, 2)))
    op.add_column("gear_use_profiles", sa.Column("wind_max_kn", sa.Numeric(6, 2)))
    op.create_check_constraint(
        "ck_gear_use_profiles_wind_range",
        "gear_use_profiles",
        "(wind_min_kn IS NULL AND wind_max_kn IS NULL) OR "
        "(wind_min_kn >= 0 AND wind_max_kn > wind_min_kn)",
    )
    # Restore the sole wind-range claim that existed in the 0084 seed state.
    op.execute(
        """
        INSERT INTO gear_claims (
            id, product_version_id, size_variant_id, color_variant_id,
            field_name, value, unit, source_id, verification_status,
            verified_at, uncertainty_note
        )
        SELECT
            '70000000-0000-0000-0000-000000000007'::uuid,
            '30000000-0000-0000-0000-000000000003'::uuid,
            '40000000-0000-0000-0000-000000000003'::uuid,
            NULL, 'wind_range', '{"min": 15, "max": 30}'::jsonb, 'kn',
            '60000000-0000-0000-0000-000000000004'::uuid,
            'verified', now(), NULL
        WHERE EXISTS (
            SELECT 1 FROM gear_product_versions
            WHERE id = '30000000-0000-0000-0000-000000000003'::uuid
        )
        AND NOT EXISTS (
            SELECT 1 FROM gear_claims
            WHERE id = '70000000-0000-0000-0000-000000000007'::uuid
        )
        """
    )
