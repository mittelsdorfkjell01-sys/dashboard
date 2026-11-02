# Europe wind measurement campaign

The authoritative campaign window is stored in
`config/europe-wind-measurement.json`.

- Start: `2026-10-31T17:00:00Z`
- End: `2026-11-21T17:00:00Z`
- Duration: exactly 21 days
- Provider: EUMETNET MeteoGate E-SOH
- Mode: shadow; public forecast effect is always `none`
- Target: 64 spatially balanced 10 m wind stations across the configured
  European bounds

The station catalogue runs daily and enriches the selected WIGOS identities
with authoritative country and station-type metadata from WMO OSCAR. Exact
model points for all 64 targets are captured before the observation batch every
30 minutes. Each target retains three adjacent
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

Repository-wide workflow overview (read-only):

```powershell
python -m scripts.backtest_status
```

This command reports the latest GitHub Actions run for the Europe measurement,
its monitor, tide worker, forecast verification, weather shadow and LiveWind
shadow workflows. It never starts, cancels or reruns a job. Interpret the
result precisely:

- `success` means the workflow ran and completed successfully;
- `failure` means its logs need investigation;
- `skipped` means the workflow exists but its current gates did not allow it to
  run; it is not evidence of an active backtest;
- the run URL opens the exact Summary and Logs in GitHub Actions.

The Europe campaign uses its dedicated measurement database and remains
separate from the public and admin deployment database. Do not delete or
repurpose its database, workflow variables or secrets while the configured
campaign window is active.

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
minutes 7, 22, 37 and 52. These are two redundant triggers per 30-minute slot;
the worker deduplicates completed slots in the database. Each real cycle stores
an append-only heartbeat, uses an ephemeral raw GRIB cache and persists only
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
   `APPLY-0094`.
5. Manually run `Europe Wind Measurement` once and inspect its counters.
6. Set `EUROPE_WIND_MEASUREMENT_ENABLED=true`.

`Monitor Europe Wind Measurement` runs at minutes 14, 29, 44 and 59. It fails
after two missed 30-minute intervals plus a ten-minute scheduler grace period,
if station coverage is below 64, operational observations are missing or older
than three hours, latest-cycle exact coverage is below 90%, station identity
metadata is incomplete, exact bundles or comparable residuals are missing, the
shadow activation boundary is violated, or database size reaches 900 MB. A
failed monitor opens or updates a GitHub issue and never changes public forecast
state.

The 180-minute observation limit is explicit in the campaign configuration; the
independent scheduler heartbeat gate is 70 minutes. Neither is a claim that
every sensor publishes every 30 minutes. Status output separates operational
captures from historical backfills and keeps the
latest observation time separate from provider receipt, import/processing time
and the observation's measurement period. Diagnose failures in this order:

1. observation time in the future: sensor clock or timezone/UTC parsing;
2. old observation with recent receipt: provider delay or a real sensor gap;
3. old receipt/import: workflow, queue, database or provider-fetch delay;
4. compare the stored measurement period and station metadata with the
   provider's stated cadence; never relabel an old observation as current.

Until the configured end, the repository owner watches the scheduled workflow
daily and acknowledges failures the same day. A failed freshness gate opens an
operations issue with the three timestamps, affected station count, workflow
run and classification (clock, provider, pipeline or genuine gap). LiveWind and
measurement-derived corrections remain launch-gated and shadow-only.

At campaign end, run a formal evaluation before any rollout decision. Report:

- station and geographic coverage plus observed provider cadences;
- expected versus captured intervals, gaps and outages by cause;
- counts excluded for clock, provenance, QC, epoch or pre-observation evidence;
- exact-bundle and comparable-residual completeness;
- error distributions and uncertainty by region, lead time and condition;
- all quality rules, known biases and limits on what the sample can prove.

Do not activate corrections from this campaign automatically. Activation needs
a separately reviewed evidence record and explicit operational approval.
