"""Add per-spot, per-variant suitability (Windfoil / Kitefoil).

Adds ``spots.variant_conditions`` (JSONB) and seeds the proven *base* variant
from each spot's existing sports without inventing foil suitability:
existing ``windsurf`` implies ``windsurf:fin = geeignet`` (Finne) and existing
``kitesurf`` implies ``kitesurf:classic = geeignet`` (klassisch). The foil
variants (``windsurf:foil`` / ``kitesurf:foil``) are deliberately left absent,
i.e. ``unbekannt``, until an editor confirms them. ``wing`` (Wingfoilen) and
``surf`` are untouched — Surf-Foil is not folded into another sport.

Revision ID: 0063_spot_variant_conditions
Revises: 0062_station_capture_operations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0063_spot_variant_conditions"
down_revision = "0062_station_capture_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("spots", sa.Column("variant_conditions", postgresql.JSONB(), nullable=True))
    # Seed only the proven base variant from the existing sports listing. Merge
    # (``||``) so any pre-existing blob is preserved; the foil variants stay
    # absent (=> unbekannt) on purpose.
    # NULLIF guards against a stray JSONB 'null' (not just SQL NULL) so the merge
    # always starts from an object, never wraps into an array.
    op.execute(
        """
        UPDATE spots
        SET variant_conditions =
            COALESCE(NULLIF(variant_conditions, 'null'::jsonb), '{}'::jsonb)
            || jsonb_build_object(
                 'windsurf:fin', jsonb_build_object('suitability', 'geeignet')
               )
        WHERE 'windsurf' = ANY(sports)
        """
    )
    op.execute(
        """
        UPDATE spots
        SET variant_conditions =
            COALESCE(NULLIF(variant_conditions, 'null'::jsonb), '{}'::jsonb)
            || jsonb_build_object(
                 'kitesurf:classic', jsonb_build_object('suitability', 'geeignet')
               )
        WHERE 'kitesurf' = ANY(sports)
        """
    )


def downgrade() -> None:
    op.drop_column("spots", "variant_conditions")
