-- Applies migration 0011_tip_parent (threaded comment replies) directly against
-- the database, e.g.:
--   psql "$DIRECT_NEON_URL" -f scripts/apply_0011.sql
--
-- Equivalent to `alembic upgrade head` for this one step, but needs no local
-- Python/alembic. Idempotent + transactional, and bumps alembic_version so a
-- later `alembic upgrade head` stays a no-op. Use the DIRECT (non-pooled) URL.
BEGIN;

ALTER TABLE local_tips ADD COLUMN IF NOT EXISTS parent_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tip_parent') THEN
    ALTER TABLE local_tips
      ADD CONSTRAINT fk_tip_parent
      FOREIGN KEY (parent_id) REFERENCES local_tips(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_tip_parent ON local_tips (parent_id);

UPDATE alembic_version SET version_num = '0011_tip_parent'
 WHERE version_num = '0010_commons_images';

COMMIT;
