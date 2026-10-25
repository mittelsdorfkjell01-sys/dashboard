"""record the second-generation schematic kite renderer

Revision ID: 0083_gear_svg_v2
Revises: 0082_gear_catalog
"""

from alembic import op


revision = "0083_gear_svg_v2"
down_revision = "0082_gear_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE gear_geometries SET generator_version = 'kite-svg-v2' "
        "WHERE generator_version = 'kite-svg-v1'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE gear_geometries SET generator_version = 'kite-svg-v1' "
        "WHERE generator_version = 'kite-svg-v2'"
    )
