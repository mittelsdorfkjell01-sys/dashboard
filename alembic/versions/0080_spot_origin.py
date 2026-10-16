"""record a spot's origin (editorial vs. community)

Adds ``spots.origin`` and ``spots.contributor_name`` so the public surfaces can
tell an editorially entered spot from one a community member proposed. The
distinction is **authorship**, not review: a community spot passes the same
admin approval, so no column here claims a quality tier.

Existing rows are editorial by default; a row that an approved
``spot_submissions`` proposal produced (``resulting_spot_id``) is back-filled to
``community`` with the submitter's name as the credit.

Revision ID: 0080_spot_origin
Revises: 0079_tide_platform_foundation
"""

from alembic import op
import sqlalchemy as sa


revision = "0080_spot_origin"
down_revision = "0079_tide_platform_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spots",
        sa.Column(
            "origin",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'editorial'"),
        ),
    )
    op.add_column("spots", sa.Column("contributor_name", sa.String(length=120), nullable=True))
    op.create_check_constraint(
        "ck_spots_origin",
        "spots",
        "origin IN ('editorial', 'community')",
    )
    op.execute(
        """
        UPDATE spots AS s
           SET origin = 'community',
               contributor_name = sub.submitter_name
          FROM spot_submissions AS sub
         WHERE sub.resulting_spot_id = s.id
        """
    )
    op.create_index("ix_spots_origin", "spots", ["origin"])


def downgrade() -> None:
    op.drop_index("ix_spots_origin", table_name="spots")
    op.drop_constraint("ck_spots_origin", "spots", type_="check")
    op.drop_column("spots", "contributor_name")
    op.drop_column("spots", "origin")
