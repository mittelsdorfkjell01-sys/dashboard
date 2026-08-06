"""versioned tide profiles and precomputed events

Revision ID: 0025_tides
Revises: 0024_catalog_axes
Create Date: 2026-08-06

Existing spots intentionally receive no profile. Tide publication therefore
remains fail-closed until an operator configures and reviews each spot.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0025_tides"
down_revision: Union[str, None] = "0024_catalog_axes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tide_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("public_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("timezone", sa.String(80)),
        sa.Column("model_name", sa.String(40), server_default="FES2022b", nullable=False),
        sa.Column("model_version", sa.String(40), server_default="2022b", nullable=False),
        sa.Column("automatic_anchor", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column("manual_anchor", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column("anchor_distance_m", sa.Float()),
        sa.Column("anchor_kind", sa.String(30)),
        sa.Column("anchor_status", sa.String(30), server_default="needs_review", nullable=False),
        sa.Column("anchor_determined_at", sa.DateTime(timezone=True)),
        sa.Column("anchor_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("anchor_warnings", postgresql.JSONB()),
        sa.Column("global_offset_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("high_offset_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("low_offset_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("constituent_adjustments", postgresql.JSONB()),
        sa.Column("manual_uncertainty_minutes", sa.Integer()),
        sa.Column("estimated_uncertainty_minutes", sa.Integer()),
        sa.Column("uncertainty_source", sa.String(80)),
        sa.Column("quality_status", sa.String(30), server_default="unavailable", nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("correction_reason", sa.Text()),
        sa.Column("correction_source", sa.Text()),
        sa.Column("edited_by", sa.String(120)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True)),
        sa.Column("calculation_status", sa.String(30), server_default="not_configured", nullable=False),
        sa.Column("calculation_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("spot_id"),
        sa.CheckConstraint("version > 0", name="ck_tide_profiles_version"),
        sa.CheckConstraint("anchor_status IN ('needs_review','auto_selected','reviewed','invalid')", name="ck_tide_profiles_anchor_status"),
        sa.CheckConstraint("quality_status IN ('unavailable','model_only','reviewed_anchor','manual_calibrated','gauge_calibrated')", name="ck_tide_profiles_quality"),
        sa.CheckConstraint("calculation_status IN ('not_configured','queued','running','ready','failed','stale')", name="ck_tide_profiles_calculation_status"),
        sa.CheckConstraint("anchor_distance_m IS NULL OR anchor_distance_m >= 0", name="ck_tide_profiles_anchor_distance"),
        sa.CheckConstraint("manual_uncertainty_minutes IS NULL OR manual_uncertainty_minutes >= 0", name="ck_tide_profiles_manual_uncertainty"),
        sa.CheckConstraint("estimated_uncertainty_minutes IS NULL OR estimated_uncertainty_minutes >= 0", name="ck_tide_profiles_estimated_uncertainty"),
    )
    op.create_index("ix_tide_profiles_due", "tide_profiles", ["enabled", "calculation_status", "last_calculated_at"])
    op.create_index("ix_tide_profiles_automatic_anchor", "tide_profiles", ["automatic_anchor"], postgresql_using="gist")
    op.create_index("ix_tide_profiles_manual_anchor", "tide_profiles", ["manual_anchor"], postgresql_using="gist")

    op.create_table(
        "tide_profile_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["tide_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "version", name="uq_tide_profile_revision_version"),
    )
    op.create_index("ix_tide_profile_revisions_spot", "tide_profile_revisions", ["spot_id", "created_at"])

    op.create_table(
        "tide_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("cycle_key", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(8), nullable=False),
        sa.Column("raw_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("corrected_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relative_height", sa.Float()),
        sa.Column("uncertainty_minutes", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_name", sa.String(40), nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), server_default="valid", nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spot_id", "profile_version", "cycle_key", name="uq_tide_events_cycle"),
        sa.CheckConstraint("event_type IN ('high','low')", name="ck_tide_events_type"),
        sa.CheckConstraint("status IN ('valid','superseded')", name="ck_tide_events_status"),
        sa.CheckConstraint("uncertainty_minutes >= 0", name="ck_tide_events_uncertainty"),
    )
    op.create_index("ix_tide_events_public", "tide_events", ["spot_id", "corrected_time", "status"])

    op.create_table(
        "tide_event_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(8), nullable=False),
        sa.Column("raw_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_model_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("manual_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("difference_minutes", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(20), server_default="single", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False), sa.Column("source", sa.Text()),
        sa.Column("actor", sa.String(120)), sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("event_type IN ('high','low')", name="ck_tide_event_overrides_type"),
        sa.CheckConstraint("scope IN ('single','high_profile','low_profile','calibration_input')", name="ck_tide_event_overrides_scope"),
    )
    op.create_index("ix_tide_event_overrides_match", "tide_event_overrides", ["spot_id", "event_type", "raw_time", "active"])

    op.create_table(
        "tide_calculation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True)), sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("requested_by", sa.String(120)), sa.Column("model_name", sa.String(40), server_default="FES2022b", nullable=False),
        sa.Column("model_version", sa.String(40), server_default="2022b", nullable=False), sa.Column("algorithm_version", sa.String(40), nullable=False),
        sa.Column("profile_version", sa.Integer()), sa.Column("processed_spots", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_spots", sa.Integer(), server_default="0", nullable=False), sa.Column("details", postgresql.JSONB()),
        sa.Column("error", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','partial','failed')", name="ck_tide_calculation_runs_status"),
    )
    op.create_index("ix_tide_calculation_runs_queue", "tide_calculation_runs", ["status", "created_at"])
    op.create_index("ix_tide_calculation_runs_spot", "tide_calculation_runs", ["spot_id", "created_at"])


def downgrade() -> None:
    op.drop_table("tide_calculation_runs")
    op.drop_table("tide_event_overrides")
    op.drop_table("tide_events")
    op.drop_table("tide_profile_revisions")
    op.drop_table("tide_profiles")
