# Claude project instructions

Read `AGENTS.md` and follow it as the canonical project guidance. Then read `docs/architecture/repository-map.md` only as far as needed for the current task.

Use `./scripts/context.ps1 <area>` before broad repository exploration and `./scripts/check.ps1 <area>` for bounded validation. Do not inspect `data/`, `reports/`, generated files, or caches unless the request explicitly requires them.

`dashboard-main` is the only development and release source. The former `surfwinddata-main` mirror is archived and must not receive changes.
