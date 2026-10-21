"""add optional editorial spot classification

Revision ID: 0081_spot_editorial_classification
Revises: 0080_spot_origin
"""

from alembic import op
import sqlalchemy as sa


revision = "0081_spot_editorial_classification"
down_revision = "0080_spot_origin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spots",
        sa.Column("editorial_classification", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_spots_editorial_classification",
        "spots",
        "editorial_classification IS NULL OR editorial_classification IN "
        "('world_class', 'worth_trip', 'worth_checking_out')",
    )
    # The agreed initial editorial assignment applies only to the public
    # catalogue at migration time. Drafts and archived rows remain untouched;
    # the nullable column has no default, so later rows also start unranked.
    op.execute(
        "UPDATE spots SET editorial_classification = 'world_class' "
        "WHERE status = 'published'"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_spots_editorial_classification", "spots", type_="check"
    )
    op.drop_column("spots", "editorial_classification")
