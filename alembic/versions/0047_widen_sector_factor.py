"""widen spot_weather_sectors speed_factor bounds to 0.50-1.60

Revision ID: 0047_widen_sector_factor
Revises: 0046_forecast_score_gust
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0047_widen_sector_factor"
down_revision: Union[str, None] = "0046_forecast_score_gust"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Exposed coasts and gap/jet effects need a wider outer hull than the
    # original 0.60-1.35. The DB constraint is the outer envelope; the applied
    # clamp (clamp_combined_factor) stays inside it.
    op.drop_constraint("ck_weather_sector_factor", "spot_weather_sectors", type_="check")
    op.create_check_constraint(
        "ck_weather_sector_factor", "spot_weather_sectors",
        "speed_factor >= 0.50 AND speed_factor <= 1.60",
    )


def downgrade() -> None:
    op.drop_constraint("ck_weather_sector_factor", "spot_weather_sectors", type_="check")
    op.create_check_constraint(
        "ck_weather_sector_factor", "spot_weather_sectors",
        "speed_factor >= 0.60 AND speed_factor <= 1.35",
    )
