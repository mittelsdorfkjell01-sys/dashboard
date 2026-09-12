# Surfwinddata development guide

## Scope and repository role

- This repository (`dashboard-main`) is the only canonical development and release source.
- The former `surfwinddata-main` mirror is archived. Do not synchronize or restore it; both Vercel targets deploy from this repository.
- Keep work task-scoped. Inspect the repository map first, then only the files and tests relevant to the requested area.

## Start here

- Architecture and task routing: `docs/architecture/repository-map.md`
- Cost-aware session/model guidance: `docs/architecture/agent-workflow.md`
- Focused context: `./scripts/context.ps1 <area>`
- Focused checks: `./scripts/check.ps1 <area>`
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
- Do not add another MCP server or plugin just to search local code. Use Graphify for cross-cutting architecture and blast-radius questions; the focused scripts and `rg` remain the default for narrow searches.

## Definition of done

- Requested behavior is implemented without unrelated refactors.
- Relevant focused checks pass, or an external blocker is reported precisely.
- The final handoff lists changed files, validation, and any remaining operational step.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `$graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For cross-cutting architecture or blast-radius questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. Use `rg` and the focused context scripts for narrow symbol or file searches.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- This repository uses Graphify in code-only mode. Do not enable semantic extraction for docs or media, or configure an external model backend, unless the user explicitly requests it.
