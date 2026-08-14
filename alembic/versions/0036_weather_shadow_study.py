"""add immutable phase-4 weather shadow study

Revision ID: 0036_weather_shadow_study
Revises: 0035_spot_best_months
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0036_weather_shadow_study"
down_revision = "0035_spot_best_months"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB


def _id():
    return sa.Column(
        "id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True
    )


def upgrade():
    op.create_table(
        "weather_shadow_studies",
        _id(),
        sa.Column("version", sa.String(80), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("config", JSON, nullable=False),
        sa.Column("algorithms", JSON, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('collecting','collecting_with_observation_gaps','ready_but_scheduler_pending','blocked_provider_budget','blocked_observation_source','blocked_persistence','failed_initial_cycle')",
            name="ck_weather_shadow_study_status",
        ),
    )
    op.create_table(
        "weather_shadow_runs",
        _id(),
        sa.Column(
            "study_id",
            UUID,
            sa.ForeignKey("weather_shadow_studies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("run_key", sa.String(160), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "diagnostics", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('processing','collecting','collecting_with_observation_gaps','blocked_provider_budget','failed_initial_cycle')",
            name="ck_weather_shadow_run_status",
        ),
    )
    op.create_table(
        "weather_shadow_forecasts",
        _id(),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("weather_shadow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "spot_id",
            UUID,
            sa.ForeignKey("spots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "shadow_profile_id",
            UUID,
            sa.ForeignKey("spot_geo_shadow_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("variant", sa.String(48), nullable=False),
        sa.Column("provider_model", sa.String(80), nullable=False),
        sa.Column("model_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hours", sa.Integer(), nullable=False),
        sa.Column("wind_speed_ms", sa.Float()),
        sa.Column("wind_gust_ms", sa.Float()),
        sa.Column("wind_direction_deg", sa.Float()),
        sa.Column("u_ms", sa.Float()),
        sa.Column("v_ms", sa.Float()),
        sa.Column("versions", JSON, nullable=False),
        sa.Column("provenance", JSON, nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "run_id",
            "spot_id",
            "variant",
            "provider_model",
            "model_run_at",
            "valid_at",
            "lead_hours",
            name="uq_weather_shadow_forecast_issued",
        ),
        sa.CheckConstraint(
            "lead_hours >= 0 AND lead_hours <= 300", name="ck_weather_shadow_lead"
        ),
    )
    op.create_index(
        "ix_weather_shadow_forecast_match",
        "weather_shadow_forecasts",
        ["spot_id", "valid_at", "variant"],
    )
    op.create_table(
        "weather_shadow_station_bindings",
        _id(),
        sa.Column(
            "study_id",
            UUID,
            sa.ForeignKey("weather_shadow_studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "spot_id",
            UUID,
            sa.ForeignKey("spots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("station_id", sa.String(80), nullable=False),
        sa.Column("binding_version", sa.String(64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("elevation_m", sa.Float()),
        sa.Column("measurement_height_m", sa.Float()),
        sa.Column("representativity", sa.String(24), nullable=False),
        sa.Column("metadata", JSON, nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "study_id",
            "spot_id",
            "provider",
            "station_id",
            "binding_version",
            name="uq_weather_shadow_station_binding",
        ),
    )
    op.create_table(
        "weather_shadow_observations",
        _id(),
        sa.Column(
            "binding_id",
            UUID,
            sa.ForeignKey("weather_shadow_station_bindings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("wind_speed_ms", sa.Float()),
        sa.Column("wind_gust_ms", sa.Float()),
        sa.Column("wind_direction_deg", sa.Float()),
        sa.Column("u_ms", sa.Float()),
        sa.Column("v_ms", sa.Float()),
        sa.Column("quality_status", sa.String(20), nullable=False),
        sa.Column("provider_qc", JSON, nullable=False),
        sa.Column("provenance", JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "binding_id",
            "observed_at",
            "interval_minutes",
            name="uq_weather_shadow_observation",
        ),
    )
    op.create_table(
        "weather_shadow_matches",
        _id(),
        sa.Column(
            "forecast_id",
            UUID,
            sa.ForeignKey("weather_shadow_forecasts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "observation_id",
            UUID,
            sa.ForeignKey("weather_shadow_observations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("time_delta_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "weather_shadow_metrics",
        _id(),
        sa.Column(
            "study_id",
            UUID,
            sa.ForeignKey("weather_shadow_studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension_hash", sa.String(64), nullable=False),
        sa.Column("dimensions", JSON, nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("metrics", JSON, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "study_id", "dimension_hash", name="uq_weather_shadow_metric_dimension"
        ),
    )


def downgrade():
    op.drop_table("weather_shadow_metrics")
    op.drop_table("weather_shadow_matches")
    op.drop_table("weather_shadow_observations")
    op.drop_table("weather_shadow_station_bindings")
    op.drop_index(
        "ix_weather_shadow_forecast_match", table_name="weather_shadow_forecasts"
    )
    op.drop_table("weather_shadow_forecasts")
    op.drop_table("weather_shadow_runs")
    op.drop_table("weather_shadow_studies")
