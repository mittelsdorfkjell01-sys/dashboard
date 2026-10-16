"""add European tide station and harmonic evidence foundation

Revision ID: 0079_tide_platform_foundation
Revises: 0078_europe_wind_campaign
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql


revision = "0079_tide_platform_foundation"
down_revision = "0078_europe_wind_campaign"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tide_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("canonical_key", sa.String(160), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("operator", sa.String(160)),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("basin", sa.String(80)),
        sa.Column("timezone", sa.String(80)),
        sa.Column("status", sa.String(20), server_default="unknown", nullable=False),
        sa.Column("public_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("quality_status", sa.String(30), server_default="unreviewed", nullable=False),
        sa.Column("latest_observation_at", sa.DateTime(timezone=True)),
        sa.Column("station_metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key"),
        sa.CheckConstraint("status IN ('unknown','active','inactive')", name="ck_tide_stations_status"),
        sa.CheckConstraint("quality_status IN ('unreviewed','raw','automatic_qc','validated','rejected')", name="ck_tide_stations_quality"),
    )
    op.create_index("ix_tide_stations_location", "tide_stations", ["location"], postgresql_using="gist")
    op.create_index("ix_tide_stations_public", "tide_stations", ["public_enabled", "status", "latest_observation_at"])

    op.create_table(
        "tide_station_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_station_id", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("attribution", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["station_id"], ["tide_stations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_station_id", name="uq_tide_station_provider_id"),
    )
    op.create_index("ix_tide_station_alias_station", "tide_station_aliases", ["station_id"])

    op.create_table(
        "tide_sensors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_sensor_id", sa.String(160), nullable=False),
        sa.Column("parameter", sa.String(40), server_default="water_level", nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("vertical_datum", sa.String(120)),
        sa.Column("gauge_zero_m", sa.Float()),
        sa.Column("cadence_seconds", sa.Integer()),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sensor_metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["station_id"], ["tide_stations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_sensor_id", name="uq_tide_sensor_provider_id"),
        sa.CheckConstraint("cadence_seconds IS NULL OR cadence_seconds > 0", name="ck_tide_sensor_cadence"),
    )
    op.create_index("ix_tide_sensors_station", "tide_sensors", ["station_id", "active"])

    op.create_table(
        "tide_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_m", sa.Float(), nullable=False),
        sa.Column("vertical_datum", sa.String(120)),
        sa.Column("quality_status", sa.String(30), server_default="raw", nullable=False),
        sa.Column("provider_flags", postgresql.JSONB()),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sensor_id"], ["tide_sensors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sensor_id", "observed_at", "payload_sha256", name="uq_tide_observation_evidence"),
        sa.CheckConstraint("quality_status IN ('raw','automatic_qc','validated','rejected')", name="ck_tide_observations_quality"),
    )
    op.create_index("ix_tide_observations_sensor_time", "tide_observations", ["sensor_id", "observed_at"])

    op.create_table(
        "tide_harmonic_solutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("algorithm_version", sa.String(40), nullable=False),
        sa.Column("training_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("constituents", postgresql.JSONB(), nullable=False),
        sa.Column("holdout_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="candidate", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["station_id"], ["tide_stations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("training_until > training_from", name="ck_tide_harmonic_training"),
        sa.CheckConstraint("status IN ('candidate','validated','rejected','superseded')", name="ck_tide_harmonic_status"),
    )
    op.create_index("ix_tide_harmonic_station_status", "tide_harmonic_solutions", ["station_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_table("tide_harmonic_solutions")
    op.drop_table("tide_observations")
    op.drop_table("tide_sensors")
    op.drop_table("tide_station_aliases")
    op.drop_table("tide_stations")
