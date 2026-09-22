"""Add insert-only station provenance and scoped approval foundation.

Revision ID: 0060_station_foundation
Revises: 0059_live_wind_holdout_cases
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0060_station_foundation"
down_revision = "0059_live_wind_holdout_cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, type_ in (
        ("country_code", sa.String(3)), ("operator", sa.String(160)),
        ("station_type", sa.String(80)), ("active_from", sa.DateTime(timezone=True)),
        ("active_to", sa.DateTime(timezone=True)), ("metadata_updated_at", sa.DateTime(timezone=True)),
        ("source_url", sa.Text()), ("metadata_payload_hash", sa.String(64)),
        ("physical_station_group", sa.String(100)), ("correlation_group", sa.String(100)),
    ):
        op.add_column("weather_stations", sa.Column(name, type_))
    op.add_column("weather_stations", sa.Column("sensor_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("weather_stations", sa.Column("identity_review_status", sa.String(24), nullable=False, server_default="unreviewed"))
    for name in ("monitoring_approved", "residual_approved", "holdout_target_approved", "holdout_input_approved"):
        op.add_column("weather_stations", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_weather_station_identity_group", "weather_stations", ["physical_station_group"])
    op.create_table(
        "weather_station_metadata_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("license", sa.String(160)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("station_id", "payload_hash", name="uq_weather_station_metadata_revision"),
    )
    for name, type_ in (
        ("published_at", sa.DateTime(timezone=True)),
        ("measurement_period_seconds", sa.Integer()),
        ("averaging_period_seconds", sa.Integer()),
        ("qc_version", sa.String(80)),
        ("qc_stage", sa.String(40)),
    ):
        op.add_column("weather_observations", sa.Column(name, type_))
    op.add_column("weather_observations", sa.Column("qc_flags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.create_index("ix_weather_observation_received", "weather_observations", ["received_at"])
    op.create_table(
        "weather_observation_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_station_id", sa.String(80), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("license", sa.String(160)),
        sa.Column("parser_version", sa.String(80), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(), nullable=False),
        sa.Column("qc_version", sa.String(80), nullable=False),
        sa.Column("qc_stage", sa.String(40), nullable=False),
        sa.Column("qc_flags", postgresql.JSONB(), nullable=False),
        sa.Column("revision_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision_status IN ('current','pending_review','rejected','quarantined')", name="ck_weather_revision_status"),
        sa.UniqueConstraint("station_id", "fingerprint", name="uq_weather_revision_station_fingerprint"),
    )
    op.create_index("ix_weather_revision_station_time", "weather_observation_revisions", ["station_id", "observed_at"])
    op.create_index("uq_weather_revision_current", "weather_observation_revisions", ["station_id", "observed_at"], unique=True,
                    postgresql_where=sa.text("revision_status = 'current'"))
    op.add_column("weather_observations", sa.Column("raw_revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_observation_revisions.id")))
    op.create_table(
        "weather_station_approval_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("weather_station_approval_audit")
    op.drop_column("weather_observations", "raw_revision_id")
    op.drop_index("uq_weather_revision_current", table_name="weather_observation_revisions")
    op.drop_index("ix_weather_revision_station_time", table_name="weather_observation_revisions")
    op.drop_table("weather_observation_revisions")
    op.drop_index("ix_weather_observation_received", table_name="weather_observations")
    for name in ("qc_flags", "qc_stage", "qc_version", "averaging_period_seconds", "measurement_period_seconds", "published_at"):
        op.drop_column("weather_observations", name)
    op.drop_index("ix_weather_station_identity_group", table_name="weather_stations")
    op.drop_table("weather_station_metadata_revisions")
    for name in ("holdout_input_approved", "holdout_target_approved", "residual_approved", "monitoring_approved", "identity_review_status", "sensor_metadata", "correlation_group", "physical_station_group", "metadata_payload_hash", "source_url", "metadata_updated_at", "active_to", "active_from", "station_type", "operator", "country_code"):
        op.drop_column("weather_stations", name)
