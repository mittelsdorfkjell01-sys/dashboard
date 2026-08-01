-- Migration 0017: admin presence heartbeat. Raw-SQL fallback (idempotent).
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS last_seen_at timestamptz;
