# Station model-error evidence

Status: calculation and persistence foundation implemented. Quality-checked
residuals can feed the separate regional LiveWind analysis; no residual changes
station measurements, `current`, raw model values, or forecast values.

## Product boundary

The calculation is strictly:

`residual_uv = measured_uv - expected_station_model_uv`

`StationModelBaseline` is the shared immutable input contract used to create
LiveWind residual evidence. It contains raw model vectors only. Calibration,
station adjustment, adaptive forecast output, or any model value carrying
observation lineage fails QC before interpolation.

The existing Open-Meteo public path usually exposes only capture-time run
provenance. It is therefore not silently promoted to an exact forecast run for
model-error evidence. `baseline_from_normalized_values` bridges the direct
official GFS/ICON adapters. The internal `ExactRunLoader` now supplies the
shared, immutable `exact-run-bundle-v2` logical dataset identity for station
and LiveWind target from the same GFS/ICON run, even across different tiles.
It requires a completed first-seen capture no later
than the station observation; a run timestamp alone is insufficient.

## Calculation

For every expected model member, the calculator:

1. selects one exact/provider-reported run strictly older than the observation;
2. requires that same run to bracket the actual observation time;
3. interpolates `u` and `v` linearly, never speed and direction;
4. records both endpoint times, interpolation fraction, run identity, grid
   distance, fetch time, dataset, provider, source key, and both endpoint
   vectors needed to reproduce interpolation;
5. combines available raw members with the versioned family-weight consensus;
6. optionally applies local physics member-by-member only through an active,
   explicitly reviewed station physics profile; and
7. subtracts the expected station vector from the measured vector.

A missing reviewed station profile leaves the raw station-coordinate model
unchanged and marks representativeness uncertainty as
`elevated_no_reviewed_station_profile`. Missing model members remain visible and
degrade QC. No members produces `unavailable`, not a fabricated residual.

Gust evidence is a separate scalar comparison. The mean-wind physics factor is
not copied onto gusts; the record states `separate_scalar_gust_residual` and
retains missing gusts as unavailable.

## Reproducibility and persistence

`weather_station_model_residuals` stores immutable evidence for:

- observation, station, analysis time, calculation and baseline versions;
- every model and run identity;
- raw consensus, expected station, measurement, and residual vectors;
- interpolation and per-member weights;
- separate gust evidence;
- station-profile and physics versions; and
- QC status, reasons, and representativeness uncertainty.
- legacy per-tile bundle hash, logical dataset manifest/hash, concrete asset
  hashes, temporal/spatial sample manifest/hash, first-seen availability,
  sampling cells/method and activation eligibility for new exact-run rows.

The SHA-256 `analysis_id` covers the calculation-relevant observation and
station snapshots, every raw model input, expected model set, station-profile
snapshot, effective physics blend, and full policy snapshot. The uniqueness
constraint makes replay idempotent without overwriting earlier evidence while
still recognizing a changed measurement or configuration as a new analysis.

`run_station_model_error_analysis` drains suitable accepted observations using
an injected `StationModelBaselineLoader`. The shadow workflow runs the exact
loader after imports. Scheduled selection is limited to recent 48-hour
observations; an already recorded exact-run availability failure is not
silently retried because later capture cannot backdate first-seen time.
Provider failures are isolated per observation. Legacy rows are retained but
cannot be used for new activation evidence. The worker shares a persistent
raw-cache mount with the capture stage.

The internal admin endpoint
`GET /admin/weather/stations/{station_id}/model-residuals` exposes the stored
evidence for review. Serving consumes only `accepted`/`degraded` rows that also
pass the current station-selection, compatibility, age, air-mass and robust
analysis gates.

## Versioning

- baseline contract: `raw-model-baseline-v1`
- exact-run bundle/loader: `exact-run-bundle-v2` / `exact-run-loader-v2`
- exact-run dataset manifest/sample: `exact-run-dataset-manifest-v2` /
  `exact-run-sample-v1`
- calculation: `station-model-error-uv-v1`
- consensus: `family-uv-v1`

Any change to run selection, interpolation, weights, gates, or vector semantics
must bump the corresponding version before new evidence is written.
