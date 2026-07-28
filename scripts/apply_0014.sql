-- Migration 0014: allow region-less spots. Raw-SQL fallback (idempotent).
ALTER TABLE spots ALTER COLUMN region_id DROP NOT NULL;
