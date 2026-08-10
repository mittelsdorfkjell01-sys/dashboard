"""add reviewed spot weather profiles and versioned sector corrections

Revision ID: 0028_weather_profiles
Revises: 0027_media_provenance
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_weather_profiles"
down_revision: Union[str, None] = "0027_media_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_users", sa.Column("wind_unit", sa.String(8), server_default=sa.text("'kn'"), nullable=False))
    op.create_check_constraint("ck_app_users_wind_unit", "app_users", "wind_unit IN ('kn','kmh','ms')")
    op.create_table(
        "spot_weather_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(64)), sa.Column("elevation_m", sa.Float()),
        sa.Column("coastal_normal_deg", sa.Float()), sa.Column("exposure", sa.String(20)),
        sa.Column("roughness_length_m", sa.Float()), sa.Column("land_reference", postgresql.JSONB()),
        sa.Column("water_reference", postgresql.JSONB()),
        sa.Column("quality_tier", sa.String(20), server_default=sa.text("'coordinates'"), nullable=False),
        sa.Column("physics_version", sa.String(40), server_default=sa.text("'wind-v1'"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("coastal_normal_deg IS NULL OR (coastal_normal_deg >= 0 AND coastal_normal_deg < 360)", name="ck_weather_profile_coastal_normal"),
        sa.CheckConstraint("elevation_m IS NULL OR elevation_m >= -500", name="ck_weather_profile_elevation"),
        sa.CheckConstraint("roughness_length_m IS NULL OR roughness_length_m > 0", name="ck_weather_profile_roughness"),
        sa.CheckConstraint("quality_tier IN ('coordinates','coastal','extended','advanced')", name="ck_weather_profile_tier"),
        sa.CheckConstraint("exposure IS NULL OR exposure IN ('sheltered','neutral','exposed')", name="ck_weather_profile_exposure"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("spot_id"),
    )
    op.create_table(
        "spot_weather_sectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_deg", sa.Float(), nullable=False), sa.Column("end_deg", sa.Float(), nullable=False),
        sa.Column("speed_factor", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("direction_offset_deg", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("start_deg >= 0 AND start_deg < 360", name="ck_weather_sector_start"),
        sa.CheckConstraint("end_deg >= 0 AND end_deg < 360", name="ck_weather_sector_end"),
        sa.CheckConstraint("speed_factor >= 0.60 AND speed_factor <= 1.35", name="ck_weather_sector_factor"),
        sa.CheckConstraint("direction_offset_deg >= -15 AND direction_offset_deg <= 15", name="ck_weather_sector_direction"),
        sa.ForeignKeyConstraint(["profile_id"], ["spot_weather_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "start_deg", "end_deg", "version", name="uq_weather_sector_version"),
    )
    op.create_index("ix_weather_sector_profile", "spot_weather_sectors", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_weather_sector_profile", table_name="spot_weather_sectors")
    op.drop_table("spot_weather_sectors")
    op.drop_table("spot_weather_profiles")
    op.drop_constraint("ck_app_users_wind_unit", "app_users", type_="check")
    op.drop_column("app_users", "wind_unit")
