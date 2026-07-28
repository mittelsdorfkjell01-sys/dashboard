-- Migration 0015: region publish status. Raw-SQL fallback (idempotent).
ALTER TABLE regions ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'published';
