# Claude project instructions

Read `AGENTS.md` and follow it as the canonical project guidance. Then read `docs/architecture/repository-map.md` only as far as needed for the current task.

Use `./scripts/context.ps1 <area>` before broad repository exploration and `./scripts/check.ps1 <area>` for bounded validation. Do not inspect `data/`, `reports/`, generated files, caches, or the sibling repository unless the request explicitly requires them.

`dashboard-main` is the development source. `surfwinddata-main` is a public/release mirror and must only receive intentional merges or cherry-picks.
