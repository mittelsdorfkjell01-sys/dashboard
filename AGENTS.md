# Surfwinddata development guide

## Scope and repository role

- This repository (`dashboard-main`) is the canonical development source.
- The sibling `surfwinddata-main` repository is the public/release mirror. Move changes there only through an explicit merge or cherry-pick; never edit both copies for one task.
- Keep work task-scoped. Inspect the repository map first, then only the files and tests relevant to the requested area.

## Start here

- Architecture and task routing: `docs/architecture/repository-map.md`
- Cost-aware session/model guidance: `docs/architecture/agent-workflow.md`
- Focused context: `./scripts/context.ps1 <area>`
- Focused checks: `./scripts/check.ps1 <area>`
- Public mirror drift: `./scripts/repo-drift.ps1`
- Backend entry point: `app/main.py`
- Frontend entry point: `frontend/src/main.tsx`
- Database migrations: `alembic/versions/`

## Working agreements

- Use `rg`/`rg --files` before opening files. Do not scan the full repository when an area is known.
- Do not read or summarize `data/`, `reports/`, caches, build output, generated files, or `.codex/*.log` unless the task explicitly targets them.
- Preserve unrelated user changes in a dirty worktree.
- Use `apply_patch` for hand edits.
- A diagnose/review request does not authorize implementation. A change/fix request includes focused implementation and relevant non-destructive validation.
- Never expose `.env` values or connect a development process to a remote database for writes. Prefer the local Docker Postgres/PostGIS database.
- Do not edit an existing migration after it may have shipped; add a new Alembic revision.
- Keep API schemas and frontend types synchronized when a response contract changes.
- Prefer focused tests first. Run a broad suite only for cross-cutting changes or before a release.
- Do not commit generated `frontend/tsconfig.tsbuildinfo`.

## Common commands

```powershell
docker compose up -d db redis
$env:DATABASE_URL='postgresql+psycopg://surf:surf@localhost:5432/surfwind'
alembic upgrade head
python -m app.seed.seed
python -m uvicorn app.main:app --reload
npm --prefix frontend run dev
```

Use the local URL only in the process environment; do not replace a user's `.env` without an explicit request.

## Skills and tools

- Use only a skill that directly matches the current request.
- Normal backend, database, and test work needs no design, SEO, iOS, Notion, or image skill.
- Use `impeccable` only for an actual frontend/UX task and `seo` only for an explicit SEO task.
- Do not add an MCP server or plugin just to search local code; the focused scripts and `rg` are the default.

## Definition of done

- Requested behavior is implemented without unrelated refactors.
- Relevant focused checks pass, or an external blocker is reported precisely.
- The final handoff lists changed files, validation, and any remaining operational step.
