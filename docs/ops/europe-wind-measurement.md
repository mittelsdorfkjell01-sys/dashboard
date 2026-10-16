# Europe wind measurement campaign

The authoritative campaign window is stored in
`config/europe-wind-measurement.json`.

- Start: `2026-10-12T15:17:54Z`
- End: `2026-11-02T15:17:54Z`
- Duration: exactly 21 days
- Provider: EUMETNET MeteoGate E-SOH
- Mode: shadow; public forecast effect is always `none`
- Target: up to 240 spatially balanced 10 m wind stations across the configured
  European bounds

The station catalogue runs daily. Exact model points are captured before the
observation batch every 30 minutes. Each rotated target retains three adjacent
future interpolation windows, so later observations can be compared with a
forecast that demonstrably existed beforehand. Campaign residuals select only
observations that have such pre-observation evidence; historical provider rows
cannot create a synthetic comparison backlog. Workflow date gates stop
campaign jobs automatically after the configured end.

Required repository variables and secrets remain the fail-closed controls
documented in `docs/ops/live-wind-capture-bootstrap.md`. A scheduled workflow
that is disabled by its repository variable does not constitute a running
campaign.

Read-only session check:

```powershell
python -m scripts.europe_measurement_status --session-check
```

Read-only progress counters from the configured database:

```powershell
python -m scripts.europe_measurement_status --database
```

For local development, `docker compose up -d europe-measurement` runs the
restart-safe 30-minute worker together with local Postgres and Redis. The
machine and Docker must remain running; after a restart, Compose resumes the
same campaign and persistent exact-run cache. Hosted operation uses the
date-gated workflow below instead of this long-running local container.

## Free GitHub-hosted operation

The hosted campaign uses `.github/workflows/europe-wind-measurement.yml` at
minutes 7 and 37. Each job uses an ephemeral raw GRIB cache and persists only
the bounded exact point windows, E-SOH observations and shadow residuals in a
dedicated online PostgreSQL database. Redis is not part of this path.

Fail-closed repository configuration:

- secret `EUROPE_WIND_MEASUREMENT_DATABASE_URL` points only to the dedicated
  measurement database;
- variable `EUROPE_WIND_MEASUREMENT_DATABASE_ID` exactly matches its database
  name and starts with `surfwind_measurement_`;
- variable `EUROPE_WIND_MEASUREMENT_ENABLED` stays `false` through bootstrap;
- the legacy self-hosted capture variables remain `false`.

Bootstrap order:

1. Create the dedicated online database.
2. Add the secret and database-ID variable.
3. Publish the campaign implementation to the default branch.
4. Manually run `Bootstrap Europe Wind Measurement Database` with confirmation
   `APPLY-0078`.
5. Manually run `Europe Wind Measurement` once and inspect its counters.
6. Set `EUROPE_WIND_MEASUREMENT_ENABLED=true`.

`Monitor Europe Wind Measurement` runs daily at 03:23 UTC. It fails if station
coverage is below 200, observations are older than three hours, exact bundles
or comparable residuals are missing, the shadow activation boundary is
violated, or database size reaches 900 MB. A failed scheduled workflow is the
operational alert; it never changes public forecast state.

At campaign end, first inspect station coverage, capture gaps, provider errors,
exact-bundle completeness and residual counts. Do not activate corrections from
this campaign automatically.
