"""seed editable spot safety notices

Revision ID: 0086_spot_safety_notices
Revises: 0085_gear_no_windrange
"""

from alembic import op
import sqlalchemy as sa

from app.seed.safety_notices import INITIAL_SAFETY_NOTICES


revision = "0086_spot_safety_notices"
down_revision = "0085_gear_no_windrange"
branch_labels = None
depends_on = None


_UPSERT_NOTICE = sa.text(
    """
    UPDATE spots
    SET editorial = jsonb_set(
            COALESCE(editorial, '{}'::jsonb),
            '{safety_notice}',
            to_jsonb(CAST(:notice AS text)),
            true
        ),
        updated_at = now()
    WHERE name = :name
      AND (editorial IS NULL OR NOT editorial ? 'safety_notice')
    """
)

_REMOVE_UNCHANGED_NOTICE = sa.text(
    """
    UPDATE spots
    SET editorial = NULLIF(editorial - 'safety_notice', '{}'::jsonb),
        updated_at = now()
    WHERE name = :name
      AND editorial ->> 'safety_notice' = :notice
    """
)


def upgrade() -> None:
    connection = op.get_bind()
    for names, notice in INITIAL_SAFETY_NOTICES:
        for name in names:
            connection.execute(_UPSERT_NOTICE, {"name": name, "notice": notice})


def downgrade() -> None:
    # Preserve any text an editor changed after this migration ran.
    connection = op.get_bind()
    for names, notice in INITIAL_SAFETY_NOTICES:
        for name in names:
            connection.execute(
                _REMOVE_UNCHANGED_NOTICE,
                {"name": name, "notice": notice},
            )
