"""Separate logical exact-run identity from spatial asset and sample provenance.

Revision ID: 0058_exact_dataset_identity
Revises: 0057_exact_run_baseline

All new columns are nullable. Existing per-tile baseline_bundle_hash values and
legacy activation flags remain untouched; serving explicitly excludes v1 rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0058_exact_dataset_identity"
down_revision: Union[str, None] = "0057_exact_run_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    table = "weather_station_model_residuals"
    op.add_column(table, sa.Column("dataset_bundle_hash", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("dataset_manifest", postgresql.JSONB(), nullable=True))
    op.add_column(table, sa.Column("sample_hash", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("sample_manifest", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_weather_residual_exact_identity_complete", table,
        "baseline_version <> 'exact-run-bundle-v2' OR activation_eligible = false OR "
        "(dataset_bundle_hash IS NOT NULL AND dataset_manifest IS NOT NULL "
        "AND sample_hash IS NOT NULL AND sample_manifest IS NOT NULL)",
    )
    op.create_index(
        "ix_weather_station_residual_dataset_bundle", table,
        ["dataset_bundle_hash", "observed_at"],
        postgresql_where=sa.text(
            "baseline_version = 'exact-run-bundle-v2' AND activation_eligible = true"
        ),
    )


def downgrade() -> None:
    table = "weather_station_model_residuals"
    op.drop_index("ix_weather_station_residual_dataset_bundle", table_name=table)
    op.drop_constraint("ck_weather_residual_exact_identity_complete", table, type_="check")
    for column in ("sample_manifest", "sample_hash", "dataset_manifest", "dataset_bundle_hash"):
        op.drop_column(table, column)
