"""Complete the manual trip planner sharing and day structure.

Revision ID: 0093_trip_planner_v2
Revises: 0092_fix_supertubos
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0093_trip_planner_v2"
down_revision = "0092_fix_supertubos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("days", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("trips", sa.Column("share_token", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("trips", sa.Column("share_notes", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_check_constraint("ck_trips_days_array", "trips", "jsonb_typeof(days) = 'array'")
    op.create_unique_constraint("uq_trips_share_token", "trips", ["share_token"])
    op.add_column("trip_stops", sa.Column("role", sa.String(20), server_default=sa.text("'alternative'"), nullable=False))
    op.add_column("trip_stops", sa.Column("spot_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_trip_stops_role", "trip_stops", "role IN ('main','alternative')")


def downgrade() -> None:
    op.drop_constraint("ck_trip_stops_role", "trip_stops", type_="check")
    op.drop_column("trip_stops", "spot_updated_at")
    op.drop_column("trip_stops", "role")
    op.drop_constraint("uq_trips_share_token", "trips", type_="unique")
    op.drop_constraint("ck_trips_days_array", "trips", type_="check")
    op.drop_column("trips", "share_notes")
    op.drop_column("trips", "share_token")
    op.drop_column("trips", "days")
