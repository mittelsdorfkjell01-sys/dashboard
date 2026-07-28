-- Migration 0013: drop the usable_wind_directions readiness requirement.
-- Raw-SQL fallback for the Neon SQL editor (idempotent). Run on the prod branch.
DELETE FROM required_fields
WHERE entity = 'spot' AND field = 'editorial.usable_wind_directions';
