# Weather Field v2 and Europe wind-map foundation

Status: **Wind and ten-day wave field serving, automatic gated publication, spot
refresh and operational monitoring are implemented**. ICON-D2/ICON-EU/GFS
provide the wind hierarchy; EWAM and GWAM provide European and global wave
guidance through T+174, and NOAA GFS-Wave supplies the bounded T+168..T+240
extended-range tail
coverage. Non-experimental publications are rejected unless they use the
frozen geometry, quantization, compression and LOD profile. Point providers
remain the explicit forecast fallback outside a usable field horizon.

## Product boundary

The Europe wind map is a model field, not a collection of spot forecasts. One
paired `wind_u`/`wind_v` field is the source for color, particles, arrows and
sampling. Spot pages may place `spot_adjusted_wind` and observations over that
field, but a point correction must never be spread into adjacent map pixels.

This makes field coverage the scalable default for Europe and later the world:
storage and transfer scale with model grid/timesteps, not with the number of
spots. Spot-specific coverage remains useful only for local correction,
observations, validation and the detailed spot UI.

## Contract

The executable schema is `app/spatial_fields/contracts_v2.py`. A publication is
valid only when it contains:

- immutable publication identity, provider, model, UTC run and valid times;
- explicit coverage and the reproducible native grid definition;
- separate native and display-resolution descriptions;
- paired eastward `wind_u` and northward `wind_v` in m/s;
- contract-global signed-int16 scale/offset/nodata definitions;
- tile schema, projection, dimensions, overlap, byte order and LOD;
- processing/quality/freshness state, attribution and asset-index checksum;
- a field URL template containing valid-time, z, x and y tokens.

`model_wind`, `spot_adjusted_wind` and `observed_wind` remain separate products.
Only `model_wind` belongs in these tiles.

## Experimental tile specification

| Property | Phase-0 value |
|---|---|
| Schema | `swd-field-tile-v2` |
| Coordinates | XYZ |
| Projection | EPSG:3857 |
| Raster | 128 × 128 cells plus a 1-cell overlap on every side |
| Variables | planar `wind_u`, then `wind_v` |
| Storage type | little-endian signed int16 |
| Physical value | `stored * 0.05 + 0.0` m/s |
| Nodata | `-32768` |
| Compression | deterministic gzip, level 9 |
| Integrity | SHA-256 per asset and for the asset index |
| Spatial interpolation | bilinear on u/v only |
| Temporal interpolation | linear on u/v only |
| Frozen LOD | source z4 for consumer zoom 0–5; source z5 for zoom 6–8 |

The binary tile starts with ASCII magic `SWF2`, a little-endian uint32 JSON
header length, canonical JSON metadata and the planar int16 arrays. The codec
rejects missing u/v pairs, shape differences, overflows, truncated payloads and
undeclared variables.

## Publication and serving boundary

The final data plane is immutable object storage/CDN:

```text
browser -> immutable manifest/index/tile assets
```

Normal tile retrieval must not pass through FastAPI or PostgreSQL. PostgreSQL
will become the Phase-1 control plane for runs, assets, QA events, active
publication pointers and rollback. A run becomes active only after every hard
gate passes; a failed run cannot change the active pointer.

No paid weather API, paid map tiles or paid geospatial service is introduced.
Phase 0 uses DWD Open Data, local processing and a browser canvas. Hosting and
egress still consume the project's existing infrastructure resources, so Phase
0B must set retention and transfer budgets before production rollout.

## Sampling rules

- Spatial and temporal interpolation always operate on u/v components.
- Direction and speed are derived after interpolation.
- All four spatial neighbours must be finite; otherwise the sample is absent.
- Calm wind has speed zero and no meaningful direction.
- Direction follows the meteorological “from” convention.
- UTC-aware, bracketed timestamps are mandatory for temporal interpolation.

## Phase-0 execution

```powershell
.venv\Scripts\python.exe scripts/weather_field_phase0_spike.py
.venv\Scripts\python.exe -m http.server 8765 `
  --directory data/weather-field-phase0/<publication-id>
```

Open `http://127.0.0.1:8765/viewer.html`. Generated GRIB-derived assets stay in
the ignored `data/weather-field-phase0/` directory and are never committed.

## Phase-0 measurements (2026-10-03, ICON-EU 12 UTC, f000)

| Measurement | Result |
|---|---:|
| Compressed U10 + V10 download | 2,271,053 bytes |
| Download | 0.485 s |
| Decode | 0.212 s |
| Tile processing | 0.360 s |
| End-to-end script | 1.061 s |
| Native grid | 1377 × 657 |
| Tiles | 20 |
| Compressed field payload | 434,141 bytes |
| GRIB/tile comparison | 12 centers, max component error 0.173 m/s |
| QA tolerance | 0.20 m/s, passed |
| Desktop Chromium | 60 FPS, 9.5 MB JS heap |
| Mobile viewport Chromium | 60 FPS, 9.5 MB JS heap |
| Browser tile network load | 424.0 KiB |
| GPU memory | unavailable through standard browser APIs |

The browser decoded the same u/v tiles for color, particle advection and cursor
sampling with no console/page errors. These numbers cover one valid time at one
LOD on a local connection; they are not yet production budgets.

## Phase-0B benchmark and frozen decisions

Three real forecast times (`f000`, `f003`, `f006`) were processed. Mean payload
per Europe timestep:

| Candidate | Mean payload | Relative | Max quantization error |
|---|---:|---:|---:|
| z4 / 128 / 0.01 m/s | 581,952 B | 100% | 0.005 m/s |
| z4 / 128 / 0.05 m/s | 433,565 B | 74.5% | 0.025 m/s |
| z4 / 256 / 0.01 m/s | 2,129,509 B | 365.9% | 0.005 m/s |
| z5 / 128 / 0.01 m/s | 1,994,133 B | 342.7% | 0.005 m/s |
| z5 / 128 / 0.05 m/s | 1,319,673 B | 226.8% | 0.025 m/s |

Frozen profile:

- 128 cells, one-cell overlap and contract-global 0.05 m/s quantization;
- deterministic gzip because it is natively decoded by the target browsers;
- z4 base LOD for overview zoom 0–5 and z5 only for detail zoom 6–8;
- `YYYYMMDDTHHZ` UTC path keys; timestamps in manifests remain ISO 8601 UTC;
- immutable tiles/index: `public, max-age=31536000, immutable`;
- immutable manifest by publication ID; active pointer: `no-cache` with ETag;
- SHA-256 for every tile and the canonical asset index;
- fresh through 9 h, delayed through 15 h, stale through 30 h, then expired;
- current run remains active until a complete replacement passes all gates.

The initial overview budget is 500 KiB per valid time for full-Europe z4. The
detail LOD is fetched only for the visible viewport and has a 1.5 MiB full-Europe
reference ceiling. Initial map loading must fetch one time only; adjacent times
are prefetched after interaction/idle, never as part of first paint.

Phase 1 can now implement the control plane, immutable storage abstraction,
publication state machine and rollback without changing the tile contract.

## Phase 1 implementation

Phase 1 is implemented as an isolated foundation. It does not register public
routes, mount the field directory, schedule downloads or replace the existing
spot forecast.

### PostgreSQL control plane

Migration `0072_weather_field_foundation` adds:

- `weather_field_models`: provider/model catalog, coverage, native-grid source,
  cadence, horizon, licence, attribution and explicit priority;
- `weather_field_runs`: immutable model-run identity and processing lifecycle;
- `weather_field_assets`: object keys, tile coordinates, byte sizes, hashes and
  verification state, never raster payloads;
- `weather_field_quality_events`: one current result per named gate with metrics;
- `weather_field_publications`: scope history, active generation and rollback
  provenance.

The database enforces one active publication per scope with a partial unique
index. Activation additionally takes a transaction-scoped advisory lock, so the
first publication and concurrent replacements are serialized. The previous
active row is flushed inactive before the replacement is promoted, while both
changes remain invisible until commit.

Run transitions are explicit:

```text
discovered -> downloading -> processing -> quality_pending -> ready
                                                    \-> rejected
any processing stage -> failed
ready -> expired
```

Stages cannot be skipped. Finalization requires verified assets, a verified
manifest and every hard gate. Publication repeats those checks under database
locks, preventing a run from being activated after its evidence changed.

Rollback creates a new publication generation pointing to a previously valid
run. It does not mutate or copy field assets. The bad current generation becomes
`rolled_back`, preserving the complete activation history.

### Model catalog

The free-data catalog currently contains:

- DWD ICON-D2: active Germany/regional primary, priority 5;
- DWD ICON-EU: active Europe primary, priority 10;
- NOAA GFS 0.25°: active global fallback, priority 20.

All entries explicitly set `blend=false`. Priority controls geographic coverage
selection, never numerical blending. Catalog synchronization updates descriptive
metadata but deliberately does not overwrite an operator's model status.

For requests with a map or spot coordinate, the API selects the smallest healthy
active coverage in priority order: ICON-D2, then ICON-EU, then GFS. `fresh` and
`delayed` publications win over stale or expired publications. If all covering
publications are degraded, the same geographic order is retained and the response
marks the selection as a fallback. A requested `model` remains a manual override;
only an unreadable or missing publication causes the API to fall through to the
next covering model. Selection is publication-based and never blends grids.

### Immutable storage

The Phase-1 backend is local/self-hosted only:

```text
WEATHER_FIELD_STORAGE_BACKEND=local
WEATHER_FIELD_STORAGE_DIR=data/weather-fields
WEATHER_FIELD_PUBLIC_BASE_URL=/weather-field-assets
```

Writes use a temporary file, `fsync` and an atomic hard-link publication. Writing
the same bytes to the same key is idempotent; different bytes at an existing key
raise an immutable-object conflict. Canonical POSIX key validation prevents path
traversal. A memory implementation supports deterministic pipeline tests.

This adds no paid storage or weather service. Remote object storage remains an
explicit future adapter rather than silently reusing the media/blob subsystem.

### Required hard gates

Activation requires successful evidence for:

1. paired u/v fields;
2. UTC and unique valid times;
3. declared coverage;
4. stable native-grid continuity;
5. physical value ranges;
6. asset/checksum integrity;
7. GRIB-to-tile comparison;
8. tile-border continuity;
9. processing-version provenance;
10. attribution;
11. complete configured near-term forecast horizon.

## Phase 2 implementation

Phase 2 connects the foundation to a bounded, durable ingestion pipeline while
leaving the existing Open-Meteo spot forecast unchanged. DWD ICON-D2, DWD
ICON-EU and NOAA GFS are active free-data adapters; fields are never blended.

The worker executes discovery, download and processing outside request paths:

```text
cron/admin enqueue -> durable job -> run discovery -> u10/v10/gust only
  -> decode and grid validation -> z4/z5 immutable tiles
  -> checksums and hard gates -> staged publication -> explicit activation
```

ICON-D2 and ICON-EU read the official DWD Open Data objects. GFS uses the
official NOAA NOMADS subset endpoint for the configured global coverage. All
adapters enforce per-object and per-run byte limits. The configured forecast
horizon is hourly through T+24, three-hourly through T+72 and six-hourly through
T+120 by default.

### Serving contract

- `GET /weather-fields/wind`: active atomic manifest pointer (15-second shared
  cache, `stale-while-revalidate`, ETag, and per-worker cold-read collapse);
- `GET /weather-fields/wind/sample`: bilinear spatial and linear u/v temporal
  sample from the exact active tile publication, never another provider;
- `GET /weather-fields/wind/health`: machine-readable freshness, quality,
  checksum, missing-tile, stalled-run and job state;
- `GET /weather-fields/waves`: automatically selects EWAM in Europe, GWAM
  globally, and NOAA GFS-Wave when `valid_at` lies in the ten-day tail
  for global fallback coverage;
- `GET /weather-fields/waves/health`: reports the EWAM, GWAM and GFS-Wave scopes
  independently so one healthy model cannot hide a stale or failed partner;
- `GET /weather-fields/wind/runs`: authenticated diagnostic alias when the admin
  API is enabled;
- `/weather-field-assets/*`: immutable direct file delivery with a one-year
  cache header; production Caddy reads the shared `weather_fields` volume
  directly, so large tile responses do not pass through FastAPI or nginx.

The administrative API under `/admin/weather-fields` exposes status, jobs,
runs and publication history. Discovery and retention can be enqueued there.
Reprocessing creates a new immutable processing version. Activation and rollback
require an explicit confirmation plus a recorded reason and actor.

### Safe rollout and operations

The three independent switches default to false:

```text
WEATHER_FIELD_PIPELINE_ENABLED=false
WEATHER_FIELD_PUBLIC_ENABLED=false
WEATHER_FIELD_AUTO_ACTIVATE=false
WAVE_FIELD_PUBLIC_ENABLED=false
```

The first switch permits cron/worker ingestion in shadow mode. The second makes
an already active publication discoverable to map clients. Automatic activation
is separately gated and is enabled only after the required consecutive shadow
cycles and resource budgets are configured for production. Failed or rejected
replacements never alter the active pointer. Retention always protects the
active run and its immediate predecessor, enabling constant-time rollback.

Run `python scripts/weather_field_worker.py` for one manual bounded batch or
`python scripts/weather_field_worker.py --loop` for the interruptible worker
loop. On the VPS, `maintenance-worker` enqueues discovery every three hours so
no ICON-D2 cycle or new DWD wave run is skipped. The same discovery cycle uses
the hourly EWAM profile through T+78, the three-hourly GWAM profile through
T+174 and the bounded three-hourly GFS-Wave tail from T+168 through T+240. A
separate health task checks wind, EWAM, GWAM and GFS-Wave every 15 minutes. The
separate `weather-field-worker` drains due jobs
without blocking observations, forecast refresh, tides or other maintenance
tasks. It waits 30 seconds only when no due job remains. The app, dedicated
worker and Caddy share the local `weather_fields` Docker volume; this adds no
paid service. Migration `0075_activate_d2_global_gfs` must be applied before
enabling all operational models.

## Phase 3 implementation

Phase 3 adds the Europe field client to the existing public `/map` route. The
route now has two deliberately separate modes:

- **Spots** keeps the established Leaflet explorer, marker clustering, live
  readings, spot forecast panel and spot navigation unchanged;
- **Wind** lazy-loads a MapLibre base map plus the weather-field renderer and
  exposes the active Phase-2 publication as a continuous Europe field.

The mode, camera, selected valid time, model, display style and optional spot
overlay are URL-addressable. A deep link can therefore restore a wind view,
while legacy map links still open the original Spot mode and are not forced to
download MapLibre.

The field client decodes the frozen `SWF2` gzip tiles in the browser. One shared
bounded tile source feeds all consumers: GPU color texture generation,
particles or reduced-motion arrows, and local interpolation. The point
inspector deliberately calls the Phase-2 `/sample` endpoint so the displayed
number follows the active-publication and temporal-interpolation rules of the
backend. Rapid tile and point requests are abortable; stale responses cannot
replace a newer interaction.

The interface includes:

- active model, run, provider and freshness state;
- discrete forecast timeline with play/pause;
- particle and arrow displays, with arrows forced for reduced motion;
- wind-speed legend and optional spot overlay;
- point inspector for wind, gust and valid time;
- retained-manifest offline handling plus loading, unavailable, expired and
  tile-error states;
- desktop controls and a mobile bottom-sheet inspector.

The hardened client distinguishes `fresh`, `delayed`, `stale`, `expired` and
offline states in words rather than color alone. It rejects incomplete runtime
manifests before constructing the renderer, retains an already loaded field
when the browser goes offline, and reloads the active pointer after reconnect.
Keyboard users can pan with the MapLibre controls and inspect the current map
centre with Enter or Space.

MapLibre and the Wind feature are separate lazy chunks. The established Spot
map remains about 23 kB minified (about 9 kB gzip). MapLibre is isolated into
cacheable vendor chunks below the repository's 1 MB raw-chunk budget; the Wind
feature itself is about 23 kB minified (about 9 kB gzip). Field network cost is
viewport-bounded and initially requests only the selected timestep and the LOD
defined by the frozen Phase-0B profile.

No Phase-3 database migration, write or new paid service is required. The old
spot forecast continues to use its existing data path; Phase 3 only consumes
the public field contract introduced by Phase 2.

## Phase 4 implementation

Phase 4 reuses the Phase-3 MapLibre field renderer inside the fullscreen map on
the spot data page. It does not create per-spot field tiles and it does not
replace the established forecast, LiveWind analysis or reference measurement.
The selected spot is rendered as a dedicated focus marker over the continuous
Europe field.

The shared `SpotDataScope` drives both the existing forecast timeline and the
field valid time. The nearest published field timestep is selected for the
currently chosen forecast hour. The spot coordinate is also sent to the field
API so the same automatic ICON-D2 → ICON-EU → GFS coverage selection used by
the landing-page map is applied. The overlay keeps the products visibly and
semantically separate:

- `Modellfeld`: bilinear u/v sample from the exact active field publication;
- `Spot-Prognose`, `Spotwind` or `Modell-Nowcast`: the existing point product;
- `Messung`: the existing reference station observation, when available.

The UI explicitly states that the model field is not a live measurement. If no
usable manifest exists, WebGL is unavailable, or the initial field tile load
fails, the previous Leaflet spot map remains visible with an explanatory status
message. A rapid time change uses a replacement abort signal; pending tile
promises from an aborted selection are not reused by the new selection.

No Phase-4 database migration is required. It consumes the active publication
and sample endpoint already implemented in Phase 2. This is intentionally the
same data plane as the landing-page Wind mode while the spot-page composition,
camera and product comparison remain separate.

The landing-page map starts in automatic model mode and keeps that mode out of
the URL. Panning across a coverage boundary re-resolves the active publication
without resetting the camera. Choosing a model in the selector writes an
explicit URL override; selecting automatic mode removes it again. The response
exposes the selection mode, reason, selected model and per-model coverage state
so the UI can distinguish automatic choice, manual override and fallback.

The pressure product derives 4 hPa isobars directly in the browser from the
decoded `pressure_msl` values already used by the colour layer. The contour
renderer respects no-data cells and the contract's one-cell tile overlap, uses
no second provider or request path, and is active only for the pressure layer.
Major 8 hPa lines receive sparse viewport-aware labels; wind particles or
arrows remain a separate overlay sourced from the paired u/v field.

## Phase 5 implementation

Phase 5 runs the established point forecast and the published field in parallel
without changing either product. It reuses active `ForecastSnapshot` rows as the
existing `spot_adjusted_wind` side and `sample_active_field` as the
`model_wind` side. Every sampled result is checked against the publication ID
frozen into the job, so an activation during processing cannot produce a mixed
evidence set.

Migration `0074_field_shadow_validation` adds three internal tables:

- `weather_field_shadow_runs` records the immutable publication, processing
  profile, limits, outcome and explicit `public_effect: none`;
- `weather_field_shadow_samples` records paired point values and deltas without
  modifying the source snapshot or field publication;
- `weather_field_shadow_metrics` stores deterministic aggregates by horizon,
  region, country, water type, direction sector and speed band.

The comparison uses the required forecast bands `T+0–6`, `T+6–24`, `T+24–48`
and `T+48–72`. Wind speed bias, MAE and RMSE, circular direction MAE and gust
errors describe `field minus existing spot forecast`. They are compatibility
and divergence evidence—not measurement accuracy and not a public confidence
score.

Pilot spots come from `config/weather-pilot-spots.json` and are bounded by
configuration. Validation jobs use the existing durable `WeatherFieldJob`
worker with hourly idempotency, bounded spots/samples and normal retry handling.
The weather-field maintenance cron queues validation only when
`WEATHER_FIELD_SHADOW_ENABLED=true`; the default remains disabled. A no-data
run is retained as `awaiting_forecast_snapshots` and may be retried in a later
hour for the same field publication.

The authenticated `/admin/weather-fields/shadow/*` endpoints expose status,
runs and metrics. The separate `/admin/weather-fields` view makes pilot limits,
evidence state and segment metrics visible and always labels cutover as not
authorized. No Phase-5 result can activate a field, replace a ForecastSnapshot,
change calibration or update a public cache.

The first local evidence run used the existing free Open-Meteo snapshot path
for Fehmarn Wulfener Hals, Valdevaqueros and Porto Pollo and compared it with
the active local ICON-EU generation 2. It produced 219 paired samples through
T+72. Overall field-minus-spot-forecast divergence was 0.871 m/s wind-speed MAE,
0.180 m/s wind-speed bias, 1.140 m/s RMSE, 21.57° circular direction MAE and
1.414 m/s gust MAE. The evidence state remains `collecting` and
`cutover_authorized` remains false: these figures measure product divergence,
not accuracy against observations.

## Local database catch-up and real pilot evidence

On 2026-10-04 the local PostgreSQL/PostGIS control plane was upgraded from
revision `0071` through `0073_weather_field_jobs`, seeded with the existing
development data and synchronized with the free model catalog. DWD ICON-EU is
active; NOAA GFS remains disabled.

A real ICON-EU `f000` ingestion exposed a border-continuity defect in the old
per-tile reprojection path. The quality gates rejected that immutable
`field-v2.0.0` run and left the publication pointer unchanged. Projection now
samples the regular ICON grid directly at deterministic XYZ cell centres using
vectorized bilinear u/v/gust interpolation. The processing version was advanced
to `field-v2.0.1`; the replacement pilot passed every hard gate and was
activated locally.

Measured evidence for that local replacement:

| Property | Result |
|---|---:|
| Valid times | 1 (`f000`) |
| Published assets | 2,810,970 bytes |
| Maximum adjacent-tile seam difference | 0.0 m/s |
| Maximum decoded GRIB/tile component difference | 0.000000446 m/s |
| Failed hard gates | 0 |

The rejected run remains in PostgreSQL as audit evidence. The active run is a
bounded local pilot and not a production Europe rollout.

### Full-horizon shadow evidence

The next local shadow candidate processed the complete configured ICON-EU
horizon with a distinct immutable identity,
`field-v2.0.1-h49-shadow`. Discovery jobs persist their processing version and
forecast-hour list, so a later configuration change cannot reinterpret a queued
job. Hourly discovery deduplication also includes this ingestion profile; a
one-timestep pilot therefore cannot suppress a full-horizon job in the same
scheduler bucket.

| Property | Result |
|---|---:|
| Forecast times | 49/49, T+0 through T+120 |
| Source download | 171,084,849 bytes |
| Field tiles | 3,724 |
| Published tile payload | 137,585,630 bytes |
| Processing wall time | approximately 107 seconds |
| Maximum decoded GRIB/tile component difference | 0.024997 m/s |
| Maximum adjacent-tile seam difference | 0.0 m/s |
| Passed hard gates | 11/11 |

Automatic activation stayed disabled. The full candidate is `ready` and its
publication is `staged`; the one-timestep pilot remains the active pointer.
Production activation still requires an explicit operator decision after
observing repeated scheduled shadow cycles, retention and VPS resource usage.

### Rollout readiness gate

Activation paths now evaluate a separate rollout gate after the immutable asset
and quality gates. A candidate must be the latest discovered model cycle and
must be preceded by three consecutive six-hour ICON-EU cycles inside a 30-hour
window. Every qualifying cycle must contain the complete configured forecast
horizon and stay within these default local budgets:

- no more than 256 MiB of source downloads;
- no more than 200 MiB of immutable field assets;
- no more than 300 seconds of processing time.

The admin status response exposes the candidate publication, qualified run IDs,
observed/required cycle counts, budgets and blocking reasons. Manual activation
returns a conflict while the gate is closed. Automatic activation leaves the
successfully processed publication staged and reports `activation_blockers`;
it does not turn a healthy processing job into a failed/retry run. Rollback is
deliberately exempt so an operator can restore a previously active generation
immediately.

Discovery probes both `f000` and the last configured forecast hour for every
required wind component. A newly announced provider cycle is therefore not
selected while its T+120 tail is still being uploaded. Provider-unavailable
processing retries are delayed by 30 minutes instead of immediately repeating
large downloads.

Historical validation uses:

```powershell
python scripts/weather_field_shadow_backfill.py `
  --model-run <UTC-cycle> `
  --processing-version <immutable-version>
```

The command refuses to run when automatic activation is enabled and only
enqueues the normal bounded worker pipeline. Backfills remain staged and carry
explicit source metadata.

Retention counts distinct model cycles rather than individual retry or
reprocessing rows. With the default retention of three, retries from one cycle
cannot evict an older cycle that is still required for `3/3` rollout evidence.
Monitoring similarly selects the staged publication with the newest model-run
timestamp, not merely the publication row created most recently. After a
generation is active, only staged publications from a newer model cycle are
reported as pending rollout candidates; retained older or same-cycle rows are
rollback and audit evidence.

### Local gated full-horizon activation

Three consecutive full-horizon cycles supplied the required local rollout
evidence. The 00 UTC cycle was reproduced through the explicit backfill path,
the 06 UTC cycle came from the scheduled shadow pipeline, and the 12 UTC cycle
was the immutable retry of a provider-incomplete first attempt.

| Model cycle | Processing identity | Download | Assets | Duration | Result |
|---|---|---:|---:|---:|---|
| 2026-10-04 00 UTC | `field-v2.0.1-h49-backfill` | 170,693,891 B | 137,384,124 B | 108 s | ready/staged |
| 2026-10-04 06 UTC | `field-v2.0.1-h49-shadow` | 171,084,849 B | 137,585,630 B | 107 s | ready/staged |
| 2026-10-04 12 UTC | `field-v2.0.1-retry-1` | 171,798,480 B | 137,391,490 B | 106 s | ready/active |

All three cycles contain 49 forecast times through T+120 and stayed within the
configured resource budgets. The activated 12 UTC candidate passed all 11 hard
quality gates, with a maximum decoded GRIB/tile component difference of
0.0249996476 m/s and an adjacent-tile seam maximum of 0.0 m/s.

The gated operator action activated publication
`2920fe13-0f7f-4287-939f-cb4aa77986c3` as local generation 2. The former
one-timestep publication remains retained as the immediate rollback target;
automatic activation remains disabled. This is local development activation,
not a production deployment.

Post-activation API verification covered the 49-time manifest, conditional
ETag request (`304`), immutable manifest and tile delivery, exact first/middle/
last samples, and a between-step `bilinear_uv+linear_uv` sample. Health reports
`ok`, the active field is fresh, all active assets are present, and there are no
open issues. No paid data or infrastructure service is involved.

### Phase 6 spot baseline activation

The spot publisher now has a fail-closed field-baseline adapter. It preserves
the existing `ForecastSnapshot` promotion and rollback transaction, applies the
existing reviewed spot physics to ICON-EU u/v samples, and records publication,
run, model and replaced horizon in the snapshot's internal lineage. Open-Meteo
continues to provide air, solar and marine values and remains the explicit tail
fallback beyond the field horizon during the transition.

Rollout is controlled by `WEATHER_FIELD_SPOT_ROLLOUT_STAGE` (`shadow`, `pilot`,
`regional`, `europe`). Pilot and regional stages additionally require an
explicit region-slug allow-list. Every spot remains on the legacy wind baseline
unless all of these gates pass independently:

- the active field is fresh;
- enough distinct full-field shadow cycles and paired spot samples exist;
- enough accepted operational observations match those immutable samples;
- field-versus-legacy divergence remains inside the configured limits;
- field-versus-observation speed, direction and gust error remain inside the
  configured limits; and
- field speed error does not regress materially against the legacy baseline.

The authenticated `GET /admin/weather-fields/spot-rollout/{spot_id}` endpoint
exposes the per-spot decision, blockers and evidence. With the default `shadow`
stage there is no public effect. The current local evidence has only one
successful comparison cycle and no operational observation matches, so Phase 6
is implemented but intentionally not activated.

An explicit `WEATHER_FIELD_SPOT_ALLOW_UNVERIFIED=true` operator override can
bypass the evidence gates for an early all-spot publication. It is recorded in
every snapshot decision and still refuses missing, stale or expired fields. On
2026-10-05 this override was deliberately enabled for the local Europe rollout;
all 11 published spots received a field-primary snapshot with 121 replaced wind
hours. Validation remains scheduled for the subsequent evidence phase.

### Operational publication and spot convergence

The dedicated weather-field worker discovers and processes new model cycles.
Complete wave runs pass the immutable asset and hard quality gates and may be
activated automatically. The forecast refresh worker fingerprints the active
EWAM/GWAM publication set; a changed set makes otherwise fresh public spot
snapshots due immediately and uses a publication-specific idempotency reason.
Every resulting snapshot records the active publication IDs, including points
where no usable wave hour exists, so the scheduler converges without a retry
loop.

`scripts/weather_field_doctor.py` combines field health, active-asset integrity,
failed/stalled jobs, spot publication convergence and local storage pressure.
The production weather-field worker uses the same doctor as its Docker health
check. Deployment and rollback commands are documented in
`docs/ops/weather-field-runbook.md`.
