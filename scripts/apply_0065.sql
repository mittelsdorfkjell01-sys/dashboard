-- Applies migration 0065_account_experience (verified public emails +
-- persisted account preferences) directly against the database, e.g.:
--   psql "$DIRECT_NEON_URL" -f scripts/apply_0065.sql
--
-- Equivalent to `alembic upgrade head` for this one step, but needs no local
-- Python/alembic. Idempotent + transactional, and bumps alembic_version so a
-- later `alembic upgrade head` stays a no-op. Use the DIRECT (non-pooled) URL.
--
-- Only valid when the database is already at 0064_exact_model_points. Check
-- first: SELECT version_num FROM alembic_version;  (if it is behind 0064, run
-- `alembic upgrade head` instead so the intervening migrations also apply.)
BEGIN;

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS pending_email varchar(255);
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS email_token_version integer NOT NULL DEFAULT 0;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS preferences jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Existing users keep access; only newly registered accounts need verification.
UPDATE app_users SET email_verified_at = created_at WHERE email_verified_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_app_users_pending_email ON app_users (pending_email);

-- Allow the 'withdrawn' submission status.
ALTER TABLE spot_submissions DROP CONSTRAINT IF EXISTS ck_spot_submissions_status;
ALTER TABLE spot_submissions ADD CONSTRAINT ck_spot_submissions_status
  CHECK (status IN ('pending', 'approved', 'rejected', 'merged', 'withdrawn'));

UPDATE alembic_version SET version_num = '0065_account_experience'
 WHERE version_num = '0064_exact_model_points';

COMMIT;
