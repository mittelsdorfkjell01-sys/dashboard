# Development data policy

The product currently has no users. Neon is therefore a lean integration and
demo database, not the long-term store for raw measurement campaigns. The
normal operating state is deliberately quiet:

- GitHub weather, station, verification, tide and LiveWind workflows are
  `workflow_dispatch` only;
- Vercel registers no cron jobs;
- `RUN_MAINTENANCE_CRONS` defaults to `false`, so a manual endpoint call still
  fails closed until an operator explicitly starts a campaign;
- local Docker PostgreSQL/PostGIS is the default for development, tests,
  backfills and exploratory imports.

## Starting a bounded campaign

Before enabling any collector, record its purpose, station/spot scope, start
and end time, expected request volume, expected database growth and the person
responsible for stopping it. Enable only the one required workflow variable and
set `RUN_MAINTENANCE_CRONS=true` only on the single deployment that owns the
campaign. At the agreed end time, turn both controls off before analysing or
exporting the results.

Do not run duplicate station-catalog paths in one campaign. Choose either the
HTTP workflow or the persistent capture workflow. A changing provider coverage
end date is operational metadata and does not constitute a new station sensor
revision or epoch.

## Retention

The default operational retention is:

| Data | Retention |
|---|---:|
| Inactive forecast snapshots | 7 days |
| Successful/superseded forecast jobs | 7 days |
| Failed forecast jobs | 14 days |
| Recommendation audit logs | 30 days |
| Successful LiveWind jobs | 7 days |
| Failed LiveWind jobs | 14 days |
| Forecast verification samples | 120 days |

Active snapshots, queued/running jobs and LiveWind jobs referenced by immutable
holdout evidence are never removed by the operational cleanup. Warm-up requests
populate caches without creating recommendation audit rows.

## Archiving and pruning campaign evidence

Raw observations, observation revisions and verification samples require an
archive before deletion. Create the archive outside the repository:

```powershell
python -m scripts.archive_development_evidence `
  --env-file .env `
  --allow-remote-read `
  --output C:\path\to\durable\backups
```

The command uses a repeatable, read-only transaction and writes compressed
NDJSON plus a manifest containing row counts, schema revision and SHA-256
checksums. Keep the archive and a provider recovery branch before pruning.

Always run the prune command without `--apply` first. The apply path refuses a
different database, missing files, checksum mismatches, post-archive table
growth or observations referenced by holdout evidence:

```powershell
python -m scripts.prune_development_evidence `
  --env-file .env `
  --archive-manifest C:\path\to\manifest.json `
  --before 2026-11-01T00:00:00Z

python -m scripts.prune_development_evidence `
  --env-file .env `
  --archive-manifest C:\path\to\manifest.json `
  --before 2026-11-01T00:00:00Z `
  --apply `
  --confirmation PRUNE-DEVELOPMENT-EVIDENCE `
  --compact
```

## Release order

Database migrations and app deployment remain coordinated even while there are
no users:

1. create and verify a recovery branch;
2. pass a fresh `base -> head` migration test locally;
3. deploy the app and migrate the database in the release window;
4. verify `/api/health` on public and admin deployments;
5. enable a bounded campaign only after the schema reports `ok`.

Never advance the shared database schema ahead of the currently deployed app's
`EXPECTED_DB_REVISION`; doing so intentionally makes health checks fail.
