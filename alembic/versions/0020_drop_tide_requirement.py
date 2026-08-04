"""drop the editorial.tide readiness requirement

Revision ID: 0020_drop_tide_requirement
Revises: 0019_spot_category_arrays
Create Date: 2026-08-04

Gezeiten (``editorial.tide``) is hidden in the spot editor and must no longer
count toward readiness / the "Fertigstellen" rank, so its required_fields row is
deleted (it stops showing up as a gap). Idempotent. Mirrors 0013.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020_drop_tide_requirement"
down_revision: Union[str, None] = "0019_spot_category_arrays"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM required_fields "
        "WHERE entity = 'spot' AND field = 'editorial.tide'"
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO required_fields (entity, field, applies_when, severity)
        SELECT 'spot', 'editorial.tide',
               '{"sports_any": ["surf"]}'::jsonb,
               'required'
        WHERE NOT EXISTS (
            SELECT 1 FROM required_fields
            WHERE entity = 'spot' AND field = 'editorial.tide'
        )
        """
    )
