"""Let an anonymous author withdraw their own comment.

Revision ID: 0099_tip_withdraw_token
Revises: 0098_tip_edited_at

Deleting a comment required an account, because ownership was proven by
``app_user_id``. Someone who posted as "Anonym" — which the composer offers on
purpose, so that reporting a hazard does not require registering first — could
never take it back.

This stores a hash of a one-time secret handed to the client at creation. The
client keeps the secret (localStorage, per comment) and sends it back to delete.
The secret itself is never stored, so a database leak does not hand anyone the
ability to delete other people's comments, and a lost secret simply means the
comment stays — the operator can still remove it.

Not tied to ``ip_hash``, which is already on the row: addresses are shared by
households, offices and whole carriers behind CGNAT, so an IP match would let
strangers delete each other's comments.
"""

from alembic import op
import sqlalchemy as sa


revision = "0099_tip_withdraw_token"
down_revision = "0098_tip_edited_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("local_tips", sa.Column("withdraw_token_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("local_tips", "withdraw_token_hash")
