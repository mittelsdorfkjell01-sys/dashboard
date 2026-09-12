# Wind-correction rollout runbook

The production prior composes WP3-A and WP5: the omnidirectional GWA/ERA5
level factor is multiplied by the direction-dependent roughness/fetch factor.
WP6 may later shrink that physical prior towards measurements. Every result is
written as a disabled candidate; nothing changes a served value until a
candidate passes the holdout gate and is deliberately activated.

The GWA input path has been checked against real data (Luxembourg City:
GWA 10 m = 2.82 m/s, ERA5 2008–2017 = 3.37 m/s → factor **C = 0.84**).
The combined result still needs the mounted production rasters and per-spot
holdout evidence described below.

Prerequisites that are data/ops, not code: mounted GWA, WorldCover and GLO-30
WBM rasters plus approved reference stations with accumulated observations.

## 1. Mount the GWA raster and validate

GWA v3 serves free (CC BY 4.0) per-country GeoTIFFs; **10 m wind-speed exists**:

```
# per country (ISO3), 10 m wind-speed; 302-redirects to the CDN file
#   <ISO3>_wind-speed_10m.tif  (EPSG:4326, NaN NoData, 250 m, ~0.2 MB small country)
curl -sL -o FRA_wind-speed_10m.tif \
  https://globalwindatlas.info/api/gis/country/FRA/wind-speed/10
```

Mosaic the countries you cover into a single Europe GeoTIFF named to match the
reader template (default `gwa_{variable}_{height}.tif` → `gwa_wind-speed_10.tif`),
or set `GWA_RASTER_FILENAME_TEMPLATE` to your scheme. Then:

```
export GWA_RASTER_DIR=/path/to/gwa
python -m scripts.check_gwa_raster        # must exit 0: CRS 4326, 10 m, plausible values
```

The doctor fails loudly on a 100 m layer, power-density, wrong CRS, or a missing
file — fix the mount before proceeding. (Combined Weibull A/k are the fallback if
a wind-speed layer is unavailable.)

## 2. Mount and validate the microscale rasters

```
export WORLDCOVER_RASTER_DIR=/path/to/worldcover   # ESA WorldCover 10 m tiles
export GLO30_WBM_RASTER_DIR=/path/to/glo30-wbm     # GLO-30 Water Body Mask tiles
python -m scripts.run_sector_producer --producer combined --check-rasters \
  --lat 43.66 --lon -1.44
```

The combined doctor must report both `gwa.ok=true` and `microscale.ok=true`.
A missing/unreadable raster or an incomplete set of 12 sectors fails closed and
writes no candidate.

## 3. Build combined candidate sectors (served wind unchanged)

```
python -m scripts.run_sector_producer --producer combined --all  # or --limit N
# or schedule the cron (bounded, resumable):
#   GET /cron/build-sectors   (Authorization: Bearer $CRON_SECRET)
```

Writes 12 **candidate** sectors per spot (`enabled=False`). Each speed factor is
`clamp(GWA/ERA5 × roughness/fetch, 0.50, 1.60)`. `select_sector` serves only the
newest *enabled* version, so candidates cannot change a served value. Re-runs
are hash-idempotent. `gwa` and `microscale` remain available as diagnostic
standalone producers; production rollout uses `combined`.

## 4. Approve reference stations and accumulate the baseline

```
# per spot: pick the nearest official station, then approve it (admin review):
#   POST /admin/weather/spots/{id}/station/auto?provider=dwd   (dwd|dmi)
#   -> set the station approved=True and representativeness_status="passed"
export CRON_SECRET=...   # required for the cron endpoints
# schedule (Vercel cron): GET /cron/observations  and  GET /cron/verification
```

`/cron/observations` imports real station observations (DWD/DMI open data; KNMI
needs a key). `/cron/verification` recomputes model calibration and the
raw-forecast scores, runs WP6 sector calibration once measurements exist, and
deletes one bounded batch of forecast samples older than the configured
retention. Forecast captures are quantised to six-hour identities by default so
cache refreshes are not treated as independent model runs. Let observations
accumulate (weeks), then snapshot a baseline:

```
python -m scripts.verification_report --persist     # note the baseline run_id
```

## 5. Activate — the only step that changes served wind (WP1-gated)

The gate is a **within-run** comparison: `/cron/verification` (via
`run_gated_verification_scoring`) replays the current serving baseline (including
active calibration and any already active sector version) **and** each spot's
latest candidate through the same member preparation and family-weighted vector
consensus over the *same* samples and observations. Activation then requires the
candidate to lower the public-consensus error — not merely a different weather
window. Repeated model runs are collapsed to one error pair per forecast-valid
instant. The 95% confidence interval is bootstrapped over UTC-day blocks.

The enforced defaults require all of the following:

- MAE drop of at least `0.2 m/s`;
- at least `100` unique forecast-valid instants;
- at least `14` distinct UTC days;
- a strictly positive lower bound of the 95% day-block bootstrap interval.

Until the count/day floors are met, the state is `collecting`; a weak or
uncertain result is `rejected`. The gate also fingerprints candidate contents,
active baseline, model calibration, family blend and physics/consensus versions;
any change requires a fresh gated run.

```
# take a gated run (serving baseline + version-bound candidate in one run_id)
python -m scripts.verification_report --gated --persist    # inspect gate_evidence
python -m scripts.activate_sectors --run <run_id>
```

`candidate_bias_improvement(run_id)` = `serving_baseline_mae − candidate_mae`
per spot. The configured gate floor always applies; CLI/API parameters can only
make it stricter, never relax it. Per spot, the same gate is mandatory:
`POST /admin/weather/spots/{id}/sectors/activate?version=N&run_id=RUN`.
If a model family overcorrects, lower `WIND_SECTOR_BLEND` (e.g. `{"regional":0.5}`)
and re-score before activating.

For a WP6 posterior, scoring starts strictly after the immutable training-window
end stored in the candidate. The pending posterior is frozen while future
holdout data accumulates, preventing training/validation overlap. A malformed or
legacy posterior cannot authorize activation and is rebuilt with a valid
boundary by the calibration worker.

The gated score records the exact candidate version; batch activation will never
substitute a newer, unscored version. Activation accepts only a complete set of
12 canonical 30-degree sectors on an active profile. It then makes those rows
effective for the locally corrected model wind, deactivates older forecast
snapshots, and drops assembled Redis responses so the retained raw provider
payload can be recalculated immediately. The measured station-based **Live Wind
remains a separate product**: forecast model-bias calibration and WP6 never
rewrite that measurement. When no accepted live measurement exists, the live
fallback can still be a locally corrected model value and is labelled by its
source. Existing browser/CDN responses can remain visible for their advertised
cache lifetime (up to 5 minutes for live and 30 minutes for the forecast).

Deployment migration `0049_disable_ungated_sectors` resets legacy Microscale and
WP6 rows that were written as enabled by the old automatic paths. Treat them as
candidates again: create a fresh gated run after deployment, then activate the
version explicitly. Older gated runs used an unversioned `corrected` label and
remain readable for reporting, but cannot authorize activation. Runs without a
serving-context fingerprint are likewise reporting-only.

### Post-deploy proof and alerts

Run the migration before deploying workers or API instances that write/read the
gate fingerprint, then prove the deployed database is at the expected head:

```
alembic upgrade head
alembic current       # must show: 0051_sector_gate_evidence (head)
alembic heads         # must show the same single head
```

Old verification runs cannot be promoted after this migration. Generate a
fresh run from real observations, inspect it, and activate only that run:

```
python -m scripts.verification_report --gated --persist --lookback-days 45
python -m scripts.activate_sectors --run <fresh-run-id>
python -m scripts.verification_report --gated --persist --lookback-days 45
```

The application emits stable operational events with structured `weather_*`
fields. Build log-based counters and alerts from these event names:

| Event | Important fields | Alert intent |
|---|---|---|
| `weather_sector_gate_rejected` | `weather_reason_code`, `weather_spot_id`, `weather_gate_run_id`, context hashes | Alert on repeated `stale_serving_context`; it means operators are trying to activate an obsolete score. |
| `weather_forecast_publisher_superseded` | `weather_reason_code`, `weather_phase`, `weather_job_id`, `weather_spot_id` | Track rate; occasional races are expected, a sustained increase means serving state is churning. |
| `public_weather_cache_generation_advanced` | `weather_spot_id`, previous/new generation | Correlate profile/sector changes with cache invalidation. |
| `weather_sector_activation_succeeded` | version, run, context hash, MAE drop, invalidated snapshots | Audit every serving change and its measured justification. |
| `weather_forecast_publisher_succeeded` | job, spot, context hash, cache generation | Confirm the next publisher run uses the activated context. |

For each activated spot, verify the activation event is followed by a cache
generation advance and a successful publisher carrying the new context hash.
Use `GET /admin/weather/verification/runs` for recent per-spot gate status,
reason, MAE drop, confidence interval, unique valid instants, distinct days and
WP6 training boundary. Re-run the gated report after enough new observations have accumulated and
compare the public-consensus MAE. Roll back operationally by activating a newly
scored replacement candidate; never flip `enabled` directly.

## 6. WP5 and WP6 model limits

```
python -m scripts.check_microscale_raster --lat 43.66 --lon -1.44
python -m scripts.run_sector_producer --producer combined --all
```

The provider is **fail-closed**: a missing or unreadable tile yields *no* factor
for that spot (and truncates the upwind fetch walk) rather than silently reading
the cell as water — only an in-file NoData pixel counts as water (Charnock). So a
mis-mount produces `microscale_unavailable`, never a fabricated correction.

Microscale roughness/fetch and the GWA level factor are composed, not treated as
alternatives. The current production model does not claim an orographic speed-up
or direction deflection: both stay neutral until a validated terrain/flow model
and suitable rasters are supplied. WP6 measurement calibration writes disabled
posterior candidates through `/cron/verification`; neither it nor a physical
producer can alter serving by itself.

## Notes

- Real GWA download naming is `{ISO3}_wind-speed_{height}m.tif` (per country); the
  reader expects one mosaicked file per variable under `GWA_RASTER_DIR`.
- GWA gives an **omnidirectional** level factor. Direction-dependent speed
  variation comes from WP5 roughness/fetch; direction offsets are currently zero.
- Station wind never enters a forecast value — it only scores and calibrates.
- Relevant policy settings are `WIND_SECTOR_MIN_MAE_DROP_MS`,
  `WIND_SECTOR_GATE_MIN_UNIQUE_VALID_TIMES`,
  `WIND_SECTOR_GATE_MIN_DISTINCT_DAYS`,
  `WIND_SECTOR_GATE_BOOTSTRAP_ITERATIONS`,
  `WEATHER_FORECAST_SAMPLE_INTERVAL_HOURS` and
  `WEATHER_FORECAST_SAMPLE_RETENTION_DAYS`.
