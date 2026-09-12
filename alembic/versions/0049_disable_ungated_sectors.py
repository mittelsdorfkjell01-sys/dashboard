"""disable legacy sector versions that bypassed candidate activation

Revision ID: 0049_disable_ungated_sectors
Revises: 0048_forecast_sector_builds
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_disable_ungated_sectors"
down_revision: Union[str, None] = "0048_forecast_sector_builds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Older direct microscale and WP6 calibration writers stored their output as
    # enabled even though no WP1 activation decision had occurred. Serving did
    # not expose sectors at the time, so conservatively return those rows to the
    # candidate state before the resolver begins honoring enabled corrections.
    op.execute(sa.text("""
        UPDATE spot_weather_sectors
        SET enabled = false, updated_at = now()
        WHERE enabled = true
          AND (
            note LIKE '%microscale_ibl%'
            OR note LIKE '%shrinkage_posterior%'
          )
    """))


def downgrade() -> None:
    # Intentionally irreversible: re-enabling rows without their original WP1
    # decision would recreate the governance bypass this migration closes.
    pass
