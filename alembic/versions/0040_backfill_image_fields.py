"""backfill focal_mobile/rotation/hero_reel on existing image objects

Revision ID: 0040_backfill_image_fields
Revises: 0039_wind_climatology_v3

``focal_mobile``, ``rotation`` and ``hero_reel`` were added to
``CANONICAL_KEYS`` (app/media/image_object.py) after migration 0027 lifted
legacy image objects to the canonical shape. 0027's upgrade SQL was never
updated for the new keys, so any image object migrated through it — rather
than freshly built via ``build_image()`` — is missing all three keys
entirely (not even ``null``), violating the canonical shape the rest of the
codebase assumes. This backfill adds them, without touching any value that's
already present.
"""
from alembic import op

revision = "0040_backfill_image_fields"
down_revision = "0039_wind_climatology_v3"
branch_labels = None
depends_on = None

_BACKFILL = """
    UPDATE {table} SET image = image
        || jsonb_build_object('focal_mobile', COALESCE(image->'focal_mobile', 'null'::jsonb))
        || jsonb_build_object('rotation',     COALESCE(image->'rotation',     '0'::jsonb))
        || jsonb_build_object('hero_reel',    COALESCE(image->'hero_reel',    'false'::jsonb))
    WHERE image IS NOT NULL AND jsonb_typeof(image) = 'object'
"""

_REVERT = """
    UPDATE {table} SET image = image - 'focal_mobile' - 'rotation' - 'hero_reel'
    WHERE image IS NOT NULL AND jsonb_typeof(image) = 'object'
"""


def upgrade() -> None:
    op.execute(_BACKFILL.format(table="spots"))
    op.execute(_BACKFILL.format(table="regions"))


def downgrade() -> None:
    op.execute(_REVERT.format(table="spots"))
    op.execute(_REVERT.format(table="regions"))
