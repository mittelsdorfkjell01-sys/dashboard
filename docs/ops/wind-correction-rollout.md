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
`run_gated_verification_scoring`) scores the raw forecast **and** each spot's
latest candidate as a shadow-corrected variant over the *same* samples and
observations, writing both under one run id. Activation then requires the
candidate to actually lower the error — not merely a different weather window.

```
# take a gated run (raw + corrected in one run_id)
python -m scripts.verification_report --gated --persist    # note the run_id
python -m scripts.activate_sectors --run <run_id> --min-bias-drop 0.2
```

`candidate_bias_improvement(run_id)` = `raw_mae − corrected_mae` per spot;
activation fires only where that drop ≥ threshold. Per spot:
`POST /admin/weather/spots/{id}/sectors/activate?version=N`.
If a model family overcorrects, lower `WIND_SECTOR_BLEND` (e.g. `{"regional":0.5}`)
and re-score before activating.

> Note: activating a sector makes it `enabled=True`, but the serving resolver
> (`resolve_weather_profile`) does not yet surface enabled sectors into the live
> forecast — that wiring is a separate, deliberate decision. The shadow score
> above faithfully measures what activation *would* do once that path is opened.

## 5. WP5 microscale (directional, where residual bias remains)

```
export WORLDCOVER_RASTER_DIR=/path/to/worldcover   # ESA WorldCover 10 m tiles
export GLO30_WBM_RASTER_DIR=/path/to/glo30-wbm     # GLO-30 Water Body Mask tiles
python -m scripts.run_sector_producer --producer microscale --all
```

Microscale writes a higher sector version that overrides the omnidirectional GWA
prior per sector; activate it the same gated way (step 4). WP6 measurement
calibration continues automatically through `/cron/verification`.

## Notes

- Real GWA download naming is `{ISO3}_wind-speed_{height}m.tif` (per country); the
  reader expects one mosaicked file per variable under `GWA_RASTER_DIR`.
- GWA gives an **omnidirectional** factor (amount only). Direction (cape vs. bay,
  on/offshore) comes only from WP5. Until then it is labelled omnidirectional.
- Station wind never enters a forecast value — it only scores and calibrates.
