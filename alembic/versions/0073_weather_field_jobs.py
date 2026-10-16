"""add weather-field worker jobs

Revision ID: 0073_weather_field_jobs
Revises: 0072_weather_field_foundation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0073_weather_field_jobs"
down_revision = "0072_weather_field_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_field_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('discover','process','retention')", name="ck_weather_field_job_kind"),
        sa.CheckConstraint("status IN ('queued','processing','succeeded','failed','superseded')", name="ck_weather_field_job_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_weather_field_job_attempts"),
        sa.ForeignKeyConstraint(["run_id"], ["weather_field_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_weather_field_job_queue", "weather_field_jobs", ["status", "scheduled_at"])
    op.create_index("ix_weather_field_job_run", "weather_field_jobs", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_weather_field_job_run", table_name="weather_field_jobs")
    op.drop_index("ix_weather_field_job_queue", table_name="weather_field_jobs")
    op.drop_table("weather_field_jobs")
