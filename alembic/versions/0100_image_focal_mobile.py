"""add the mobile focal key to canonical image objects

Revision ID: 0100_image_focal_mobile
Revises: 0099_tip_withdraw_token
Create Date: 2026-11-17

The image payload is JSONB rather than a relational column.  The runtime
builder gained ``focal_mobile`` after migration 0027 had already shipped, so
existing rows need the same explicit key as newly written rows.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0100_image_focal_mobile"
down_revision: Union[str, None] = "0099_tip_withdraw_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("spots", "regions"):
        op.execute(
            f"""
            UPDATE {table}
            SET image = image || jsonb_build_object('focal_mobile', 'null'::jsonb)
            WHERE image IS NOT NULL
              AND jsonb_typeof(image) = 'object'
              AND NOT image ? 'focal_mobile'
            """
        )


def downgrade() -> None:
    for table in ("spots", "regions"):
        op.execute(
            f"""
            UPDATE {table}
            SET image = image - 'focal_mobile'
            WHERE image IS NOT NULL AND jsonb_typeof(image) = 'object'
            """
        )
