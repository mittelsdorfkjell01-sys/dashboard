# Production database recovery

Use only the manually dispatched **Production database recovery** workflow. The
GitHub `production` environment must require reviewer approval. Never paste a
database URL into an input, command, issue, or workflow log.

1. Confirm `DIRECT_DATABASE_URL`, `POOLED_DATABASE_URL`, and
   `PRODUCTION_API_BASE_URL` exist as GitHub Actions secrets. Direct and pooled
   connectivity are checked separately.
2. Determine the current `alembic_version` and confirm the repository has exactly
   one Alembic head. The preflight prints revision identifiers only. Its target
   must equal the application's `EXPECTED_DB_REVISION`.
3. Confirm a provider-level backup or recovery point exists, is recent enough,
   and has a documented restore procedure. Record its identifier outside workflow
   logs. Enter `BACKUP CONFIRMED` only after this check.
4. Obtain protected-environment approval and run the workflow from the intended
   default-branch commit. Migration uses the direct connection only.
5. The workflow rechecks direct and pooled connections and the target revision,
   then checks health, spot version, spot list, one live value, and one forecast.

Stop before migration if the backup is absent, the target is not the single head,
either connection fails, the current revision is unexpected, or compatibility is
uncertain. Stop after migration and deploy nothing further if verification fails.
Restore only through the provider's approved procedure after an incident decision;
do not automatically downgrade because migration `0040` rewrites existing JSON.

## Neon transfer guard and Weather Shadow

The scheduled Weather Shadow workflow is fail-closed and should remain paused
during a transfer-quota incident. Configure these GitHub values without placing
their contents in workflow inputs or logs:

- Secret `NEON_API_KEY`: use a least-privilege project-scoped API key; the guard
  itself sends only the project-detail `GET` request.
- Variable `NEON_PROJECT_ID`: the production Neon project identifier.
- Variable `WEATHER_SHADOW_ENABLED`: leave unset or `false` while paused; set
  exactly `true` only after the quota has reset and the public cache deployment
  has been verified.
- Secret `REDIS_URL`: the same managed Redis endpoint used by the public Vercel
  deployment. A process-local or `localhost` cache does not prevent Neon reads
  across serverless instances. Configure this secret in both GitHub Actions and
  Vercel, then verify Redis is reported healthy before enabling Weather Shadow.

The guard reads Neon's project detail API, not Postgres. It warns at 3 GB,
raises a critical warning at 4 GB, and fails the workflow at 4.5 GB so scheduled
generation cannot consume the final 0.5 GB reserved for production traffic.
GitHub Actions notifications should be enabled for failed workflows; the step
summary records only byte totals and status, never a connection URL or API key.
