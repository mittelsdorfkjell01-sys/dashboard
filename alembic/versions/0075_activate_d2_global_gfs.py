"""activate ICON-D2 and global GFS weather-field models

Revision ID: 0075_activate_d2_global_gfs
Revises: 0074_field_shadow_validation
"""

from alembic import op
import sqlalchemy as sa


revision = "0075_activate_d2_global_gfs"
down_revision = "0074_field_shadow_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE weather_field_models SET status = 'active' "
            "WHERE model_key IN ('icon-d2', 'gfs-0p25') "
            "AND status = 'disabled'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE weather_field_models SET status = 'disabled' "
            "WHERE model_key IN ('icon-d2', 'gfs-0p25') "
            "AND status = 'active'"
        )
    )
