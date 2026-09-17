# LiveWind operations and staged rollout

## Safety boundary

LiveWind has four non-negotiable product invariants:

1. `measurement` is a real station observation and remains separately labelled.
2. `current` is the existing model nowcast and is never rewritten by a station.
3. `live_wind` may consume **station residuals**, never raw station wind.
4. `forecast` is independent. This runbook does not implement or activate an
   adaptive forecast.

`LIVE_WIND_ROLLOUT_STAGE=shadow` is the default. Shadow jobs persist internal
analysis evidence in `weather_live_wind_jobs`; public endpoints do not read those
payloads. Raw model state, measurements, station residuals and finished LiveWind
analyses use separate cache namespaces. Measurement imports advance only the
LiveWind input generation; new model captures advance the weather generation.
Final analysis keys include spot, product, both generations, model/analysis/
physics/profile versions and the rollout/verification configuration. A short
distributed lock prevents cache stampedes without mixing spots or products.

## Deployment prerequisites

### Canary acceptance boundary (not the production Shadow workflow)

The repository workflow below uses production-scoped credentials and is **not**
a Staging/Canary launcher. Do not dispatch or enable it to test a staging
migration. This repository currently has no verified Linux runner, staging API,
or staging database inventory, so the 72-hour Canary is `canary_not_started`.
Its existing `LIVE_WIND_FORCE_BASELINE=true` setting keeps public station
adjustment closed; the Canary preflight additionally refuses `APP_ENV=production`,
non-local databases, non-Linux runners, public region allowlists, missing
ecCodes tools, non-UTC clocks, and unverified cache persistence.

On an **authorized isolated Linux staging runner**, after identifying and
recording the database host/name, Redis target and mounted cache path without
printing credentials, set `APP_ENV=development`, `LIVE_WIND_CANARY_MODE=true`,
`LIVE_WIND_ROLLOUT_STAGE=shadow`, `LIVE_WIND_FORCE_BASELINE=true`,
`LIVE_WIND_ENABLED_REGION_SLUGS=''` (or leave unset), a stable
`LIVE_WIND_CANARY_RUNNER_ID`, a unique `LIVE_WIND_CANARY_ID`, and the
expected `LIVE_WIND_EXACT_RUN_CACHE_ID`. Set
`LIVE_WIND_CANARY_STAGING_DATABASE` to the exact database name; it must match
`DATABASE_URL` and begin with `surfwind_staging_` or `surfwind_canary_`.
The staging DB must be a verified local target at `0059`; never use the
production `DIRECT_DATABASE_URL`.
Run these in two **different runner jobs** with different
`LIVE_WIND_RUNNER_JOB_ID` values:

```bash
python -m scripts.exact_run_preflight --persistence create
# Stop this process/job; start a new job on the same identified runner/mount.
python -m scripts.exact_run_preflight --canary --persistence verify \
  --expected-probe-sha256 '<checksum_sha256 from the first job, stored outside the mount>'
```

The first command writes only `.preflight-probes/persistence.json` under the
cache mount. The second verifies its cache identity, checksum, different
process and different runner-job ID, and repeats mount, atomic rename and
dependency checks. It never counts as model or activation evidence. A host
restart is **not** proven by this two-job test: report
`persistence_not_fully_verified` until an authorized host restart and a
repeat verification have actually occurred. Do not remove the probe or
replace its cache ID to make a failed verification pass. Keep the checksum
outside the mount in the operator's change record; set
`LIVE_WIND_CANARY_PROBE_SHA256` to it for all commands below.

The isolated control plane stores only operational state on the exact-run
mount. It never modifies a public product, activation profile or Forecast.
`canary-start` executes the first bounded cycle, and an authorized scheduler
must invoke `canary-cycle` every ten minutes thereafter. Each cycle is limited
to 900 seconds and the configured tile, station and spot batch sizes. A cycle
lock rejects concurrent runs; database leases and unique keys protect replay.
Pause/stop set a persistent kill switch checked between stages. An in-flight
provider call may finish its current stage, but it cannot begin the next one.
No automatic public activation occurs. The control status becomes `completed`
only after a real 72-hour wall-clock interval and successful cycles without a
gap beyond `LIVE_WIND_JOB_LATE_MINUTES`; that is technical continuity only,
not Pilot or Europe evidence.

```bash
python -m scripts.live_wind_canary preflight
python -m scripts.live_wind_canary migrate-check
python -m scripts.live_wind_canary canary-dry-run
python -m scripts.live_wind_canary canary-start
python -m scripts.live_wind_canary canary-status
python -m scripts.live_wind_canary canary-cycle
python -m scripts.live_wind_canary canary-report
python -m scripts.live_wind_canary canary-pause
python -m scripts.live_wind_canary canary-resume
python -m scripts.live_wind_canary canary-retry
python -m scripts.live_wind_canary canary-stop
```

`canary-retry` is permitted only for a failed run within the configured
current cycle window and only for transient connection/timeout errors. It
never backdates model availability or observation receipt. Any failed or
interrupted cycle irreversibly breaks that run's 72-hour continuity, even if
the operator later resumes collection. Stop does not delete cache assets,
jobs or evidence. A stopped run
cannot be resumed. If a new run is needed, retain the old state as a reviewed
archive before provisioning a distinct cache/control namespace; never edit
its run ID or evidence in place. The existing production-scoped GitHub Shadow
workflow is **not** the Canary scheduler.

`LIVE_WIND_VERIFICATION_MAX_SUBGROUP_REGRESSION_MS` alone no longer opens the
gate. A reviewed `LIVE_WIND_VERIFICATION_SUBGROUP_POLICY_VERSION` must be set
before creating immutable holdout evidence; the version and limit become part
of its context hash. The public gate requires exact evidence-policy agreement.
No threshold is approved in this repository, so both values stay unset and
the gate remains closed with `subgroup_regression_policy_missing`.

Apply the additive migration before starting either scheduler or worker:

```bash
alembic upgrade head
alembic current  # 0059_live_wind_holdout_cases (head)
alembic heads    # exactly one head
```

Configure the GitHub Actions workflow `.github/workflows/live-wind-shadow.yml`:

- repository variable `LIVE_WIND_SHADOW_ENABLED=true`;
- repository variable `WEATHER_OBSERVATION_ENDPOINT`, ending in
  `/cron/observations`;
- repository variable `LIVE_WIND_ENDPOINT`, ending in `/cron/live-wind`;
- optional repository variable `LIVE_WIND_HOLDOUT_TRAINING_MANIFEST`, an absolute
  path on the persistent runner to a separately reviewed training inventory;
- secrets `DIRECT_DATABASE_URL`, `REDIS_URL`, `LIVE_WIND_CRON_SECRET`, and
  `LIVE_WIND_WORKER_JWT_SECRET`;
- the API deployment's `CRON_SECRET` must equal `LIVE_WIND_CRON_SECRET`.
- a Linux self-hosted runner labelled `live-wind`, with a persistent shared
  read/write mount configured as `LIVE_WIND_EXACT_RUN_CACHE_DIR`. The path must
  itself be an absolute Linux mount point, not overlay/tmpfs. Provision a stable
  `.exact-run-cache-id` text file on that mount and set repository variable
  `LIVE_WIND_EXACT_RUN_CACHE_ID` to the same value. The worker checks mount
  type, identity, atomic rename and at least 5 GB free before capture or
  shadow analysis. A hosted ephemeral runner cannot pass this gate.

The workflow pins `LIVE_WIND_ROLLOUT_STAGE=shadow`; changing a repository
variable cannot accidentally activate public corrections. It runs every ten
minutes, captures exact GFS/ICON assets, imports a fair bounded station batch,
computes station residuals, enqueues a fair bounded spot batch, drains jobs,
then runs provider and scheduler doctors. Capture and residual errors are
reported independently and do not suppress the other providers or shadow
jobs. The worker and exact-run capture stages must share the same cache mount.
After the shadow batch, the workflow builds immutable holdout cases. Aggregate
verification is skipped until the reviewed training manifest path is set. A
missing manifest can still produce diagnostic cases, but none may be
`activation_eligible`. The preflight additionally checks database/Redis clock
skew, UTC runner time, the scheduled capture mode and shadow-only stage.

The direct database URL is worker-only. Never expose it to the frontend or use
it in a public serverless request. Run `scripts.live_wind_worker` on a persistent
worker if the full catalogue no longer fits the GitHub job budget.

### Holdout collection, replay and verification

Migration `0059_live_wind_holdout_cases` adds insert-only
`weather_live_wind_holdout_cases`. A database trigger rejects UPDATE and DELETE;
changed inputs get a new input hash and row. The worker removes the target
station, strong-ID/spatial aliases, explicit dependencies and its nearby or
declared correlation group **before station scoring**. It then uses only foreign
observations with `observed_at`, `received_at` and `imported_at` at or before
the original `analysis_cutoff_at`, and residuals created by that cutoff. The
target model must have completed first-seen capture before the hidden
measurement's `observed_at`. The hidden u/v vector is queried only after model,
station selection and prediction. A second audit checks the sealed case before
aggregate scoring. Unknown receipt/import times, legacy exact bundles, trained
station profiles without source lineage and target physics profiles without
training lineage are excluded from activation. Diagnostic cases retain reasons.
Because station approval and geometry are mutable records rather than historical
snapshots, a station whose metadata was updated after the cutoff is also excluded
from activation on replay. This conservatively limits backfill; it does not
reconstruct a historical station approval from today's state.

The current candidate engine is static and untrained. A reviewed manifest may
therefore list exactly one source, `regional-live-wind-engine`, whose
`content_hash` equals the SHA-256 of the deployed
`app/weather/live_wind_analysis.py`, with an empty `weather_blocks` list.
`training_source_hash` must be the canonical hash of the `training_sources`
array. A date or reviewer flag alone is not proof. Trained profiles cannot be
declared safe using this static-source manifest; their input lineage needs a
separate implementation/review. Neither manifest nor builder activates serving.

The reviewed JSON manifest must contain `candidate_version`, UTC
`training_window_end`, UTC `frozen_at`, `reviewed: true`,
`lineage_complete: true`, `training_weather_blocks: []`, one
`training_sources` entry with `source_id: "regional-live-wind-engine"`,
`content_hash`, UTC `last_observed_at` no later than the training boundary and
`weather_blocks: []`, plus the canonical `training_source_hash`. Obtain the
deployed engine hash with:

```bash
python -c "from app.weather.live_wind_holdouts import _engine_hash; print(_engine_hash())"
```

Have a reviewer compare the manifest against the deployed source and freeze
time; do not manufacture an earlier training boundary from later observations.

Run on the configured persistent Linux runner after migration and mount
provisioning (these commands are **not** a production acceptance claim):

```bash
python -m scripts.exact_run_preflight
python -m scripts.live_wind_holdouts status
python -m scripts.live_wind_holdouts build --dry-run --limit 25
python -m scripts.live_wind_holdouts build --limit 25
python -m scripts.live_wind_holdouts build --limit 25 --since 2026-09-01T00:00:00+00:00 --until 2026-09-02T00:00:00+00:00
python -m scripts.live_wind_holdouts build --limit 25 --recompute --candidate-version regional-live-wind-uv-v2
python -m scripts.live_wind_holdouts verify --training-manifest /persistent/live-wind/reviewed-training.json --dry-run
python -m scripts.live_wind_holdouts verify --training-manifest /persistent/live-wind/reviewed-training.json
python -m scripts.live_wind_doctor --days 14 --no-rasters
```

`build` is bounded and resumable; a repeated input cannot duplicate a case.
`--recompute` deliberately creates a new immutable version only if inputs
changed. `status` is read-only. Historical assets first captured today cannot
make old measurements activation-eligible. Missing historical station-receipt
timestamps remain unproven.

Verification persists via `persist_live_wind_verification_evidence`; the
operations report reads actual case and evidence rows. Country/station-group
balancing and 24-hour weather-block bootstrap are used for aggregate intervals.
Pilot checks require 500 eligible cases, 14 days, 10 target stations, four wind
sectors, <=35% fallbacks, calm/strong/rapid-change/conflict cases and multiple
countries, terrain and coastal classes. Small subgroups are reported as
`insufficient_evidence`. No subgroup regression limit has been approved:
`LIVE_WIND_VERIFICATION_MAX_SUBGROUP_REGRESSION_MS` defaults to unset and keeps
the activation gate closed. Fourteen days cannot establish Europe-wide
seasonal readiness.

### Exact-run raw cache and first-seen contract

`ExactRunLoader` uses only NOAA/NCEP GFS 0.25-degree subset GRIB and DWD
ICON-EU GRIB fields. It stores raw bytes under SHA-256 object names and atomic
per-run/lead/field/domain manifests. GFS uses reusable 10-degree tiles; ICON-EU
uses one shared grid asset per lead/field. The first **completed capture** is
`available_at`; run initialization alone never establishes availability.
Future or uncaptured historical files cannot be retroactively declared available.
Same-source changes found during the hourly verification pass write a conflict
sidecar and make that asset ineligible; the original object and manifest remain
for audit. Linux advisory locks release automatically if a worker dies. A
malformed/truncated GRIB is rejected before a manifest is published.

Do not automatically prune this cache yet. Back up manifests, objects and
conflicts together; monitor disk capacity. Every SHA referenced by persisted
station residuals or LiveWind job bundle diagnostics must remain available.
A future cleanup job must first build that reference set, run in dry-run mode,
and only consider unreferenced objects after a reviewed retention period.
Never remove a conflict sidecar to make old evidence appear eligible.

The legacy `baseline_bundle_hash` remains an immutable per-tile provenance
hash. New `dataset_bundle_hash` covers only the logical run, provider, model,
dataset version, valid times, required fields, loader/manifest version and
eligibility class. It excludes tile, location, retrieval time and concrete
bytes. Each raw cache object has an `asset_content_hash`; station and target
have distinct `sample_hash` values including cells and temporal interpolation.
The residual join requires matching dataset hashes **and** explicit manifest
compatibility. Different tiles are allowed. Existing v1 residuals retain their
old hash and are invalid for activation until reproduced as v2 evidence.
Old cache manifests with only `available_at` are classified as availability
unproven; that timestamp is never reinterpreted as a completed capture.
Provider publication metadata/source revisions are currently unavailable in
the adapters, so only verified first-seen captures before observation qualify.

Deterministic local acceptance, using only local `surfwind_test`, Redis and
small offline GFS/ICON fixtures (the test fixture resets that test database's
`public` schema; do not point it at a valuable database):

```bash
docker compose up -d db redis
python -m scripts.live_wind_shadow_smoke
```

The command emits one JSON summary and exits nonzero if preflight, empty/
legacy migration, fixture import→residual→shadow, idempotency, concurrency or
final schema checks fail. It never fetches weather or changes public products.
For the actual persistent runner use `python -m scripts.exact_run_preflight`
before capture; it requires Postgres, Redis, current migration and the mount.

Known unrelated issue: the existing public `DwdIconProvider._nearest` imports
`codes_grib_new_from_message`, which is absent in local ecCodes 2.44.0. The
internal `nearest_exact_grid` uses the available `codes_new_from_message` and
is exercised separately. This package does not change the public sampler.

Dry-run rebuild audit (read-only): group `weather_station_model_residuals` by
`baseline_version`, `activation_eligible` and `qc_status`; separately count
`weather_live_wind_jobs` with `diagnostics.baseline_source` equal to
`exact_run_bundle`. Keep all prior rows. Only new observations with recorded
pre-observation first-seen assets can produce eligible exact-run residuals;
there is no honest backfill for old measurements lacking availability proof.

## Data mounts and doctors

The current request-time LiveWind calculation uses already reviewed spot
profiles. Offline production/review of those profiles needs these mounts:

- `GWA_RASTER_DIR`: GWA v3 10 m wind-speed mosaic, normally
  `gwa_wind-speed_10.tif` (or set `GWA_RASTER_FILENAME_TEMPLATE`);
- `WORLDCOVER_RASTER_DIR`: ESA WorldCover 10 m tiles;
- `GLO30_DEM_RASTER_DIR`: Copernicus GLO-30 elevation tiles;
- `GLO30_WBM_RASTER_DIR`: GLO-30 Water Body Mask tiles.

Do not place these in a public media bucket. Mount them read-only on the offline
profile/doctor worker. GitHub-hosted runners intentionally call the doctor with
`--no-rasters`; run the complete doctor on the mounted worker:

```bash
python -m scripts.live_wind_doctor --days 14 --fail-on-alert
python -m scripts.check_gwa_raster
python -m scripts.check_microscale_raster --lat 54.5 --lon 8.5
```

The provider doctor performs no external probe. It checks configured connectors,
current station counts per provider and country, last import attempt and sanitized
error state. This prevents a doctor from worsening a provider outage or consuming
rate limits.

## Queue behavior

- `(spot_id, cycle_at, analysis_version)` makes scheduler replay idempotent.
- A partial unique index permits only one queued/processing/retry job per spot.
- Claims use `SELECT … FOR UPDATE SKIP LOCKED` plus a random worker token.
- Only the token owner may heartbeat, complete, or retry a job.
- A stale heartbeat makes a job reclaimable after
  `LIVE_WIND_JOB_LEASE_SECONDS` (default 300 s).
- Failed jobs use bounded exponential backoff and become terminal only after
  `LIVE_WIND_JOB_MAX_ATTEMPTS` (default 5).
- Never-run and least-recently-run spots sort first; active jobs are excluded.
  This prevents a fast or permanently failing spot from starving the catalogue.
- The job result records station count, correction magnitude, conflict,
  uncertainty, confidence, fallback, exclusions, cache hit, runtime, region and
  terrain class.

Observation imports use the same oldest-first principle. Failed station/provider
attempts set `next_attempt_at` with bounded exponential backoff. Successful imports
clear the backoff. Provider failures are isolated per station and cannot block
other configured providers.

## Monitoring and alarm limits

The internal endpoint is:

```text
GET /admin/weather/live-wind/operations?days=14&include_rasters=true
GET /admin/weather/live-wind/jobs?status=failed
```

Default alarm/readiness thresholds are configuration, not constants hidden in
the worker:

| Signal | Warning / fallback |
|---|---|
| station import missing/late | critical after `LIVE_WIND_IMPORT_LATE_MINUTES=30` |
| enqueue/worker success missing/late | critical after `LIVE_WIND_JOB_LATE_MINUTES=45` |
| oldest due job | critical after 45 minutes (starvation) |
| stations in provider error | warning immediately; persistent scheduler/provider lateness is critical |
| station count per public correction | baseline below `LIVE_WIND_MIN_STATION_COUNT=2` |
| confidence | baseline below `LIVE_WIND_MIN_CONFIDENCE=0.20` |
| conflict | baseline above `LIVE_WIND_MAX_CONFLICT_INDEX=0.65` |
| uncertainty | baseline above `LIVE_WIND_MAX_UNCERTAINTY_MS=5.0` |
| correction magnitude | baseline above `LIVE_WIND_MAX_CORRECTION_MS=6.0` |
| regional shadow fallback rate | automatic public baseline above `LIVE_WIND_READINESS_MAX_FALLBACK_RATE=0.35` |

The report also includes active/current stations by provider and country,
typical observation delay and interval, missing station metadata, duplicate
identities, license state, all station-selection exclusion reasons, cache hit
rate, runtime distributions, and operational outcomes grouped by terrain and
region. These grouped values are operational failure/fallback metrics, **not an
accuracy score**.

Alert delivery is supplied by the scheduler platform: `live_wind_doctor
--fail-on-alert` exits 2 for critical provider/scheduler alerts and makes the
Action fail. Route failed workflow notifications to the on-call channel before
enabling a pilot.

## Rollout sequence

Rollout never advances automatically:

1. `shadow`: collect only; no public station adjustment.
2. Keep shadow running across at least
   `LIVE_WIND_READINESS_MIN_DAYS=14`, at least 500 analyses and at least four of
   eight wind sectors. Include calm, frontal/high-conflict and strong-wind days.
3. `internal`: inspect stored results in the admin endpoints; public remains
   baseline.
4. `pilot`: set `LIVE_WIND_ENABLED_REGION_SLUGS` to a small reviewed allowlist.
5. `regional`: expand the same explicit allowlist one region at a time.
6. `global`: only after independent held-out validation. The per-analysis
   quality gate, recent regional shadow-health circuit and emergency fallback
   remain active. The circuit requires at least
   `LIVE_WIND_HEALTH_MIN_ANALYSES=10` within
   `LIVE_WIND_HEALTH_WINDOW_MINUTES=360`.

Before `pilot`, require all `rollout_readiness.checks` to pass and evaluate the
configured candidate with spatial leave-one-station-out plus temporal block
holdouts. The target station, its observation and detected dependent/double
stations must be absent from the analysis input. Store the result once in
`weather_live_wind_verification_evidence` and configure its exact context hash in
`LIVE_WIND_VERIFICATION_CONTEXT_HASH`. Public activation fails closed unless the
candidate version, sample/day/station thresholds, positive minimum improvement
and positive lower confidence bound all match. Evidence never advances the
rollout stage automatically; region allowlists and the manual rollout remain
mandatory. Operational health alone cannot authorize a scientific rollout.
The subgroup harm threshold remains unset and therefore blocks activation even
if aggregate holdout metrics eventually pass. Trained-profile cases also remain
ineligible until their source lineage is independently auditable.

## Immediate rollback

Set `LIVE_WIND_FORCE_BASELINE=true` and redeploy/restart API instances. This
overrides every stage, including `global`, but leaves shadow evidence intact for
diagnosis. Alternatively move the stage to `shadow`. No observation, residual,
forecast or job row needs deletion.

For a single bad region, remove its slug from
`LIVE_WIND_ENABLED_REGION_SLUGS`. A quality violation on an individual analysis
already returns the model baseline immediately with a `quality_gate:*` fallback
reason. Never edit a shadow result into a public value and never clear the job
table as a rollback mechanism.

## Current hard blocker and adaptive Forecast decision

The repository has an internal exact-run loader, scheduled shadow path and a
locally fixture-tested holdout builder. It has **not** been accepted on a
self-hosted Linux runner. The persistent mount, migration, full live worker
flow and 14+ representative days of independent evidence still require
operational acceptance. No real pilot evidence is asserted here. Open-Meteo
`current` remains a separate
public model nowcast and never substitutes for an exact shadow model run.
The exact shadow sampler uses `DwdIconProvider.nearest_exact_grid` because the
pre-existing public `_nearest` path imports an ecCodes symbol absent from the
pinned runtime. That public provider path was deliberately left unchanged in
this work package and needs a separate regression-checked repair.

Do **not** begin the adaptive Forecast while any of these are true:

- the exact-run loader or persistent capture mount is not operational;
- fewer than 14 representative days/weather regimes are available;
- held-out LiveWind accuracy and uncertainty calibration are missing;
- product-boundary audit reports a measurement/forecast source violation;
- any pilot readiness or doctor check fails.
