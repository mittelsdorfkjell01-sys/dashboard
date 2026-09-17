"""add observable station import state

Revision ID: 0053_observation_import_state
Revises: 0052_normalized_wind

The table is additive and stores only the latest sanitized operational state.
It does not rewrite or delete station observations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0053_observation_import_state"
down_revision: Union[str, None] = "0052_normalized_wind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_observation_import_states",
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("error_class", sa.String(length=120)),
        sa.Column(
            "consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "last_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('success','error')",
            name="ck_weather_observation_import_state_status",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_weather_observation_import_state_failures",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["weather_stations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("station_id"),
    )
    op.create_index(
        "ix_weather_observation_import_state_provider_status",
        "weather_observation_import_states",
        ["provider", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weather_observation_import_state_provider_status",
        table_name="weather_observation_import_states",
    )
    op.drop_table("weather_observation_import_states")
