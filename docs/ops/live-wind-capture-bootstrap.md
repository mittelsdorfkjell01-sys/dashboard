# Non-production raw capture bootstrap

Status: `continuous_capture_not_started`. This procedure prepares raw station
and Exact-Run capture only. It must not run residuals, holdouts, LiveWind jobs,
Canary, public activation, or an adaptive forecast.

## Hard prerequisites

Record all values in the operator change ticket without printing credentials:

- reviewed Git commit containing the single Alembic head;
- authorised self-hosted Linux runner labels `self-hosted`, `linux`, `live-wind`;
- stable `LIVE_WIND_RUNNER_ID`;
- non-production database named `surfwind_capture_*` or `surfwind_staging_*`;
- PostGIS database migrated to the checked-out commit's exact head;
- dedicated Redis endpoint;
- absolute persistent non-overlay mount with `.exact-run-cache-id`;
- at least 5 GB free on that mount;
- UTC runner clock, database clock and Redis clock within the preflight limit;
- public rollout `shadow`, forced baseline enabled, empty public region list;
- both scheduler enable variables still `false` during bootstrap.

Required repository variables:

```text
LIVE_WIND_CAPTURE_AUTHORIZED=true
LIVE_WIND_CAPTURE_ENVIRONMENT_ID=<exact non-production database name>
LIVE_WIND_RUNNER_ID=<stable reviewed runner identity>
LIVE_WIND_EXACT_RUN_CACHE_DIR=<absolute persistent Linux mount>
LIVE_WIND_EXACT_RUN_CACHE_ID=<contents of .exact-run-cache-id>
LIVE_WIND_CAPTURE_ENABLED=false
LIVE_WIND_CAPTURE_CATALOG_ENABLED=false
```

Required repository secrets:

```text
LIVE_WIND_CAPTURE_DATABASE_URL
LIVE_WIND_CAPTURE_REDIS_URL
LIVE_WIND_CAPTURE_PROBE_SHA256
```

The database and Redis secrets must identify non-production resources. The
worker checks that the database name exactly equals
`LIVE_WIND_CAPTURE_ENVIRONMENT_ID`; the environment ID must use an allowed
non-production prefix. No public/API JWT or production database secret is used.

For the preferred host-local scheduler, put the same values in a root-owned
`/etc/surfwind/live-wind-capture.env` (`chmod 600`) and also set:

```text
LIVE_WIND_REPOSITORY_DIR=/srv/surfwind/dashboard
LIVE_WIND_DEPLOYED_COMMIT=<reviewed full commit SHA>
```

Install `ops/systemd/*.service` and `ops/systemd/*.timer` in
`/etc/systemd/system`. The services share a nonblocking lock, verify the pinned
clean checkout, run the cross-job cache proof, and preserve the required order.
Enable timers only after both bootstrap jobs and the manual first cycle pass:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now surfwind-station-catalog.timer
sudo systemctl start surfwind-station-catalog.service
sudo systemctl start surfwind-capture.service
sudo systemctl enable --now surfwind-capture.timer surfwind-capture-doctor.timer
systemctl list-timers 'surfwind-*'
systemctl --failed 'surfwind-*'
```

`surfwind-capture-doctor.service` exits nonzero and becomes a visible systemd
alarm when either provider has no fresh operational observations/catalog cycle
or when either GFS/ICON asset inventory is missing or stale. Provider alerts
remain separate; one healthy provider never hides another provider's gap.

## Checkout and migration proof

On the authorised runner, record the output without credentials:

```bash
git rev-parse HEAD
git status --short
alembic heads
alembic current
python -m scripts.exact_run_preflight
```

There must be one code head, the database must equal that head, and the checkout
must contain no local source changes. Do not migrate or start capture from a
worktree-only state.

## Two-job cache persistence proof

In bootstrap job A:

```bash
export LIVE_WIND_RUNNER_JOB_ID="bootstrap-a-${GITHUB_RUN_ID:-manual}"
python -m scripts.exact_run_preflight --persistence create
```

Store the emitted SHA-256 in the change ticket and then in the
`LIVE_WIND_CAPTURE_PROBE_SHA256` secret. In a distinct job B on the same named
runner and mount:

```bash
export LIVE_WIND_RUNNER_JOB_ID="bootstrap-b-${GITHUB_RUN_ID:-manual}"
python -m scripts.exact_run_preflight \
  --persistence verify \
  --require-new-job \
  --expected-probe-sha256 "$LIVE_WIND_CAPTURE_PROBE_SHA256"
```

This proves a different job can read the identical mount artifact and cache
identity. It does not prove host-restart persistence; perform and record a later
authorised host-restart verification if that guarantee is required.

## Scheduler separation and order

- `.github/workflows/station-catalog.yml`: daily DWD/DMI metadata refresh.
- `.github/workflows/live-wind-capture.yml`: every ten minutes, exact GFS/ICON
  capture first, then DWD/DMI operational observations.

Both workflows are fail-closed behind separate enable variables. The raw
capture workflow contains no residual, holdout, LiveWind or activation command.
Enable the catalog schedule first, inspect one successful catalog cycle, then
manually dispatch raw capture twice in distinct jobs. Confirm the second run is
idempotent and preserves the first `received_at` before enabling its schedule.

`availability_class` describes immutable capture origin, not LiveWind freshness:

- `captured_operationally`: the station had a proven earlier collector attempt,
  the observation is no older than its enrolled epoch, and the first HTTP
  receipt belongs to the recorded current capture job;
- `historical_backfill`: an explicit backfill, or an older provider sample
  found during the station's first bootstrap poll;
- `availability_unproven`: the first receipt, epoch enrollment or capture-job
  relationship cannot be proven.

Receipt delay never changes these meanings. In particular, a DWD value first
received 34 minutes after its observation remains operational capture evidence,
but fails the separate versioned 30-minute LiveWind input gate. Replays preserve
the original origin, `received_at` and `first_seen_at`.

## Status, pause and restart

```bash
python -m scripts.station_capture_worker status
python -m scripts.station_capture_worker pause
# Leave scheduler variables false while investigating.
python -m scripts.station_capture_worker resume
python -m scripts.station_capture_worker status
```

Pause is persistent per DWD/DMI provider cursor. Disabling both scheduler
variables prevents new jobs; pausing providers prevents observation imports if
a job is dispatched accidentally. Resume does not backfill or rewrite
`received_at`. Catalog and exact model assets remain immutable evidence.

## First-cycle acceptance record

For at least two separated catalog/observation jobs and one process restart,
record:

- Git SHA, migration head, environment ID, runner ID and job ID;
- exact asset counts/cache hits and manifest versions;
- station-cycle counts by provider and structured errors;
- first and last operational capture timestamps;
- operational observations split into first-import LiveWind-usable, operational
  but too late, historical backfill and unproven origin;
- DWD validator state and unchanged first `received_at` on replay;
- catalog age, epoch changes and pending review counts;
- cache probe checksum and cross-job verification result;
- confirmation that purpose approvals, residuals, holdouts and public effects
  remain zero.

An isolated fixture or one live smoke does not change the status from
`continuous_capture_not_started`. Only successful authorised scheduled jobs on
the recorded commit and resources establish a real start time.
