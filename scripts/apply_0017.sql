-- Applies migration 0017_admin_last_seen (admin presence heartbeat) directly
-- against the database, e.g.:
--   psql "$DIRECT_NEON_URL" -f scripts/apply_0017.sql
--
-- Equivalent to `alembic upgrade head` for this one step, but needs no local
-- Python/alembic. Idempotent + transactional, and bumps alembic_version so a
-- later `alembic upgrade head` stays a no-op. Use the DIRECT (non-pooled) URL.
BEGIN;

ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS last_seen_at timestamptz;

UPDATE alembic_version SET version_num = '0017_admin_last_seen'
 WHERE version_num = '0016_team_note_priority';

COMMIT;
