"""Manual account trip planner.

Revision ID: 0089_trip_planner
Revises: 0088_region_content
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0089_trip_planner"
down_revision = "0088_region_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checklist", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_trips_date_order"),
        sa.CheckConstraint("status IN ('draft','planned','completed','cancelled')", name="ck_trips_status"),
        sa.CheckConstraint("jsonb_typeof(checklist) = 'array'", name="ck_trips_checklist_array"),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trips_user_dates", "trips", ["app_user_id", "start_date", "end_date"])
    op.create_table(
        "trip_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("spot_name", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_trip_stops_position"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "position", name="uq_trip_stops_position"),
    )
    op.create_index("ix_trip_stops_spot", "trip_stops", ["spot_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_stops_spot", table_name="trip_stops")
    op.drop_table("trip_stops")
    op.drop_index("ix_trips_user_dates", table_name="trips")
    op.drop_table("trips")
