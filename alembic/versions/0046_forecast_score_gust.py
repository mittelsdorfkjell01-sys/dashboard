"""add gust_mae_ms to forecast verification scores

Revision ID: 0046_forecast_score_gust
Revises: 0045_forecast_verify_scores
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_forecast_score_gust"
down_revision: Union[str, None] = "0045_forecast_verify_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forecast_verification_scores", sa.Column("gust_mae_ms", sa.Float()))


def downgrade() -> None:
    op.drop_column("forecast_verification_scores", "gust_mae_ms")
