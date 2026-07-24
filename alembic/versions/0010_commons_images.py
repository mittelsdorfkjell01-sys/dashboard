"""commons images: external license metadata on spot_images

Revision ID: 0010_commons_images
Revises: 0009_app_accounts
Create Date: 2026-07-24

Wikimedia Commons photos are fetched automatically, not uploaded through the
consent flow, so license_version/license_accepted_at (which track *our own*
upload-consent event) have nothing to record for them and become nullable.
The photo's real license/attribution as reported by Commons gets its own
columns, distinct from those two.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_commons_images"
down_revision: Union[str, None] = "0009_app_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("spot_images", sa.Column("license_name", sa.String(80), nullable=True))
    op.add_column("spot_images", sa.Column("license_url", sa.String(500), nullable=True))
    op.add_column("spot_images", sa.Column("source_url", sa.String(500), nullable=True))
    op.alter_column("spot_images", "license_version", existing_type=sa.String(20), nullable=True)
    op.alter_column(
        "spot_images",
        "license_accepted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "spot_images",
        "license_accepted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column("spot_images", "license_version", existing_type=sa.String(20), nullable=False)
    op.drop_column("spot_images", "source_url")
    op.drop_column("spot_images", "license_url")
    op.drop_column("spot_images", "license_name")
