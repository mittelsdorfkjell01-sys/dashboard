"""Add fail-closed station epochs, availability and review evidence.

Revision ID: 0061_station_qualification
Revises: 0060_station_foundation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0061_station_qualification"
down_revision = "0060_station_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_station_epochs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("epoch_number", sa.Integer(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("metadata_revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_station_metadata_revisions.id")),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("reviewer", sa.String(160)),
        sa.Column("review_reason", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("station_id", "epoch_number", name="uq_station_epoch_number"),
        sa.UniqueConstraint("station_id", "configuration_hash", name="uq_station_epoch_configuration"),
        sa.CheckConstraint("status IN ('pending_review','reviewed','superseded')", name="ck_station_epoch_status"),
    )
    op.create_index("ix_station_epoch_status", "weather_station_epochs", ["station_id", "status"])
    op.add_column("weather_stations", sa.Column("current_epoch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_station_epochs.id")))
    op.add_column("weather_observations", sa.Column("epoch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_station_epochs.id")))
    op.add_column("weather_observations", sa.Column("availability_class", sa.String(32), nullable=False, server_default="availability_unproven"))
    op.create_check_constraint(
        "ck_weather_observation_availability",
        "weather_observations",
        "availability_class IN ('captured_operationally','historical_backfill','availability_unproven')",
    )
    op.add_column("weather_observations", sa.Column("first_seen_at", sa.DateTime(timezone=True)))
    op.create_index("ix_observation_epoch_time", "weather_observations", ["epoch_id", "observed_at"])
    op.add_column("weather_observation_revisions", sa.Column("epoch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_station_epochs.id")))
    op.add_column("weather_observation_revisions", sa.Column("availability_class", sa.String(32), nullable=False, server_default="availability_unproven"))
    op.create_check_constraint(
        "ck_weather_revision_availability",
        "weather_observation_revisions",
        "availability_class IN ('captured_operationally','historical_backfill','availability_unproven')",
    )
    op.add_column("weather_observation_revisions", sa.Column("first_seen_at", sa.DateTime(timezone=True)))
    op.add_column("weather_observation_revisions", sa.Column("revised_at", sa.DateTime(timezone=True)))
    op.create_index("ix_revision_epoch_time", "weather_observation_revisions", ["epoch_id", "observed_at"])
    op.create_table(
        "weather_station_dossiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("epoch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_station_epochs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dossier_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("ready_for_review", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dossier_epoch_generated", "weather_station_dossiers", ["epoch_id", "generated_at"])
    op.execute("""
        CREATE FUNCTION reject_station_dossier_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'weather_station_dossiers are immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_station_dossier_immutable
        BEFORE UPDATE OR DELETE ON weather_station_dossiers
        FOR EACH ROW EXECUTE FUNCTION reject_station_dossier_mutation()
    """)
    op.create_table(
        "weather_station_group_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("epoch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_station_epochs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_type", sa.String(24), nullable=False),
        sa.Column("group_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rule_version", sa.String(80), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("actor", sa.String(160)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("group_type IN ('physical','sensor','correlation')", name="ck_station_group_type"),
        sa.CheckConstraint("status IN ('proposed','confirmed','rejected')", name="ck_station_group_status"),
    )
    op.create_index("ix_group_decision_epoch_type_time", "weather_station_group_decisions", ["epoch_id", "group_type", "decided_at"])
    op.create_index("uq_station_group_proposal", "weather_station_group_decisions",
                    ["epoch_id", "group_type", "group_key"], unique=True,
                    postgresql_where=sa.text("status = 'proposed'"))
    for name, type_ in (
        ("epoch_id", postgresql.UUID(as_uuid=True)), ("dossier_hash", sa.String(64)),
        ("policy_version", sa.String(80)), ("group_version", sa.String(80)),
        ("expires_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("weather_station_approval_audit", sa.Column(name, type_))
    op.create_foreign_key("fk_station_approval_epoch", "weather_station_approval_audit", "weather_station_epochs", ["epoch_id"], ["id"])
    op.create_index("ix_station_approval_epoch_scope_time", "weather_station_approval_audit", ["epoch_id", "scope", "decided_at"])
    op.create_table(
        "weather_station_provider_cursors",
        sa.Column("provider", sa.String(20), primary_key=True),
        sa.Column("watermark_at", sa.DateTime(timezone=True)),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_cycle_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_class", sa.String(120)),
    )


def downgrade() -> None:
    op.drop_table("weather_station_provider_cursors")
    op.drop_index("ix_station_approval_epoch_scope_time", table_name="weather_station_approval_audit")
    op.drop_constraint("fk_station_approval_epoch", "weather_station_approval_audit", type_="foreignkey")
    for name in ("expires_at", "group_version", "policy_version", "dossier_hash", "epoch_id"):
        op.drop_column("weather_station_approval_audit", name)
    op.drop_index("uq_station_group_proposal", table_name="weather_station_group_decisions")
    op.drop_index("ix_group_decision_epoch_type_time", table_name="weather_station_group_decisions")
    op.drop_table("weather_station_group_decisions")
    op.execute("DROP TRIGGER trg_station_dossier_immutable ON weather_station_dossiers")
    op.execute("DROP FUNCTION reject_station_dossier_mutation()")
    op.drop_index("ix_dossier_epoch_generated", table_name="weather_station_dossiers")
    op.drop_table("weather_station_dossiers")
    op.drop_index("ix_revision_epoch_time", table_name="weather_observation_revisions")
    op.drop_constraint("ck_weather_revision_availability", "weather_observation_revisions", type_="check")
    for name in ("revised_at", "first_seen_at", "availability_class", "epoch_id"):
        op.drop_column("weather_observation_revisions", name)
    op.drop_index("ix_observation_epoch_time", table_name="weather_observations")
    op.drop_constraint("ck_weather_observation_availability", "weather_observations", type_="check")
    for name in ("first_seen_at", "availability_class", "epoch_id"):
        op.drop_column("weather_observations", name)
    op.drop_column("weather_stations", "current_epoch_id")
    op.drop_index("ix_station_epoch_status", table_name="weather_station_epochs")
    op.drop_table("weather_station_epochs")
