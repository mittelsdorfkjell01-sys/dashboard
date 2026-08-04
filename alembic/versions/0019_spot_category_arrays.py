"""spot category axes become multi-select arrays

Revision ID: 0019_spot_category_arrays
Revises: 0018_spot_finish_rank
Create Date: 2026-08-04

Converts ``spots.water_type``, ``spots.level`` and ``spots.water_character`` from
single ``varchar`` columns to ``varchar[]`` (multi-select, like ``sports`` /
``style``). Existing scalar values are wrapped into a one-element array; NULL /
empty become an empty array. The old composite btree index on
``(water_type, level)`` is replaced by GIN indexes so membership filters
(``value = ANY(col)``) stay indexed.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019_spot_category_arrays"
down_revision: Union[str, None] = "0018_spot_finish_rank"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = ("water_type", "level", "water_character")


def upgrade() -> None:
    op.drop_index("ix_spots_water_level", table_name="spots")

    for col in _COLS:
        op.execute(
            f"""
            ALTER TABLE spots
                ALTER COLUMN {col} DROP DEFAULT,
                ALTER COLUMN {col} TYPE varchar[] USING (
                    CASE
                        WHEN {col} IS NULL OR {col} = '' THEN ARRAY[]::varchar[]
                        ELSE ARRAY[{col}]::varchar[]
                    END
                ),
                ALTER COLUMN {col} SET DEFAULT '{{}}'::varchar[],
                ALTER COLUMN {col} SET NOT NULL
            """
        )

    op.create_index(
        "ix_spots_water_type", "spots", ["water_type"], postgresql_using="gin"
    )
    op.create_index("ix_spots_level", "spots", ["level"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_spots_level", table_name="spots")
    op.drop_index("ix_spots_water_type", table_name="spots")

    for col in _COLS:
        op.execute(
            f"""
            ALTER TABLE spots
                ALTER COLUMN {col} DROP DEFAULT,
                ALTER COLUMN {col} DROP NOT NULL,
                ALTER COLUMN {col} TYPE varchar(30) USING (
                    CASE
                        WHEN {col} IS NULL OR array_length({col}, 1) IS NULL THEN NULL
                        ELSE {col}[1]
                    END
                )
            """
        )

    op.create_index(
        "ix_spots_water_level", "spots", ["water_type", "level"]
    )
