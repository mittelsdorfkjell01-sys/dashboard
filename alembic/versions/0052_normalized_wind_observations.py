"""add normalized public wind observation storage

Revision ID: 0052_normalized_wind
Revises: 0051_sector_gate_evidence

This migration is intentionally additive. Existing observations are neither
rewritten nor deleted; the new nullable columns distinguish legacy rows until
they are naturally replaced by normalized imports.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052_normalized_wind"
down_revision: Union[str, None] = "0051_sector_gate_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weather_stations", sa.Column("wigos_id", sa.String(length=80))
    )
    op.add_column(
        "weather_stations", sa.Column("icao_id", sa.String(length=16))
    )
    op.add_column(
        "weather_stations", sa.Column("measurement_height_m", sa.Float())
    )
    op.add_column(
        "weather_stations", sa.Column("license", sa.String(length=160))
    )
    op.add_column(
        "weather_stations",
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_weather_station_measurement_height",
        "weather_stations",
        "measurement_height_m IS NULL OR "
        "(measurement_height_m >= 0 AND measurement_height_m <= 300)",
    )

    op.add_column(
        "weather_observations", sa.Column("gust_period_seconds", sa.Integer())
    )
    op.add_column(
        "weather_observations", sa.Column("wind_u_ms", sa.Float())
    )
    op.add_column(
        "weather_observations", sa.Column("wind_v_ms", sa.Float())
    )
    op.add_column(
        "weather_observations",
        sa.Column("received_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "weather_observations",
        sa.Column("imported_at", sa.DateTime(timezone=True)),
    )
    op.create_check_constraint(
        "ck_weather_observation_gust_period",
        "weather_observations",
        "gust_period_seconds IS NULL OR "
        "(gust_period_seconds >= 1 AND gust_period_seconds <= 86400)",
    )

    op.create_table(
        "weather_observation_quarantine",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("station_id", postgresql.UUID(as_uuid=True)),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_station_id", sa.Text(), nullable=False),
        sa.Column("station_identity", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("import_status", sa.String(length=24), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=False),
        sa.Column(
            "data_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "normalized_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "import_status IN ('raw','rejected','quarantined')",
            name="ck_weather_observation_quarantine_status",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["weather_stations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fingerprint", name="uq_weather_observation_quarantine_fingerprint"
        ),
    )
    op.create_index(
        "ix_weather_observation_quarantine_lookup",
        "weather_observation_quarantine",
        ["provider", "provider_station_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weather_observation_quarantine_lookup",
        table_name="weather_observation_quarantine",
    )
    op.drop_table("weather_observation_quarantine")

    op.drop_constraint(
        "ck_weather_observation_gust_period",
        "weather_observations",
        type_="check",
    )
    op.drop_column("weather_observations", "imported_at")
    op.drop_column("weather_observations", "received_at")
    op.drop_column("weather_observations", "wind_v_ms")
    op.drop_column("weather_observations", "wind_u_ms")
    op.drop_column("weather_observations", "gust_period_seconds")

    op.drop_constraint(
        "ck_weather_station_measurement_height",
        "weather_stations",
        type_="check",
    )
    op.drop_column("weather_stations", "provenance")
    op.drop_column("weather_stations", "license")
    op.drop_column("weather_stations", "measurement_height_m")
    op.drop_column("weather_stations", "icao_id")
    op.drop_column("weather_stations", "wigos_id")
