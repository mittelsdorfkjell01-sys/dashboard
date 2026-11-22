"""enforce catalogue-wide uniqueness for provider hero images

Revision ID: 0101_unique_media_hero
Revises: 0100_image_focal_mobile
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0101_unique_media_hero"
down_revision: Union[str, None] = "0100_image_focal_mobile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Refuse to pick an arbitrary winner when production already contains a
    # duplicate.  Operators can resolve the rows using the existing media
    # worklist and rerun the migration without silent data loss.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM media_usage
            WHERE role = 'hero' AND external_id IS NOT NULL
            GROUP BY provider, external_id
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION
              'duplicate provider heroes exist; resolve them before migration 0101';
          END IF;
        END $$;
        """
    )
    op.create_index(
        "uq_media_usage_unique_hero",
        "media_usage",
        ["provider", "external_id"],
        unique=True,
        postgresql_where=sa.text("role = 'hero' AND external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_media_usage_unique_hero", table_name="media_usage")
