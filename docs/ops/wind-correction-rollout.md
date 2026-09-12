# Wind-correction rollout runbook

The full pipeline (WP1–WP6 + sector-producer runner + WP3-A omnidirectional GWA)
is on `main` and tested. Nothing changes the served wind until the data below is
mounted and sectors are **deliberately activated** after a measured bias drop.
Validated end-to-end against real data (Luxembourg City: GWA 10 m = 2.82 m/s,
ERA5 2008–2017 = 3.37 m/s → factor **C = 0.84**).

Prerequisites that are data/ops, not code: a mounted GWA raster, approved
reference stations with accumulated observations, and (for WP5) WorldCover +
GLO-30 rasters.

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

## 2. Build candidate sectors (served wind unchanged)

```
python -m scripts.run_sector_producer --all            # or --limit N
# or schedule the cron (bounded, resumable):
#   GET /cron/build-sectors   (Authorization: Bearer $CRON_SECRET)
```

Writes 12 **candidate** sectors per spot (`enabled=False`, one omnidirectional C
each). `select_sector` serves only the newest *enabled* version, so candidates
cannot change a served value. Re-runs are hash-idempotent.

## 3. Approve reference stations and accumulate the baseline

```
# per spot: pick the nearest official station, then approve it (admin review):
#   POST /admin/weather/spots/{id}/station/auto?provider=dwd   (dwd|dmi)
#   -> set the station approved=True and representativeness_status="passed"
export CRON_SECRET=...   # required for the cron endpoints
# schedule (Vercel cron): GET /cron/observations  and  GET /cron/verification
```

`/cron/observations` imports real station observations (DWD/DMI open data; KNMI
needs a key). `/cron/verification` recomputes model calibration and the
raw-forecast scores, and runs WP6 sector calibration once measurements exist. Let
observations accumulate (weeks), then snapshot a baseline:

```
python -m scripts.verification_report --persist     # note the baseline run_id
```

## 4. Activate — the only step that changes served wind (WP1-gated)

The gate is a **within-run** comparison: `/cron/verification` (via
`run_gated_verification_scoring`) replays the current serving baseline (including
active calibration and any already active sector version) **and** each spot's
latest candidate through the same member preparation and family-weighted vector
consensus over the *same* samples and observations. Activation then requires the
candidate to lower the sample-weighted public-consensus error — not merely a
different weather window. The gate also fingerprints the candidate contents,
active baseline, model calibration, family blend and physics/consensus versions;
any change requires a fresh gated run.

```
# take a gated run (serving baseline + version-bound candidate in one run_id)
python -m scripts.verification_report --gated --persist    # note the run_id
python -m scripts.activate_sectors --run <run_id> --min-bias-drop 0.2
```

`candidate_bias_improvement(run_id)` = `serving_baseline_mae − candidate_mae` per spot;
activation fires only where that drop ≥ threshold. Per spot, the same gate is
mandatory:
`POST /admin/weather/spots/{id}/sectors/activate?version=N&run_id=RUN&min_bias_drop=0.2`.
If a model family overcorrects, lower `WIND_SECTOR_BLEND` (e.g. `{"regional":0.5}`)
and re-score before activating.

The gated score records the exact candidate version; batch activation will never
substitute a newer, unscored version. Activation accepts only a complete set of
12 canonical 30-degree sectors on an active profile. It then makes those rows
effective in both live and forecast serving, deactivates older forecast snapshots,
and drops assembled Redis responses so the retained raw provider payload can be
recalculated immediately. Existing browser/CDN responses can remain visible for
their advertised cache lifetime (up to 5 minutes for live and 30 minutes for the
forecast).

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
alembic current       # must show: 0050_verification_gate_context (head)
alembic heads         # must show the same single head
```

Old verification runs cannot be promoted after this migration. Generate a
fresh run from real observations, inspect it, and activate only that run:

```
python -m scripts.verification_report --gated --persist --lookback-days 45
python -m scripts.activate_sectors --run <fresh-run-id> --min-bias-drop 0.2
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
Re-run the gated report after enough new observations have accumulated and
compare the public-consensus MAE. Roll back operationally by activating a newly
scored replacement candidate; never flip `enabled` directly.

## 5. WP5 microscale (directional, where residual bias remains)

```
export WORLDCOVER_RASTER_DIR=/path/to/worldcover   # ESA WorldCover 10 m tiles
export GLO30_WBM_RASTER_DIR=/path/to/glo30-wbm     # GLO-30 Water Body Mask tiles
# validate the exact tiles a representative spot needs (fails loudly on a
# missing/unreadable tile, wrong CRS, empty layer, or wrong product codes):
python -m scripts.check_microscale_raster --lat 43.66 --lon -1.44   # must exit 0
python -m scripts.run_sector_producer --producer microscale --all
```

The provider is **fail-closed**: a missing or unreadable tile yields *no* factor
for that spot (and truncates the upwind fetch walk) rather than silently reading
the cell as water — only an in-file NoData pixel counts as water (Charnock). So a
mis-mount produces `microscale_unavailable`, never a fabricated correction.

Microscale writes a higher sector version that overrides the omnidirectional GWA
prior per sector after activation; it is stored disabled and must use the same
gated path (step 4). WP6 measurement calibration also writes disabled candidates
through `/cron/verification`; neither producer can alter serving by itself.

## Notes

- Real GWA download naming is `{ISO3}_wind-speed_{height}m.tif` (per country); the
  reader expects one mosaicked file per variable under `GWA_RASTER_DIR`.
- GWA gives an **omnidirectional** factor (amount only). Direction (cape vs. bay,
  on/offshore) comes only from WP5. Until then it is labelled omnidirectional.
- Station wind never enters a forecast value — it only scores and calibrates.
