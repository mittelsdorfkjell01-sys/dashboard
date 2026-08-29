# Backend guidance

- `app/api/` owns HTTP routing; domain behavior belongs in the corresponding service package, not in route functions.
- `app/models/` is the SQLAlchemy source of truth; `app/schemas/` defines public contracts.
- Keep public catalogue reads lightweight. Avoid implicit relationship loads and large JSONB columns in list endpoints.
- A schema change requires a new Alembic revision plus model, schema, API, and test updates.
- Use the local Postgres/PostGIS database for integration tests. Never silently fall back to SQLite.
- For weather work, preserve provenance, units, timezone semantics, stale flags, and the distinction between measurements, nowcasts, forecasts, and climatology.
- Prefer the focused area checks in `scripts/check.ps1`; see `docs/architecture/repository-map.md` for test ownership.
