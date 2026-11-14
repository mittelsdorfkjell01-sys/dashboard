"""Record when a comment was edited by its author.

Revision ID: 0098_tip_edited_at
Revises: 0097_single_foil_variant

Authors can now change their own comment after posting. A changed comment must
say so: a reply underneath may be answering wording that no longer exists, and
silently rewriting published text is how a thread stops being a record of what
was said.

``edited_at`` is NULL for every comment as it was written, and set to the
moment of the first and every later edit. It is deliberately a timestamp rather
than a boolean so the marker can say *when*, and so an edit made within seconds
of posting can be told apart from one made a month later.
"""

from alembic import op
import sqlalchemy as sa


revision = "0098_tip_edited_at"
down_revision = "0097_single_foil_variant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("local_tips", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("local_tips", "edited_at")
