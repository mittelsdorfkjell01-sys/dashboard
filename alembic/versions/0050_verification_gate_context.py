"""bind WP1 verification scores to the effective serving context

Revision ID: 0050_verification_gate_context
Revises: 0049_disable_ungated_sectors
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050_verification_gate_context"
down_revision: Union[str, None] = "0049_disable_ungated_sectors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "forecast_verification_scores",
        sa.Column("gate_context_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("forecast_verification_scores", "gate_context_hash")
