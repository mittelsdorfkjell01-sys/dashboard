"""Persist provider resources and station-catalog scheduler state.

Revision ID: 0062_station_capture_operations
Revises: 0061_station_qualification
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0062_station_capture_operations"
down_revision = "0061_station_qualification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0061 made dossiers insert-only, but its trigger also intercepted
    # referential CASCADE cleanup. Keep direct UPDATE/DELETE forbidden while
    # allowing a deliberate parent-row deletion to complete atomically.
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_station_dossier_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF pg_trigger_depth() > 1 THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'weather_station_dossiers are immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.create_table(
        "weather_provider_http_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("resource_url", sa.Text(), nullable=False),
        sa.Column("request_variant_hash", sa.String(64), nullable=False),
        sa.Column("request_variant", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("etag", sa.Text()),
        sa.Column("last_modified", sa.Text()),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("payload_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.Text()),
        sa.Column("response_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_not_modified_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint(
            "provider", "resource_url", "request_variant_hash",
            name="uq_weather_provider_http_resource",
        ),
        sa.CheckConstraint("payload_size_bytes >= 0", name="ck_provider_http_payload_size"),
        sa.CheckConstraint("last_status_code IN (200, 304)", name="ck_provider_http_status"),
    )
    op.create_index(
        "ix_provider_http_checked", "weather_provider_http_resources",
        ["provider", "last_checked_at"],
    )
    op.create_table(
        "weather_station_catalog_states",
        sa.Column("provider", sa.String(20), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_class", sa.String(120)),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("last_counts", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            "consecutive_failures >= 0", name="ck_station_catalog_failures"
        ),
    )
    op.create_table(
        "weather_station_capture_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            "job_type IN ('observations','catalog')", name="ck_station_cycle_job_type"
        ),
        sa.CheckConstraint(
            "status IN ('success','partial','error','no_work','overlap_skipped')",
            name="ck_station_cycle_status",
        ),
    )
    op.create_index(
        "ix_station_capture_cycle_provider_time",
        "weather_station_capture_cycles",
        ["job_type", "provider", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_station_capture_cycle_provider_time",
        table_name="weather_station_capture_cycles",
    )
    op.drop_table("weather_station_capture_cycles")
    op.drop_table("weather_station_catalog_states")
    op.drop_index("ix_provider_http_checked", table_name="weather_provider_http_resources")
    op.drop_table("weather_provider_http_resources")
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_station_dossier_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'weather_station_dossiers are immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
