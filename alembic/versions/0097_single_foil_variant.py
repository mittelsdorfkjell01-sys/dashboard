"""Collapse the per-sport foil variants into one ``foil`` category.

Revision ID: 0097_single_foil_variant
Revises: 0096_wave_verification

``spots.variant_conditions`` keyed foil per sport (``windsurf:foil``,
``kitesurf:foil``). What a foil needs from a place — depth under the board, a
launch deep enough to get going, a wind window for a much faster craft — is a
property of the water, not of whether the rider holds a sail or a bar, so the
two keys asked editors the same question twice and let one sandbank read
"Windfoil ungeprüft, Kitefoil geeignet".

Both keys fold into ``foil``. Where a spot carried both and they disagreed,
the more cautious suitability wins (ungeeignet > eingeschraenkt > geeignet,
with unbekannt yielding to any real assessment): a foil claim that is wrong in
the optimistic direction ends in a grounded foil, one that is wrong in the
cautious direction only costs a session someone might have had.

The rest of the block (wind_directions, usable_depth_m, tide, notes, level)
comes from whichever side won, so the numbers always belong to the assessment
they were written for; merging fields across the two would invent a block no
editor ever wrote. Nothing is deleted: a spot with only one foil key keeps its
block verbatim under the new name.

Downgrade restores ``windsurf:foil`` / ``kitesurf:foil`` by copying the merged
block to whichever foil sports the spot lists. That cannot resurrect a
distinction this migration merged away — it is a shape restore, not a data
restore.
"""

from alembic import op
import sqlalchemy as sa


revision = "0097_single_foil_variant"
down_revision = "0096_wave_verification"
branch_labels = None
depends_on = None

OLD_KEYS = ("windsurf:foil", "kitesurf:foil")
NEW_KEY = "foil"
FOIL_SPORTS = ("windsurf", "kitesurf")

# Most cautious first: the winner of a disagreement.
_CAUTION_ORDER = {"ungeeignet": 0, "eingeschraenkt": 1, "geeignet": 2, "unbekannt": 3}


def _rank(block) -> int:
    if not isinstance(block, dict):
        return 99
    return _CAUTION_ORDER.get(block.get("suitability"), 3)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, variant_conditions FROM spots "
            "WHERE variant_conditions IS NOT NULL "
            "AND (variant_conditions ? 'windsurf:foil' OR variant_conditions ? 'kitesurf:foil')"
        )
    ).fetchall()

    for spot_id, conditions in rows:
        if not isinstance(conditions, dict):
            continue
        candidates = [conditions[key] for key in OLD_KEYS if key in conditions]
        merged = dict(conditions)
        for key in OLD_KEYS:
            merged.pop(key, None)
        winner = min(candidates, key=_rank, default=None)
        if isinstance(winner, dict):
            # An existing `foil` block (there should be none) is not overwritten
            # by a migrated one — it was written against the new vocabulary.
            merged.setdefault(NEW_KEY, winner)
        bind.execute(
            sa.text("UPDATE spots SET variant_conditions = :v WHERE id = :id").bindparams(
                sa.bindparam("v", type_=sa.JSON())
            ),
            {"v": merged or None, "id": spot_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, sports, variant_conditions FROM spots "
            "WHERE variant_conditions IS NOT NULL AND variant_conditions ? 'foil'"
        )
    ).fetchall()

    for spot_id, sports, conditions in rows:
        if not isinstance(conditions, dict):
            continue
        block = conditions.get(NEW_KEY)
        restored = dict(conditions)
        restored.pop(NEW_KEY, None)
        listed = set(sports or []) & set(FOIL_SPORTS)
        for sport in listed:
            restored[f"{sport}:foil"] = block
        bind.execute(
            sa.text("UPDATE spots SET variant_conditions = :v WHERE id = :id").bindparams(
                sa.bindparam("v", type_=sa.JSON())
            ),
            {"v": restored or None, "id": spot_id},
        )
