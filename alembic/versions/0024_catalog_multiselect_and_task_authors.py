"""bottom multi-select, three skill levels, stable board authors

Revision ID: 0024_catalog_axes
Revises: 0023_admin_totp
Create Date: 2026-08-06

Existing bottom scalars are wrapped losslessly in arrays. Skill levels map
``intermediate`` to ``advanced`` and ``pro`` to ``expert``; duplicates caused
by the merge are removed. The same vocabulary migration is applied to historic
ratings. Board author emails remain stored for audit compatibility, while a
nullable user foreign key is backfilled for display-name resolution.

Downgrade restores a representative scalar bottom value (the first item) and
maps ``expert`` back to ``pro``. The intermediate/advanced distinction cannot
be reconstructed after the intentional merge.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_catalog_axes"
down_revision: Union[str, None] = "0023_admin_totp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE spots
            ALTER COLUMN bottom_type TYPE varchar[] USING (
                CASE WHEN bottom_type IS NULL OR btrim(bottom_type) = ''
                     THEN ARRAY[]::varchar[] ELSE ARRAY[bottom_type]::varchar[] END
            ),
            ALTER COLUMN bottom_type SET DEFAULT '{}'::varchar[],
            ALTER COLUMN bottom_type SET NOT NULL
        """
    )
    op.create_index("ix_spots_bottom_type", "spots", ["bottom_type"], postgresql_using="gin")

    op.execute(
        """
        UPDATE spots SET level = array_remove(ARRAY[
            CASE WHEN 'beginner' = ANY(level) THEN 'beginner' END,
            CASE WHEN 'intermediate' = ANY(level) OR 'advanced' = ANY(level)
                 THEN 'advanced' END,
            CASE WHEN 'pro' = ANY(level) OR 'expert' = ANY(level) THEN 'expert' END,
            CASE WHEN 'n/a' = ANY(level) THEN 'n/a' END
        ]::varchar[], NULL)
        """
    )
    op.execute(
        """
        UPDATE spot_ratings SET skill_level = CASE skill_level
            WHEN 'intermediate' THEN 'advanced'
            WHEN 'pro' THEN 'expert'
            ELSE skill_level END
        """
    )

    op.add_column(
        "board_tasks",
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_board_tasks_author_user_id_admin_users", "board_tasks", "admin_users",
        ["author_user_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_board_tasks_author_user_id", "board_tasks", ["author_user_id"])
    op.execute(
        """
        UPDATE board_tasks AS task SET author_user_id = admin_user.id
        FROM admin_users AS admin_user
        WHERE task.author_user_id IS NULL
          AND lower(task.author) = lower(admin_user.email)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_board_tasks_author_user_id", table_name="board_tasks")
    op.drop_constraint(
        "fk_board_tasks_author_user_id_admin_users", "board_tasks", type_="foreignkey"
    )
    op.drop_column("board_tasks", "author_user_id")

    op.execute(
        """
        UPDATE spot_ratings SET skill_level = CASE skill_level
            WHEN 'expert' THEN 'pro' ELSE skill_level END
        """
    )
    op.execute(
        """
        UPDATE spots SET level = array_replace(level, 'expert', 'pro')
        """
    )

    op.drop_index("ix_spots_bottom_type", table_name="spots")
    op.execute(
        """
        ALTER TABLE spots
            ALTER COLUMN bottom_type DROP DEFAULT,
            ALTER COLUMN bottom_type DROP NOT NULL,
            ALTER COLUMN bottom_type TYPE varchar(30) USING (
                CASE WHEN array_length(bottom_type, 1) IS NULL THEN NULL
                     ELSE bottom_type[1] END
            )
        """
    )
