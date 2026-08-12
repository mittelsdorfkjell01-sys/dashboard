"""add versioned Surfwinddata forecast system

Revision ID: 0032_forecast_system
Revises: 0031_community_upvotes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0032_forecast_system"
down_revision = "0031_community_upvotes"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB
def ident(): return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True)
def stamps(): return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]

def upgrade():
    op.create_table("forecast_providers", ident(), sa.Column("key",sa.String(40),nullable=False,unique=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("provider_type",sa.String(20),nullable=False),sa.Column("enabled",sa.Boolean(),server_default=sa.text("false"),nullable=False),sa.Column("licence",sa.String(120),nullable=False),sa.Column("attribution",sa.Text(),nullable=False),sa.Column("official_url",sa.Text(),nullable=False),sa.Column("commercial_review_required",sa.Boolean(),server_default=sa.text("true"),nullable=False),sa.Column("metadata",JSON,server_default=sa.text("'{}'::jsonb"),nullable=False),*stamps())
    op.create_table("forecast_model_runs",ident(),sa.Column("provider_key",sa.String(40),nullable=False),sa.Column("model_key",sa.String(80),nullable=False),sa.Column("dataset_version",sa.String(80)),sa.Column("run_at",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("checksum",sa.String(128)),sa.Column("bytes_downloaded",sa.Integer(),server_default="0",nullable=False),sa.Column("valid_until",sa.DateTime(timezone=True)),sa.Column("diagnostics",JSON,server_default=sa.text("'{}'::jsonb"),nullable=False),*stamps(),sa.UniqueConstraint("provider_key","model_key","run_at",name="uq_forecast_model_run"),sa.CheckConstraint("status IN ('detected','downloading','validating','ready','failed','expired')",name="ck_forecast_model_run_status"))
    op.create_index("ix_forecast_model_run_latest","forecast_model_runs",["provider_key","model_key","run_at"])
    op.create_table("spot_geo_profile_versions",ident(),sa.Column("spot_id",UUID,sa.ForeignKey("spots.id",ondelete="CASCADE"),nullable=False),sa.Column("version",sa.Integer(),nullable=False),sa.Column("algorithm_version",sa.String(40),nullable=False),sa.Column("coordinate_hash",sa.String(64),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("quality",sa.String(20),nullable=False),sa.Column("sources",JSON,server_default=sa.text("'[]'::jsonb"),nullable=False),sa.Column("profile",JSON,server_default=sa.text("'{}'::jsonb"),nullable=False),sa.Column("warnings",JSON,server_default=sa.text("'[]'::jsonb"),nullable=False),sa.Column("active",sa.Boolean(),server_default=sa.text("false"),nullable=False),*stamps(),sa.UniqueConstraint("spot_id","version",name="uq_spot_geo_profile_version"),sa.UniqueConstraint("spot_id","coordinate_hash","algorithm_version",name="uq_spot_geo_profile_input"),sa.CheckConstraint("status IN ('pending','processing','ready','failed','stale')",name="ck_spot_geo_profile_status"))
    op.create_index("ix_spot_geo_profile_active","spot_geo_profile_versions",["spot_id","active"])
    op.create_table("forecast_snapshots",ident(),sa.Column("spot_id",UUID,sa.ForeignKey("spots.id",ondelete="CASCADE"),nullable=False),sa.Column("generated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("valid_until",sa.DateTime(timezone=True),nullable=False),sa.Column("consensus_version",sa.String(40),nullable=False),sa.Column("physics_version",sa.String(40),nullable=False),sa.Column("geo_profile_id",UUID,sa.ForeignKey("spot_geo_profile_versions.id",ondelete="SET NULL")),sa.Column("quality_level",sa.String(32),nullable=False),sa.Column("fallback_status",sa.String(40),nullable=False),sa.Column("payload",JSON,nullable=False),sa.Column("internal",JSON,server_default=sa.text("'{}'::jsonb"),nullable=False),sa.Column("attributions",JSON,server_default=sa.text("'[]'::jsonb"),nullable=False),sa.Column("active",sa.Boolean(),server_default=sa.text("false"),nullable=False),*stamps(),sa.CheckConstraint("quality_level IN ('baseline','automatic','calibrated','reviewed')",name="ck_forecast_snapshot_quality"))
    op.create_index("ix_forecast_snapshot_active","forecast_snapshots",["spot_id","active"]); op.create_index("ix_forecast_snapshot_generated","forecast_snapshots",["spot_id","generated_at"])
    op.create_table("forecast_processing_jobs",ident(),sa.Column("spot_id",UUID,sa.ForeignKey("spots.id",ondelete="CASCADE")),sa.Column("kind",sa.String(32),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("idempotency_key",sa.String(160),nullable=False,unique=True),sa.Column("requested_by",sa.String(160)),sa.Column("progress",sa.Integer(),server_default="0",nullable=False),sa.Column("attempt_count",sa.Integer(),server_default="0",nullable=False),sa.Column("options",JSON,server_default=sa.text("'{}'::jsonb"),nullable=False),sa.Column("diagnostics",JSON,server_default=sa.text("'{}'::jsonb"),nullable=False),sa.Column("error",sa.Text()),sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("finished_at",sa.DateTime(timezone=True)),*stamps(),sa.CheckConstraint("status IN ('queued','processing','succeeded','failed','superseded','paused')",name="ck_forecast_processing_job_status"),sa.CheckConstraint("progress >= 0 AND progress <= 100",name="ck_forecast_processing_job_progress"))
    op.create_index("ix_forecast_job_queue","forecast_processing_jobs",["status","created_at"]); op.create_index("ix_forecast_job_spot","forecast_processing_jobs",["spot_id","created_at"])

def downgrade():
    for table in ("forecast_processing_jobs","forecast_snapshots","spot_geo_profile_versions","forecast_model_runs","forecast_providers"):
        op.drop_table(table)
