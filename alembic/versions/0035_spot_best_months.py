"""persisted best-months per spot (tile display)

Revision ID: 0035_spot_best_months
Revises: 0034_geodata_shadow_phase2
"""

from alembic import op
import sqlalchemy as sa

revision = "0035_spot_best_months"
down_revision = "0034_geodata_shadow_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spots",
        sa.Column("best_months", sa.ARRAY(sa.SmallInteger()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("spots", "best_months")
