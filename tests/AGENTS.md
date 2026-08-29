# Test guidance

- Backend integration tests require local Postgres/PostGIS from `docker compose`; they do not use SQLite.
- Add the narrowest regression test that proves the requested behavior.
- Keep external weather/media providers mocked unless a test is explicitly marked as a live smoke test.
- Prefer `./scripts/check.ps1 <area>` to a full suite during iteration.
- If a test is blocked by external quota or credentials, still run syntax, contract, and pure-unit checks and report the exact missing dependency.
- Do not weaken assertions merely to make an implementation pass.
