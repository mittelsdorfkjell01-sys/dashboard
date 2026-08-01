-- Migration 0018: spot finish-rank override. Raw-SQL fallback (idempotent).
ALTER TABLE spots ADD COLUMN IF NOT EXISTS finish_rank varchar(10);
