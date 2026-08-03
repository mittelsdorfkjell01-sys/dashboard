-- Applies migration 0018_spot_finish_rank (spot finish-rank override) directly
-- against the database, e.g.:
--   psql "$DIRECT_NEON_URL" -f scripts/apply_0018.sql
--
-- Equivalent to `alembic upgrade head` for this one step, but needs no local
-- Python/alembic. Idempotent + transactional, and bumps alembic_version so a
-- later `alembic upgrade head` stays a no-op. Use the DIRECT (non-pooled) URL.
BEGIN;

ALTER TABLE spots ADD COLUMN IF NOT EXISTS finish_rank varchar(10);

UPDATE alembic_version SET version_num = '0018_spot_finish_rank'
 WHERE version_num = '0017_admin_last_seen';

COMMIT;
