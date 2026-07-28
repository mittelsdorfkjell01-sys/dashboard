"""drop the usable_wind_directions readiness requirement

Revision ID: 0013_drop_wind_dir_requirement
Revises: 0012_admin_notifications
Create Date: 2026-07-29

The "Nutzbare Windrichtungen" field was removed from the spot form, and go-live
is no longer blocked by readiness — so its required_fields row is deleted so it
stops showing up as a gap. Idempotent.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013_drop_wind_dir_requirement"
down_revision: Union[str, None] = "0012_admin_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM required_fields "
        "WHERE entity = 'spot' AND field = 'editorial.usable_wind_directions'"
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO required_fields (entity, field, applies_when, severity)
        SELECT 'spot', 'editorial.usable_wind_directions',
               '{"sports_any": ["kitesurf", "wavekite", "windsurf", "wing"]}'::jsonb,
               'required'
        WHERE NOT EXISTS (
            SELECT 1 FROM required_fields
            WHERE entity = 'spot' AND field = 'editorial.usable_wind_directions'
        )
        """
    )
