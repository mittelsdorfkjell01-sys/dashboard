# Surfwinddate — Backend (Sprints 1–8)

Foundation for a watersport spot & trip-planning platform. Sprint 1 delivered the
runnable project skeleton: full database schema (Postgres + PostGIS), ORM models,
Pydantic schemas, a read-only FastAPI, and seedable example data. **Sprint 2**
adds the offline **ERA5 climatology pipeline** (see
[ERA5 climatology pipeline](#era5-climatology-pipeline-sprint-2)). **Sprint 3**
adds the runtime **Open-Meteo live + forecast path** (see
[Live + forecast](#live--forecast-sprint-3)). **Sprint 4** adds the **score engine**
(see [Score engine](#score-engine-sprint-4)). **Sprint 5** adds the **search core**
(see [Search](#search-sprint-5)). **Sprint 6** adds **open axes & reverse search**
(see [Open axes](#open-axes--reverse-search-sprint-6)). **Sprint 7** adds
**similarity search** (see [Similarity](#similarity-sprint-7)). **Sprint 8** adds
the **admin / data-maintenance** write workflow (see [Admin](#admin-sprint-8)).

> **Out of scope so far:** watches & notifications (Sprint 9). Admin
> authentication now exists (cookie sessions + roles, see
> [Admin auth & accounts](#admin-auth--accounts-sprint-a)); end-user accounts are
> still future work. The `watches` and `notifications` tables exist but are not yet
> populated or exposed. The climatology pipeline and the region-season aggregate
> are run **manually** (CLI/function); admin spot-creation triggers an ERA5 job but
> climatology still derives offline. The live path returns **raw values only** —
> the score engine layers on top of it and the climatology, but the two data paths
> are never blended across the 10-day forecast horizon.

## Stack

Python 3.12 (tested on 3.11) · FastAPI · SQLAlchemy 2.x · Alembic ·
PostgreSQL + PostGIS · Redis · pytest.

## Project layout

```
app/
  config.py            # env-based settings (pydantic-settings)
  db/                  # Base, engine/session
  models/              # SQLAlchemy models (8 tables)
  schemas/             # Pydantic read schemas (+ geo helpers)
  services/overrides.py# apply_overrides() read-overlay helper
  admin/constants.py   # single source of truth for the category enums
  media/               # hero-image validation + on-disk storage (Sprint: upload)
  api/                 # FastAPI routers: spots, regions, search, admin
  seed/                # seed data + `python -m app.seed.seed`
  main.py              # FastAPI app (+ CORS + /media StaticFiles)
alembic/               # migration env + versions/ (0001 … 0003_spot_categories)
tests/                 # migration / seed / API / geo / categories / upload tests
frontend/              # React + Vite + Tailwind SPA (wired to the API)
docker-compose.yml     # postgis + redis
scripts/init-test-db.sql
```

## Setup

1. **Start infrastructure** (Postgres+PostGIS on 5432, Redis on 6379). The DB
   container also auto-creates the `surfwind_test` database used by the tests:

   ```bash
   docker compose up -d
   ```

2. **Create a virtualenv and install dependencies:**

   ```bash
   python -m venv .venv
   .venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
   # source .venv/bin/activate && pip install -r requirements.txt # macOS/Linux
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env
   ```

   | Variable            | Default                                                        |
   | ------------------- | -------------------------------------------------------------- |
   | `DATABASE_URL`      | `postgresql+psycopg://surf:surf@localhost:5432/surfwind`       |
   | `TEST_DATABASE_URL` | `postgresql+psycopg://surf:surf@localhost:5432/surfwind_test`  |
   | `REDIS_URL`         | `redis://localhost:6379/0`                                     |
   | `CORS_ORIGINS`      | `http://localhost:5173` (comma-separated or JSON array)        |
   | `MEDIA_DIR`         | `data/media` (uploaded hero images on disk)                    |
   | `MEDIA_URL_PREFIX`  | `/media` (StaticFiles mount serving `MEDIA_DIR`)               |

4. **Run the migration** (creates PostGIS + all tables/indexes):

   ```bash
   alembic upgrade head
   ```

## Seed

The **core** catalogue (`app/seed/data.py`) is 3 regions (Tarifa, Sardinia, Kieler
Bucht) and 11 **published** spots with coordinates, sports, and — where genuinely
known — the category axes (`water_character`, `style`) and `facilities` (e.g. Laboe,
Porto Pollo, Fehmarn). This is what the tests seed.

The seed **CLI** additionally loads a researched **European draft batch**
(`app/seed/data_europe.py`): 25 more regions and 40 more spots (20 wind + 20 wave —
Canaries, Aegean, Portugal, N-Spain, France, Ireland, UK). These are all
`status="draft"`, so they are **not public** (the frontend shows only `published`)
until a curator reviews and publishes them (readiness also needs a derived
climatology + credited image). Their `usable_wind_directions` are authored as
8-point compass letters and normalised to 45°, wrap-aware `{min,max}` windows so the
scoring/similarity engine consumes them natively.

Idempotent — safe to re-run (existing slugs are skipped; note it does **not**
back-fill new columns onto rows that already exist, so drop/re-seed a dev DB to pick
up added fields):

```bash
python -m app.seed.seed          # core + European draft batch (28 regions, 51 spots)
```

`seed(db)` called directly (e.g. in tests) loads the core only; pass
`seed(db, include_europe=True)` for the full batch.

## Run the API

```bash
uvicorn app.main:app --reload
```

Read-only endpoints (interactive docs at `/docs`):

| Method & path        | Description                                              |
| -------------------- | ------------------------------------------------------- |
| `GET /spots`              | List spots; filters: `region_id`, `status`, `sport`, `level`, `water_character`, `style` (multi) |
| `GET /spots/{id}`         | Single spot (404 if unknown)                            |
| `GET /spots/{id}/live`    | Current conditions (Open-Meteo, cached) — Sprint 3      |
| `GET /spots/{id}/forecast`| Surfwinddata 10-day forecast; days 1–5 hourly, days 6–10 trend |
| `GET /spots/{id}/badge`   | Now-badge: gut/mäßig/nein for current conditions — Sprint 4 |
| `GET /spots/{id}/season`  | Seasonal curve; `stage=1` descriptive, `stage=2` scored — Sprint 4 |
| `GET /spots/{id}/similar` | Similar spots; `mode=charakter\|saison\|beides` — Sprint 7 |
| `GET /spots/{id}/alternatives`| Character-similar spots running now, ranked — Sprint 7 |
| `GET /search`             | Text/geocode search → ranked spots/regions — Sprint 5   |
| `POST /search/geometry`   | Spots inside a drawn circle/rectangle — Sprint 5        |
| `GET /map`                | Pins for a bbox viewport, coloured by value — Sprint 5  |
| `GET /portfolio`          | Per-region (or global) pin-maps — Sprint 5              |
| `GET /search/best-spots`  | Best spots over a time window (region or open catalogue) — Sprint 6 |
| `GET /search/best-regions`| Rank regions over a time window — Sprint 6              |
| `GET /areas/best-weeks`   | Open time: best weeks for an area — Sprint 6            |
| `GET /regions`            | List regions                                            |
| `GET /regions/{id}`       | Single region (404 if unknown)                          |
| `GET /regions/{id}/season`| Region season aggregate (52 weeks) — Sprint 6          |
| `POST /admin/spots` · `PATCH /admin/spots/{id}` | Create draft / update editorial + categories + facilities |
| `POST /admin/spots/{id}/override` · `/revert`   | Pin / unpin an auto value (provenance + audit) — Sprint 8 |
| `POST /admin/spots/{id}/image` (url) · `/image/upload` (file) | Set image by URL / upload a validated hero image |
| `POST /admin/spots/{id}/live` · `GET …/readiness` | Publish (409 with gaps until ready) / readiness checklist |
| `POST /admin/regions` · `…/{id}/defaults` · `…/{id}/stock-image` | Region CRUD + stock image — Sprint 8 |
| `GET /health`             | Liveness probe                                          |

Geography columns are serialized as `{"lon": .., "lat": ..}` (points) and
`{"rings": [[[lon, lat], ...]]}` (polygons).

## ERA5 climatology pipeline (Sprint 2)

An **offline batch** that turns a 20-year ERA5 hourly reanalysis into a
pre-computed, per-week seasonal climatology stored in `spots.climatology`.
Nothing here runs at request time. The code lives in [`app/era5/`](app/era5/):

| Function (`app.era5.*`)                | Stage                                              |
| -------------------------------------- | -------------------------------------------------- |
| `grid.resolve_grid_cell(lat, lon)`     | nearest ERA5 cell(s) — 0.25° wind/temp, 0.50° wave |
| `cds.request_era5_extract(...)`        | build CDS request, create `Era5Job` (`queued`)     |
| `cds.poll_cds_job(cds_request_id, ...)`| download raw extract → Parquet, job `extracting`   |
| `components.compute_wind_components`    | speed (kt) + 16-sector direction (0 = N)           |
| `solar.filter_daylight(series, lat, lon)`| keep only daytime hours (solar elevation > 0)    |
| `aggregate.aggregate_weekly_histogram`  | `wind_joint[16][6]` & `swell_joint[16][6]` / week  |
| `aggregate.derive_display_stats`        | wind p10/p50/p90, dominant dir, swell, air/sst p50 |
| `pipeline.build_climatology_record`     | write `spots.climatology` (52 weeks), job `derived`|
| `pipeline.recompute_climatology`        | re-derive from the raw file, **no CDS call**       |

### Job lifecycle

`era5_jobs.status` moves `queued → extracting → derived`, or `failed` on error.
Each job records its `cds_request_id` (in `params`), the request window, and the
`raw_path` of the downloaded extract. Submission is **idempotent per spot**: a
non-failed job is reused rather than resubmitted.

### Klimatologie-Datenquelle (Open-Meteo Historical)

The default extraction path is **Open-Meteo Historical**, not CDS — plain HTTP GET
JSON, no auth, no `~/.cdsapirc`, licence **CC BY 4.0** (`app/era5/openmeteo.py`,
injected via `app/admin/deps.py::get_extract_client`). Only the *data source*
changed; the histogram/score/overlay logic is untouched.

| Achse | Quelle | Zeitraum | Auflösung |
| ----- | ------ | -------- | --------- |
| **Wind / Temp** | Historical Weather API (ERA5), `archive-api.open-meteo.com` | ~20 Jahre (Default 2006–2025) | stündlich, 0.25° |
| **Wellen** | Marine API (Wellenmodell), `marine-api.open-meteo.com` | **nur ab ~2022** (geringere Tiefe) | stündlich |

- **Wind** kommt tief und lückenlos aus ERA5. `wind_speed_10m` (in m/s) +
  `wind_direction_10m` werden in die ERA5-`u/v`-Komponenten umgerechnet, die die
  Pipeline erwartet; `temperature_2m` (°C → Kelvin).
- **Wellen** haben bei Open-Meteo nur kurze Historie (belegt in
  [`Konzept und Prompts/wellen_datenquelle_pruefung.md`](Konzept%20und%20Prompts/wellen_datenquelle_pruefung.md)):
  archive-api liefert für Wellen nur `null`, die Marine API echte Werte erst ab
  ~2022. Gewählt wurde **Option (b)** — Wellen über den kürzeren verfügbaren
  Zeitraum, im Record **klar markiert** (`wave_source`, `wave_window`, `wave_note`).
  Wind- und Wellenachse teilen eine Zeitachse; die `_swell_joint`-Logik filtert
  ohnehin auf `isfinite`, sodass Wellen-Stunden vor ~2022 automatisch entfallen.
  **Kein CDS-Fallback nötig.**
- **Glättung:** die 52-Wochen-Kurve wird mit einem rollierenden Fenster
  (`CLIMATOLOGY_SMOOTH_WEEKS`, Default 3, **wrap-around** 52↔1) geglättet — die
  geglätteten `weeks` sind Anzeige-/Score-Kurve, die Rohkurve bleibt unter
  `weeks_raw` erhalten.
- **Roh-Cache:** gezogene Reihen liegen als Parquet unter `ERA5_RAW_DIR/omcache/`
  (Key = Zelle + Zeitraum). Ein erneuter Lauf zieht **nicht** erneut über das Netz.
- **Attribution (fürs UI):** „Wetterdaten von Open-Meteo.com, CC BY 4.0".
- **Overrides** bleiben unberührt: `recompute_climatology` schreibt nur
  `spots.climatology`, nie `spots.overrides`.

```bash
python -m app.era5.cli request tarifa-los-lances   # Open-Meteo, kein Login nötig
python -m app.era5.cli poll <request_id>           # zieht + cached die Reihe
python -m app.era5.cli build tarifa-los-lances      # 52-Wochen-Klimatologie
```

### CDS setup (optional fallback — not the default path)

The Copernicus CDS adapter (`app/era5/_real_cds.py`) stays available but is
**optional** and off the default path (opt in with `... cli request <spot> --cds`).
It needs `pip install cdsapi xarray netCDF4` and a `~/.cdsapirc`:

1. Create a free account at <https://cds.climate.copernicus.eu/> and accept the
   ERA5 licence.
2. Put your key in `~/.cdsapirc`:

   ```
   url: https://cds.climate.copernicus.eu/api
   key: <UID>:<API-KEY>
   ```

3. Parsing the downloaded NetCDF additionally needs `xarray` + `netCDF4`
   (optional, not pinned in `requirements.txt`).

> Tests never touch the network — they inject a fake CDS client (see
> `tests/era5_helpers.py`), so neither a CDS account nor `xarray` is needed to
> run `pytest`.

### Running the pipeline for a spot

```bash
# 1. submit a 20-year extract (window = last 20 full years, e.g. 2006–2025)
python -m app.era5.cli request tarifa-los-lances

# 2. poll until the raw Parquet lands, then derive the climatology
python -m app.era5.cli poll <cds_request_id>
python -m app.era5.cli build tarifa-los-lances

# 3. later, re-derive from the stored raw file without re-querying CDS
python -m app.era5.cli recompute tarifa-los-lances --dump
```

### Bulk: all spots at once (`app.era5.batch`)

The per-spot commands above are fine for one spot; to populate the whole
catalogue use the **batch orchestrator**, which chains `request → poll → build`
over a selection of spots. It only *orchestrates* the tested per-spot functions —
it never re-implements the derivation and never touches `spots.overrides`.

```bash
python -m app.era5.batch                       # all spots, skip those already done
python -m app.era5.batch --status published     # only the live catalogue
python -m app.era5.batch --region sardinia      # one region (repeatable)
python -m app.era5.batch --slug tarifa-los-lances --force   # recompute one
python -m app.era5.batch --dry-run              # list compute/skip, no network
# equivalently: python -m app.era5.cli batch ...
```

- **Idempotent** — spots that already carry climatology are skipped; `--force`
  recomputes and, when a cached raw Parquet exists, does so **without any network
  fetch** (`recompute_climatology`).
- **Net-resilient** — retries with backoff on transient HTTP errors (429/5xx/
  timeouts, `--retries`), a `--sleep` pause between spots, and per-spot isolation:
  one failing spot is logged and marked `failed`, the batch continues.
- **Reportable** — one `ok`/`skip`/`fail` line per spot plus a summary; the process
  exits non-zero if any spot failed (for automation). Wave-history markers
  (`wave_source`/`wave_window`/`wave_note`) are carried through unchanged.
- **Needs outbound access** to `archive-api.open-meteo.com` (wind/temp) and
  `marine-api.open-meteo.com` (waves). Run it where those are reachable (e.g. the
  VPS). Verify the result with `python -m scripts.verify_content`.

### Where the raw data lives

Downloaded extracts are written as Parquet under `ERA5_RAW_DIR`
(default `data/era5_raw/`, configurable in `.env`), one file per job; the path is
recorded in `era5_jobs.raw_path`. Parquet is used instead of NetCDF for the
on-disk raw format because it is a single light dependency (`pyarrow`),
cross-platform, and round-trips exactly what `recompute_climatology` needs.

### Climatology shape & binning assumptions

`spots.climatology` is `{source, window, generated_at, weeks: [...52]}`. Each week
carries `daylight_hours`, a `wind`/`swell` block (percentiles, dominant 16-point
direction, and the `joint[16][6]` histogram) plus `air_p50_c` / `sst_p50_c`.

The exact histogram bins reference an external "Score-Parameter-Doc" that is not
in the repo; the edges in [`app/era5/bins.py`](app/era5/bins.py) are a documented,
reasonable interpretation and can be refined later without changing the pipeline:

- **Wind speed (kt), 6 bins:** lower edges `0, 6, 10, 14, 18, 25` (last open-ended).
- **Swell height (m), 6 bins:** lower edges `0, 0.5, 1, 1.5, 2, 3` (last open-ended).
- **Direction:** 16 compass sectors of 22.5°, sector 0 centred on North.
- **Long-period swell:** mean wave period ≥ 10 s.
- Daylight = solar elevation above the geometric horizon (NOAA solar position).

`overrides` are never written by the pipeline; `apply_overrides()` continues to
overlay editor-pinned values on top of the freshly derived climatology.

## Live + forecast (Sprint 3)

The **runtime** path: current conditions and a 10-day forecast from
[Open-Meteo](https://open-meteo.com/), cached in Redis. It is **strictly
separate** from the ERA5 climatology — nothing is merged across the two and
nothing beyond the 10-day horizon is ever returned. **Live data is never
persisted to Postgres** (cache only). Code lives in [`app/live/`](app/live/):

| Function (`app.live.*`)                  | Responsibility                                   |
| ---------------------------------------- | ------------------------------------------------ |
| `models.select_model(lat, lon, pref)`    | pick primary/home model; `spots.model_pref` wins |
| `models.consensus_models(lat, lon, pref)`| the primary + independent globals fetched together |
| `consensus.spread / confidence_from_spread` | median/min/max band + spread→confidence tier |
| `client.HttpOpenMeteoClient`             | `fetch_forecast` (multi-model) / `fetch_marine` (httpx) |
| `cache.cache_get/cache_set`              | Redis JSON cache, keyed + TTL'd                  |
| `service.get_live_conditions(spot_id)`   | current consensus `{wind,gust,…}` + `wind_spread`/`gust_spread` |
| `service.get_forecast_series(spot_id)`   | 10 days; days 1–5 hourly, days 6–10 trend + confidence |

### Model selection

`select_model` returns `spots.model_pref` when set, otherwise the most specific
regional model covering the spot, falling back to Open-Meteo's `best_match`:

| Model                         | Domain (approx.)                    |
| ----------------------------- | ----------------------------------- |
| `meteofrance_arome_france_hd` | France & coasts (41–51.5 N, −5.5–9.5 E) |
| `icon_d2`                     | Central Europe (43.2–58.1 N, −3.9–20.3 E) |
| `icon_eu`                     | Wider Europe nest (29.5–70.5 N, −23.5–62.5 E) |
| `best_match`                  | everywhere else (global blend)      |

### Cache keys & TTL

Keys are `om:{model}:{lat_r}:{lon_r}:{var}` with coordinates rounded to 2 decimals
(~1 km, so nearby spots share entries). The atmospheric forecast uses the chosen
model with `var=forecast`; the marine payload is model-independent and uses
`om:marine:{lat_r}:{lon_r}:marine`. Values are JSON; TTL is `LIVE_CACHE_TTL`
(default **1800 s / 30 min**, within the 30–60 min band). The cached fetch always
pulls the full 10-day horizon once, so `/live` and `/forecast` share one entry per
(model, location) — a second call within the TTL makes **no** HTTP request.

### Confidence staffing

Each forecast day carries a confidence tier derived from **model disagreement**
(see the consensus band below): tight agreement → `hoch`, wide spread → `niedrig`.
Because model spread naturally widens with the horizon this trends downward on its
own; the old calendar rule (days 1–3 `hoch` / 4–5 `mittel` / 6–7 `niedrig`) remains
only as a graceful fallback for days with fewer than two models reporting. The
horizon is hard-capped at 10 days even if more were requested or returned.

### Model consensus & uncertainty band (Sprint 18, Phase 1)

Instead of one model, the forecast fetches several independent systems in a
**single** request — the spot's regional/home pick plus the global trio
`icon_seamless` / `gfs_seamless` / `ecmwf_ifs025` (`consensus_models`; overridable
via `LIVE_CONSENSUS_MODELS`). Per timestep we report the **consensus** (median
across models) as the headline `wind`/`gust`, plus a **spread band**
(`wind_spread`/`gust_spread` = `{low, high, median, n}`, min/max across models) as
honest, data-driven uncertainty — the model disagreement no consumer tool shows.

- One request per location covers every model → **no extra cost** (larger payload
  only). Multi-model responses are cached under `var=forecast_multi`.
- `n` is how many models reported; when a spot/timestep has only one model with
  data the band collapses to that value and confidence falls back to the calendar
  rule — **no spot ever falls out** (graceful degradation).
- Direction/air come from the primary model; waves stay single-source (the Marine
  API is not multi-model). Runtime-derived + cached only — no schema/DB changes.

> Phase 2 (per-spot bias correction against observations) and Phase 3 (crowd
> reports) are deliberately deferred — they need observation/traffic data.

> Scoring/badges live in the score engine (Sprint 4), which consumes this path —
> the live endpoints themselves return raw values only.

## Score engine (Sprint 4)

The central, rule-based evaluation that badge, season curve and rankings depend
on. It produces a **categorical** rating — `gut` / `mäßig` / `nein` — and runs the
**same** logic live and over the climatology. Code in [`app/scoring/`](app/scoring/):

| Function (`app.scoring.*`)              | Responsibility                                  |
| --------------------------------------- | ----------------------------------------------- |
| `evaluate_conditions(values, …)`        | core: `{rating, reasons}` for one value set     |
| `apply_gates(values, editorial, sport)` | hard pass/fail gates (a fail = simply `nein`)   |
| `grade_magnitude(values, …)`            | `gut` vs `mäßig` (+ gust downgrade, level offsets) |
| `profile_thresholds(level, sport)`      | per-level ideal-band offsets                    |
| `score_live(spot_id, profile)`          | now-badge via the Sprint 3 live cache           |
| `score_climatology_week(spot_id, week, …)` | usable-hours share of a week's histogram     |
| `score_climatology_curve(spot_id, …)`   | `pct_usable[52]` + flagged good weeks           |
| `describe_week(spot_id, week)`          | Stage-1 description (no gates)                   |
| `spot_confidence(spot_id, sport)`       | `hoch` / `mittel` / `niedrig`                    |

### Parameter layers

A rating is shaped by three layers, most specific last:

1. **`scoring_params` (global, versioned).** Bins, gates, ideal bands, level
   offsets, `week_good_threshold = 0.40`, distance `d0 = 40`. One active row per
   sport, defined in [`app/scoring/params.py`](app/scoring/params.py) as
   `SCORING_PARAMS_V1`. The exact numbers reference the external
   "Score-Parameter-Doc" (not in the repo) and are a documented interpretation.
2. **Spot `editorial`.** Per-spot overrides: usable wind/swell direction windows,
   tide dependence, `facing` (onshore gate), `confidence_override`, `wind_type`.
3. **Rider `profile`.** The rider `level` (beginner → pro) shifts only the *ideal*
   band, so the same conditions can read `gut` for a beginner and `mäßig` for a pro
   (and vice-versa) while the hard gates stay identical.

### Gates (a failed gate = `nein`, no hazard text)

- **Wind (kite/wind/wing):** daylight, wind direction ∈ usable, strength ∈ `[min, max]`.
- **Surf:** swell direction ∈ window, height ∈ `[min, max]`, period ≥ `period_min`,
  tide ∈ window (if tide-dependent), and no strong onshore wind.

`grade_magnitude` then downgrades a wind `gut` to `mäßig` when `gust/mean ≥ 1.4`
or `gust − mean ≥ 8 kt`.

### Live ↔ climatology consistency

A climatology week is scored by running `evaluate_conditions` over **every cell**
of the week's `joint[16][6]` histogram (direction × magnitude), weighting by the
cell's hour count. `pct_usable` = passing hours / daylight hours, `gut_anteil` =
good hours / hours — the *same* gates/grading used for the live badge, so seasonal
and now ratings can't drift apart.

### Versioning `scoring_params`

`scoring_params` rows are keyed `(sport, version)` with one `active` row per sport.
To revise the model, add `SCORING_PARAMS_V2` and insert rows with `version = 2`
(flip `active`); pre-computed climatology scores carry a `scoring_params_version`
tag so stale results are detectable. `seed_scoring_params(db)` (run as part of
`python -m app.seed.seed`) upserts the v1 active rows. The search ranking score
(`app/scoring` `SeasonalRuleScorer`, the default `Scorer`) is derived from the same
engine — `0.6·gut_anteil + 0.4·pct_usable` for the relevant week.

## Search (Sprint 5)

The search core resolves a query to ranked spots/regions and powers the map.
Code lives in [`app/search/`](app/search/):

| Function (`app.search.*`)               | Responsibility                                       |
| --------------------------------------- | ---------------------------------------------------- |
| `text.search_entities(query)`           | own full-text index over spots+regions (name/country/aliases) |
| `geocode.classify_geocode(query)`       | Open-Meteo geocoding → `{type: point\|area, point, bounds}` |
| `spatial.search_nearby_spots(point, …)` | `ST_DWithin`, adaptive radius (start 25 km, doubles) |
| `spatial.search_by_geometry(shape, …)`  | circle → `ST_DWithin`, rectangle → `ST_Within`       |
| `ranking.rank_nearby(items, …)`         | `score × exp(−d/d0)`, `d0` per sport from `scoring_params` |
| `service.search(query, …)`              | orchestration (see below)                            |
| `service.query_map` / `query_portfolio` | viewport pins / per-region map portfolio             |
| `pins.cluster_pins` / `toggle_sport`    | grid clustering at low zoom / sport re-query         |

### Search flow

1. **Entity index first.** `search_entities` matches the query (accent-folded,
   case-insensitive) against spot/region names, country and aliases (aliases in a
   JSONB `aliases` list — `editorial.aliases` on spots, `defaults.aliases` on
   regions), grouped into `regionen` / `spots`.
2. If there is an entity hit, the best match anchors a **nearby search** and the
   results are ranked — so `?q=Laboe` returns **Laboe + Stein + the surrounding
   spots, score-ranked with distance damping**.
3. **Otherwise geocode.** `classify_geocode` resolves the query to a **point**
   (a town/place → adaptive-radius `ST_DWithin`) or an **area** (country / island
   / admin region → query its **bounds** via `ST_Within`, *not* a radius around
   the centre). A geocoded place is **never** returned as a result itself — it
   only drives the spatial query.

The response is `{regionen, spots, treffer}` (`treffer` = total result count),
plus a `resolved` marker (`entities` / `point` / `area` / `none`).

### Point vs. area

| Input            | Resolver        | Spatial query                         |
| ---------------- | --------------- | ------------------------------------- |
| spot/region name | entity index    | nearby around the match, ranked       |
| town / place     | geocode `point` | `ST_DWithin`, adaptive radius (25 km→) |
| country / island | geocode `area`  | `ST_Within` over the geocoded bounds  |
| drawn circle     | geometry        | `ST_DWithin`                          |
| drawn rectangle  | geometry        | `ST_Within` (envelope)                |

### Ranking & sport toggle

`rank_nearby` multiplies each spot's score by a distance-decay `exp(−d/d0)`, where
`d0` (km) comes from the active `scoring_params` row for the sport (else a per-sport
default). A clearly better but somewhat farther spot can therefore outrank a
mediocre near one. The selected sport is threaded into the scorer (via
`profile.sport`), so each spot is scored/coloured for *that* sport rather than its
first-listed one. Switching sport (`toggle_sport`) re-runs the query with the new
`sports[]` filter and re-ranks/re-colours — e.g. flatwater-only spots drop in a
wave sport, and the survivors are re-scored for the wave sport.

### Scoring seam

Ranking needs a continuous 0–1 score per spot. Search ranks against the `Scorer`
seam in [`app/scoring/`](app/scoring/); the default is now `SeasonalRuleScorer`,
backed by the **Sprint 4 score engine** (`0.6·gut_anteil + 0.4·pct_usable` for the
relevant week), with `InterimScorer` kept as a lightweight fallback when a spot has
no climatology. The scorer is **injectable** — endpoints resolve it via
`app/search/deps.py` and tests pass a deterministic fake.

The seed adds a Baltic **Kieler Bucht** region with clustered spots (Laboe, Stein,
Schilksee, Heidkate, Fehmarn) so the Laboe scenario, nearby ranking and the
sport toggle can be exercised against real PostGIS.

## Open axes & reverse search (Sprint 6)

Sprint 5 finds spots in space at the *current* time. Sprint 6 lets **both axes be
open** — "place given → time wanted" and "time given → place wanted" — and adds the
region level. Code in [`app/search/timewindow.py`](app/search/timewindow.py) and
[`app/scoring/region.py`](app/scoring/region.py):

| Function                                   | Responsibility                                  |
| ------------------------------------------ | ----------------------------------------------- |
| `resolve_time_window(lens, range_input)`   | season (weeks/months) or current (days ≤ 7); `open` allowed |
| `rank_by_timewindow(cands, window, …)`     | **coverage**-first, **intensity** tie-break     |
| `best_weeks_for_area(spots, …)`            | open *time*: rank the 52 weeks for an area      |
| `aggregate_region_season(region_id)`       | persist `regions.season[52]` (counts, not means) |
| `best_regions_for_window(window, …)`       | rank regions over a window                       |
| `best_spots_in_region` / `…_open_place`    | region zoom / whole-catalogue ranking            |
| `region_when_to_go(region_id, …)`          | smoothed 52-week region curve                    |

### Coverage vs. intensity

Ranking over a window is deliberately **not** a plain average. The primary key is
**coverage** — the share of the window's weeks in which a candidate is good
(`pct_usable_hours ≥ week_good_threshold`, 0.40). Ties break on **intensity** — the
mean `pct_usable` over the window. So a spot that is *reliably* good across many
weeks outranks one that is spectacular in a single week but quiet otherwise.

### Open place / open time / both

- **Open place** (`GET /search/best-spots` without `region_id`) ranks the whole
  catalogue. The v1 catalogue scope **is** Europe, so "best spots in June" and "best
  spots in June in Europe" are identical.
- **Open time** (`GET /areas/best-weeks`, or any window without month/weeks) ranks
  the 52 weeks for the area; for a single spot this reduces to its own season curve.
- **Both open** → the travel default: rank regions over the season
  (`GET /search/best-regions` with no window).

### Region aggregate (count, don't average)

`regions.season` stores, per week, `spots_working` (**how many** spots are good that
week — a *count*) plus median `wind_p50` / `sst_p50` / `air_p50`. Counting matters:
a week where a single strong spot fires still ranks, instead of being washed out by
the region's quiet spots. The aggregate is run manually:

```bash
python -m app.scoring.region        # (re)aggregate every region's season
```

`GET /regions/{id}/season` returns it (computing on demand if missing); add
`?smooth=true` for the smoothed when-to-go curve. Time windows are expressed via
`?month=7` or `?weeks=23-30`; omitting both means the open axis (all 52 weeks).

## Similarity (Sprint 7)

"More like this", in two deliberately separate dimensions, plus the practical
alternatives case. Code in [`app/similarity/`](app/similarity/):

| Function (`app.similarity.*`)               | Responsibility                              |
| ------------------------------------------- | ------------------------------------------- |
| `orientation.normalize_orientation(sectors, facing)` | wind sectors → onshore/side/offshore pattern relative to the coast |
| `character.character_distance(a, b)`        | feel: water/bottom/level/wind-range/orientation |
| `season.season_distance(curve_a, curve_b)`  | correlation of the 52-week curves           |
| `service.find_similar_spots(id, mode, …)`   | `charakter` / `saison` / `beides`           |
| `service.find_alternatives(id, time_context, …)` | character-similar spots running *now*  |

### Orientation normalisation (why mirrored coasts match)

Comparing *absolute* compass directions would call a west-facing and an
east-facing beach different even when they fish the same wind. So
`normalize_orientation` expresses each usable wind sector **relative to the spot's
`facing`** and folds left/right, yielding a distribution over
`onshore / side_onshore / cross / side_offshore / offshore`. A west-facing spot
working N–NE wind and its mirror — an east-facing spot working S–SW wind — produce
the **identical** pattern, so character similarity recognises them as the same.

### The three modes

- **`charakter`** — a weighted distance over `editorial`/structural features:
  water type, bottom type, rider level, the numeric wind range, and the
  orientation pattern. Missing features are skipped and the remaining weights
  re-normalised.
- **`saison`** — `(1 − pearson) / 2` of the two spots' 52-week usable-hours curves.
  High correlation ⇒ same season ⇒ near 0; anti-correlation ⇒ opposite seasons ⇒
  near 1; a flat (no-variance) curve is neutral (0.5).
- **`beides`** — the mean of the two distances.

### Alternatives

`find_alternatives` takes the character-similar pool, keeps only spots that are
**running in the chosen time window** (`pct_usable ≥ week_good_threshold` for that
week), and ranks them with the Sprint 5 `score × exp(−d/d0)` logic — i.e. *what
else is firing right now that feels like here*.

### Stage dependency

Character similarity reads **maintained `editorial`/`facing`** (a Stage-2 concern):
`usable_wind_directions` (→ orientation), `wind_range`, plus the structural columns.
The seed's Baltic spots are filled accordingly. A spot without these still compares
on whatever it has (orientation simply drops out); season similarity needs only the
climatology curves.

## Admin (Sprint 8)

The write workflow for curators — create spots/regions, maintain editorial text,
override auto-computed values **with provenance**, manage image rights and publish
a spot only once it is complete. Pure API/logic, no UI. Code in
[`app/admin/`](app/admin/); endpoints under `/admin` (see the API table). Since
**Sprint A** every `/admin/*` route requires a logged-in admin/curator session
(cookie) — see [Admin auth & accounts](#admin-auth--accounts-sprint-a) below.

| Function (`app.admin.*`)                  | Responsibility                              |
| ----------------------------------------- | ------------------------------------------- |
| `spots.create_spot(data)`                 | draft spot, region-defaults template, ERA5 job |
| `spots.update_spot(id, data)`             | patch editorial + structural/category columns (validated) |
| `spots.update_spot_metadata(id, editorial)` | merge editorial (incl. free text); value **or** `n/a` |
| `spots.override_auto_field(id, field, val)` | pin to `overrides`, keep auto, audit        |
| `spots.revert_override(id, field)`        | drop the override                           |
| `spots.manage_spot_image(id, image)`      | url/source/license/credit (all mandatory)   |
| `readiness.validate_spot_readiness(id)`   | checklist + `ready` from `required_fields`   |
| `spots.set_spot_live(id)`                 | publish — only if ready, else gap list (409) |
| `regions.create_region` / `assign_spot_to_region` / `update_region_defaults` | region CRUD + template |
| `jobs.trigger_era5_job` / `get_job_status` | (re)submit / inspect the ERA5 job           |

Bilder werden seit Sprint 6 durch den Media-Picker gesetzt (`app.media.adopt`,
`app.api.admin_media`); die einmalige Unsplash-Stock-Seam ist zurückgebaut.

### Maintenance flow

```
create_spot ──▶ status=draft, era5_cell resolved, ERA5 job queued, defaults inherited
   │
   ├─ update_spot_metadata   (description & co.; each field a value or "n/a")
   ├─ manage_spot_image      (url + source + license + credit)
   └─ (climatology derives offline via the Sprint 2 pipeline)
   │
validate_spot_readiness ──▶ checklist + gaps
   │
set_spot_live ──▶ published   (rejected with the gap list until ready)
```

### Required fields, and what `n/a` means

Completeness is **declarative**: the `required_fields` table lists fields (some
gated per sport via `applies_when`, e.g. `usable_wind_directions` for wind sports,
`tide` for surf). A field is satisfied by a real value **or** the explicit `n/a`
sentinel — so a curator can mark a field *not applicable* and still reach `ready`.
On top of the field rules, readiness also requires a **derived climatology** and a
**fully-credited image**. `set_spot_live` refuses (HTTP 409) with the exact gap
list until everything passes.

### Overrides: provenance, audit, and recompute

`override_auto_field` writes the pinned value into `spots.overrides` — the
auto-computed column is **left intact** — and appends a `spot_audit` row recording
`{field, auto, from, to}`. Read endpoints surface the effective value with a
per-field provenance of **`überschrieben`** (vs. `auto`); `revert_override` removes
it. Because overrides live in their own column, **`recompute_climatology` (Sprint 2)
rewrites `spots.climatology` but never touches `spots.overrides`** — a pinned value
survives a re-derivation. (There is intentionally no `wind_danger`/`hazards`
field; unusable conditions are simply a `nein`.)

## Admin auth & accounts (Sprint A)

Real login replaces the shared `X-Admin-Key`. Operators sign in with an email +
password; the server sets a short-lived **JWT in an httpOnly cookie**
(`swd_session`, 12 h). Two roles: **`admin`** (everything, incl. user management)
and **`curator`** (curate/moderate, no user management). The signed-in user's
email is the **`actor`** recorded in every audit row.

- Model [`AdminUser`](app/models/admin_user.py) (migration `0004`), passwords
  hashed with **bcrypt** ([`app/auth/security.py`](app/auth/security.py)).
- Guards in [`app/auth/deps.py`](app/auth/deps.py): `current_user`,
  `require_role("admin"[, "curator"])`, `get_actor`. The `/admin` router requires
  `admin` **or** `curator`; `/admin/users` requires `admin`.
- **Bootstrap:** on startup, if no admin exists and `ADMIN_BOOTSTRAP_EMAIL` /
  `ADMIN_BOOTSTRAP_PASSWORD` are set, the first admin is created (idempotent).
- **Break-glass:** an optional `ADMIN_KEY` (unset by default) still lets a correct
  `X-Admin-Key` header through as `actor="break-glass"`, for emergencies only.

New endpoints:

| Method + path                       | Role    | Purpose                              |
| ----------------------------------- | ------- | ------------------------------------ |
| `POST /auth/login`                  | public  | set session cookie, returns the user |
| `POST /auth/logout`                 | any     | clear the session cookie             |
| `GET  /auth/me`                     | session | current user (401 if signed out)     |
| `GET/POST /admin/users`             | admin   | list / create operator accounts      |
| `PATCH /admin/users/{id}`           | admin   | change role / active / display name  |
| `POST /admin/users/{id}/password`   | admin   | reset a user's password              |

Frontend: `AuthProvider`/`useAuth` ([`src/lib/auth.tsx`](frontend/src/lib/auth.tsx)),
`credentials: "include"` on every request, a `/admin/login` page, a `RequireAuth`
route guard, and an admin-only `/admin/users` screen. The old `AdminKeyBar` is gone.

New env vars (see [`env.prod.example`](env.prod.example)): `JWT_SECRET`,
`ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`, `COOKIE_SECURE`,
`TAKEDOWN_CONTACT_EMAIL` (+ optional break-glass `ADMIN_KEY`).

## Admin dashboard (Sprint B)

A back-office UI so the operator finds and drives everything without URL-guessing.
Read-side aggregation in [`app/admin/dashboard.py`](app/admin/dashboard.py) over
existing tables (no new state); new read endpoints on the `/admin` router:

| Method + path      | Purpose                                                        |
| ------------------ | -------------------------------------------------------------- |
| `GET /admin/overview` | KPIs: spot status counts, region count, readiness gaps, recent + not-live lists |
| `GET /admin/spots`    | filter (`status`,`region_id`,`sport`,`q`) + `sort` + paginate → `{items,total}` |
| `GET /admin/regions`  | regions with per-status spot counts                         |

Frontend: an [`AdminShell`](frontend/src/components/AdminShell.tsx) layout (sidebar
nav + user/logout), a dashboard ([`AdminHome`](frontend/src/pages/AdminHome.tsx))
with status tiles + "not live / readiness open" + recently edited, a filterable
spots table ([`AdminSpots`](frontend/src/pages/AdminSpots.tsx)) with go-live/ERA5
row actions, a regions view ([`AdminRegions`](frontend/src/pages/AdminRegions.tsx))
with create + defaults + stock-image, and `AdminSpotForm` extended with an ops
panel ([`SpotOpsPanel`](frontend/src/components/SpotOpsPanel.tsx): readiness +
go-live, ERA5 trigger/status, and a read-only view of active overrides). All admin
routes are nested under the shell behind `RequireAuth`. No new env vars.

## Community / UGC (Sprint C)

The public write layer: users rate spots, leave local tips, propose new spots, and
upload images (gallery + hero candidates) — with a versioned image license accepted
at upload. **No moderation UI yet** (that's Sprint D); status fields are already in
place so nothing user-submitted goes live unreviewed where it shouldn't. Models in
[`app/models/ugc.py`](app/models/ugc.py) (migration `0005`), pseudonymous
(`author_name` + non-public `author_email`, nullable `app_user_id` reserved).

Endpoints in [`app/api/community.py`](app/api/community.py) — all writes are
rate-limited per IP (Redis, fail-open) with a honeypot field and store a salted
`ip_hash` (never the raw IP):

| Method + path                    | Purpose                                                   |
| -------------------------------- | --------------------------------------------------------- |
| `GET  /community/license`        | versioned upload terms (`v1`) for the consent checkbox     |
| `POST /spots/{id}/ratings`       | stars(1–5) + skill_level + sport + **conditions** (req)    |
| `GET  /spots/{id}/ratings`       | published ratings **+ aggregate** (count, avg, Bayesian score) |
| `POST /spots/{id}/tips` · `GET`  | local tips (published only)                                |
| `POST /submissions`              | new-spot proposal — validated vs. create schema, stored `pending` (no spot created) |
| `POST /spots/{id}/images`        | multipart upload; `hero_candidate` must pass HERO_REQ, `gallery` moderate limits; `license_accept` required |
| `GET  /spots/{id}/images`        | visible gallery (`approved` / `published_hero`)            |
| `POST /images/{id}/report`       | increments `report_count`, returns the take-down contact   |

`gallery` uploads are post-moderated (visible immediately, reportable);
`hero_candidate` uploads default to `pending` and await admin approval (Sprint D).
The rating aggregate uses a **Bayesian average** `(C·m + Σstars)/(C + n)`
([`app/community/aggregate.py`](app/community/aggregate.py)) with three sort-mode
key functions (`beste` / `geheimtipp` / `empfohlen`) the search layer can reuse
without recomputing the numeric scoring core. License terms live in
[`app/media/license.py`](app/media/license.py); the take-down address comes from
`TAKEDOWN_CONTACT_EMAIL`. No new env vars beyond that (added in Sprint A).

## Moderation / review (Sprint D)

The operator sights and decides every user contribution from one panel. Service in
[`app/admin/moderation.py`](app/admin/moderation.py); every decision writes a
[`ModerationAudit`](app/models/moderation_audit.py) row (migration `0006`,
`actor` = the logged-in email). Approvals reuse the normal admin write path — a
submission becomes a **draft** spot via `create_spot`; a hero candidate is promoted
into `spot.image` via `manage_spot_image` — so nothing bypasses readiness/go-live.

Endpoints (admin/curator) on the `/admin` router:

| Method + path                              | Effect                                          |
| ------------------------------------------ | ----------------------------------------------- |
| `GET  /admin/review/queue`                 | bundled items + counts (also feed `/admin/overview`) |
| `POST /admin/submissions/{id}/approve`     | create draft spot, link `resulting_spot_id`, `merged` |
| `POST /admin/submissions/{id}/reject`      | `rejected` + review note                        |
| `POST /admin/images/{id}/approve`          | promote hero candidate → `published_hero`       |
| `POST /admin/images/{id}/reject`           | `rejected`                                       |
| `POST /admin/images/{id}/remove`           | `removed` (out of gallery/hero)                 |
| `POST /admin/images/{id}/dismiss-reports`  | clear `report_count` + report rows              |
| `POST /admin/tips/{id}/hide` · `/restore`  | hide/unhide a tip (reversible)                  |
| `POST /admin/ratings/{id}/hide` · `/restore` | hide/unhide a rating (reversible)             |

Frontend: an [`/admin/review`](frontend/src/pages/AdminReview.tsx) panel with tabs
(submissions · hero images · reported images · tips & ratings), each item showing a
preview + context + approve/reject/remove + note. The public spot page gains a
[`SpotCommunity`](frontend/src/components/SpotCommunity.tsx) section — gallery with a
"Melden" report dialog, ratings (aggregate + form), local tips (list + form), and a
user image upload with the visible license checkbox (client-side hero-size gate,
reusing `HERO_REQ`). No new env vars; migration `0006`.

## Media picker (Sprint 8-media)

The admin picks hero and gallery images through **`/admin/media`** — a
serverside proxy over Unsplash, Pexels, Wikimedia Commons and Openverse plus a
cross-provider coordinate search. Adopting a photo writes a complete, correct
rights record without anybody typing it: the provider is re-queried on adopt so
the client-supplied identity is verified, the size and licence gates run
serverside a second time, and the resulting object is persisted through
`app.media.image_object.build_image` — the same canonical shape every image on
a spot or region has since migration `0027`.

### The image object

Written by `build_image`, validated by the same code, and read by both the
admin and the public site through one component (`ImageCredit`):

```jsonc
{
  "url":          "https://images.unsplash.com/…",
  "source":       "Unsplash",           // display name shown in the credit
  "license":      "Unsplash License",   // snapshot text as it read on adopt
  "license_url":  "https://…", "credit": "Sam Rivera",
  "credit_url":   "https://…",          // photographer profile / attribution link
  "provider":     "unsplash",           // machine slug: unsplash|pexels|wikimedia|
                                        // openverse|upload|community|manual|seed|unknown
  "external_id":  "Qw3w0hVjJ2M",        // provider photo id → duplicate index
  "source_page":  "https://…",          // the photo's detail page at the provider
  "retrieved_at": "2026-08-06T…Z",
  "delivery":     "hotlinked",          // hotlinked (provider CDN) | hosted (our storage)
  "focal":        {"x": 50, "y": 50},   // object-position percent
  "width": 6000, "height": 4000,
  "geo_verified": false,                // only true where coordinate proximity was established
  "role":         "hero",               // hero | gallery
  "source_status": null, "source_checked_at": null   // populated by verify-sources
}
```

**Licence snapshot, not licence reference.** Photos get deleted, accounts
vanish, and provider terms change; a link alone would not survive that.

### Provider proxy

| Provider     | Delivery    | Key needed?              |
|--------------|-------------|--------------------------|
| Unsplash     | `hotlinked` | `UNSPLASH_ACCESS_KEY` — demo 50/h, production 5000/h |
| Pexels       | `hosted`    | `PEXELS_API_KEY`         |
| Wikimedia    | `hosted`    | user-agent only (`WIKIMEDIA_USER_AGENT`) |
| Openverse    | `hosted`    | anonymous works; `OPENVERSE_CLIENT_ID` + `SECRET` raise the rate limit |
| *nearby*     | mixed       | cross-provider, coordinate-verified from Commons |

Provider API keys stay on the server. A missing key disables that one tab with
a clear message — it never breaks the overlay. Provider outages, exhausted
budgets and unavailable sources each isolate one tab: `status: "ok" | "disabled"
| "budget_exhausted" | "error"` on every search response.

### Budget & cache

Live in Postgres (`media_search_cache`, `media_provider_budget`), not Redis —
`app.live.cache` is deliberately fail-open, which is wrong for a request budget
(a counter that fails open cannot hold Unsplash's 50/hour line). The counter is
atomic (`INSERT … ON CONFLICT DO UPDATE`), search responses are cached for 24 h
per normalised query so trivially-different spellings share a cache entry, and
expired rows are swept alongside the existing climatology cron.

Tune with `MEDIA_BUDGET_PER_HOUR`, `MEDIA_BUDGET_WARN_RATIO`,
`MEDIA_SEARCH_CACHE_TTL`, `MEDIA_HTTP_TIMEOUT`.

### Size and licence gates

Hero-eligible: `w ≥ 3840 && h ≥ 1920` — the smallest source that survives a
2:1 crop without upscaling, whatever the focal point. Gallery-eligible: long
edge `≥ 1600`. Photos that fail a gate are marked, not hidden — a Wikimedia
gallery would otherwise look empty. Photos whose licence forbids commercial
use or modification are dropped, because an operator can never make them
usable.

### Adopt

`POST /admin/media/adopt` carries an **identity** — provider, external id,
role, target, focal — never a payload. Everything else is re-resolved. On
success the outgoing hero is demoted to the gallery, its `media_usage` entry
follows it, and the new hero replaces it. Duplicate hero photos are refused
with HTTP 409 (`code: "duplicate_hero"`); duplicate gallery photos surface as
a warning. `POST /admin/media/verify-sources` is operator-triggered and writes
`source_status` back into the image object.

### Deliberately absent

- **Pixabay.** Its API serves ~1280 px to non-approved accounts (fails the
  hero gate) and its terms forbid permanent hotlinking.
- **Multi-width derivatives and blur placeholders.** The repo re-encodes at
  one width; a proper responsive derivative set for adopted images is a
  separate piece of work.

## Categories, facilities, media & frontend

A later phase adds three **validated category axes**, **facilities**, a **hero-image
upload**, **CORS**, and a **React frontend** wired to the API (replacing the mock
data). The controlled vocabularies live in one place —
[`app/admin/constants.py`](app/admin/constants.py) — and are mirrored to German
display labels on the frontend in
[`frontend/src/lib/labels.ts`](frontend/src/lib/labels.ts):

| Axis (spot column)  | Keys (English, machine-readable)                                  |
| ------------------- | ----------------------------------------------------------------- |
| `level`             | `beginner` · `intermediate` · `advanced` · `pro`                  |
| `water_character`   | `flach` · `chop` · `welle_klein` · `welle_gross` · `tiefes_wasser`|
| `style` (multi)     | `freeride` · `freestyle` · `big_air` · `wave_riding`              |
| `facilities` (keys) | `parking` · `shower` · `food` · `camping` · `school`             |

- **Validation.** Invalid enum values are rejected at both the Pydantic layer and
  the service layer → **HTTP 422**. `NULL`/empty is always allowed and means
  *unknown*. `similarity/character.py` imports `LEVELS` from the same constants, so
  the level vocabulary has a single source of truth.
- **Readiness.** `water_character` is a **required** field (satisfiable by `"n/a"`);
  `style` and `facilities` are **recommended** and never block going live — a spot
  with unknown facilities is publishable.
- **Facilities semantics.** `facilities` is JSONB, `{kind: {"available": bool,
  "note"?: str}}`. A **missing** kind means *unknown* and is **hidden** on the spot
  page; `available: false` renders muted as "nicht vorhanden".
- **Filtering.** `GET /spots` gains `level`, `water_character`, and a multi-value
  `style` (array overlap). On the frontend these drive the **"Sortieren & Filtern"**
  dropdown; the categories are filter/sort data only and are **not** shown as pills
  on spot cards. They **are** shown in the spot-page "Steckbrief".

### Hero-image upload

`POST /admin/spots/{id}/image/upload` (multipart: `file` + `credit`) re-validates
the same rules as the frontend gate ([`ImageUpload.tsx`](frontend/src/components/ImageUpload.tsx)
`HERO_REQ`) **server-side** — min **3840×2000 px**, landscape, JPG/PNG, ≤ **12 MB** —
in [`app/media/hero.py`](app/media/hero.py). The file is stored under
`MEDIA_DIR/spots/{id}/hero.<ext>` and served via the `MEDIA_URL_PREFIX` StaticFiles
mount; the spot image is recorded as `{url, source: "upload", license: "own",
credit}`. The URL-based `POST /admin/spots/{id}/image` remains as an alternative.

### Frontend

React 18 + Vite + TypeScript + Tailwind + React Router + Leaflet, in
[`frontend/`](frontend/). The pages fetch live from the API (no more mock spots),
with loading skeletons and error states:

```bash
cd frontend
npm install
cp .env.example .env.local     # VITE_API_URL, default http://localhost:8000
npm run dev                     # http://localhost:5173
npm run build                   # type-check + production build
npm test                        # vitest — filter/sort/adapter/facility-hiding logic
```

| Route                    | Page                                                       |
| ------------------------ | ---------------------------------------------------------- |
| `/`                      | Landing — published spots, sort/filter dropdown            |
| `/map`                   | Leaflet map of spots                                       |
| `/spot/:id`              | Spot detail — categories (Steckbrief), facilities, live    |
| `/region/:slug`          | Region — its spots, sort/filter dropdown                   |
| `/admin/spot/new`        | **Admin spot form** — full editorial record + image upload |
| `/admin/spot/:id/edit`   | Admin spot form, pre-filled for editing                    |

The admin form (`AdminSpotForm.tsx`) sets categories and facilities via dropdowns/
chips (never free-typed tags), uploads the hero image after creating the draft, and
then shows the readiness checklist (what still blocks "live"). The API base URL is
`VITE_API_URL`; root-relative image URLs from the API are resolved against it.

The layer split on the frontend: [`lib/api.ts`](frontend/src/lib/api.ts) (typed
fetch client), [`lib/labels.ts`](frontend/src/lib/labels.ts) (enum → German),
[`lib/adapt.ts`](frontend/src/lib/adapt.ts) (backend record → view model),
[`lib/hooks.ts`](frontend/src/lib/hooks.ts) (`useSpots`/`useSpot`/`useSpotLive`),
and [`lib/filters.ts`](frontend/src/lib/filters.ts) (URL-synced filter/sort state).

## Frontend ↔ Backend

Every page reads the **live API** — there is no mock data (`frontend/src/data/*`
was removed). Spots/regions come from the DB; the hero search hits `/search`; the
10-day forecast comes from `/spots/{id}/forecast`; category/facility/season panels
render real data and **hide** (or show an empty state) when the backend has none.

### The one config point: `VITE_API_URL`
The backend base URL is configured **only** via `VITE_API_URL` (a Vite build-time
variable). Nowhere else is it hardcoded (the sole fallback is
`http://localhost:8000` in `frontend/src/lib/api.ts` for local dev).

- **Local:** `cp frontend/.env.example frontend/.env.local` → `VITE_API_URL=http://localhost:8000`.
- **Vercel:** set `VITE_API_URL` in the project's Environment Variables to the
  deployed backend URL (e.g. `https://api.example.com`). Rebuild after changing it.
- The backend must allow the frontend origin via `CORS_ORIGINS` (Sprint 9).

> **Symptom → cause.** An **empty landing "aktuelle Top Spots" row and a dead
> search** on the deployed site is almost always a wiring problem, *not* missing
> data: `VITE_API_URL` is unset (so the build fell back to `http://localhost:8000`
> and every fetch fails), the backend is down/unreachable, or `CORS_ORIGINS` does
> not list the frontend origin. Check, in order: `GET <backend>/health` →
> `GET <backend>/spots?status=published` returns > 0 → the browser Network tab
> shows requests going to the **deployed** backend (not localhost) with no CORS
> error. Only once those pass is it a content problem (see the climatology batch
> below for empty season/best-spots panels).

### Local dev — both services at once
```bash
# terminal 1 — backend
docker compose up -d db redis
uvicorn app.main:app --reload            # http://localhost:8000

# terminal 2 — frontend
cd frontend && npm install && npm run dev # http://localhost:5173
```

### Search
The hero "WO? / WANN?" card submits `GET /search?q=&sport=&week=` and navigates
to `/search`. The Wind/Welle toggle maps to the backend's single-valued `sport`
filter (`welle/wave → surf`, `wind → kitesurf` as the representative wind
discipline). Open axes are covered minimally: an **empty** query shows the best
regions for the season (`/search/best-regions`), and each region page lists its
**best weeks** (`/areas/best-weeks`). These show an empty state until spots have a
derived climatology.

### Admin key
Admin write endpoints are guarded by `X-Admin-Key` when the server sets `ADMIN_KEY`
(Sprint 9). Enter the key once in the **admin form** (the "Admin-Key" bar); it is
held in memory + `sessionStorage` for the session and sent on every `/admin/*`
request. This is a single shared secret for an internal test operation — **not** a
user-auth system (no per-editor accounts or rights). Without a key entered, a
server that has `ADMIN_KEY` set returns 401 on writes (reads are unaffected).

### Image upload
Real hero-image uploads work: the admin form posts the validated file to the
multipart `POST /admin/spots/{id}/image/upload` (Sprint 3), which stores it under
`MEDIA_DIR` and serves it from the `/media` mount. There is no half-built upload UI
— the old standalone image page was removed; upload lives in the spot form.

## Deploy & Betrieb (VPS)

Production runs on a **single VPS with Docker Compose** — same `postgis`/`redis`
images as local dev, plus the API image (built from the `Dockerfile`) and a
[Caddy](https://caddyserver.com/) reverse proxy that terminates TLS automatically.
Files: `Dockerfile`, `docker-compose.prod.yml`, `Caddyfile`, `env.prod.example`,
`scripts/entrypoint.sh` (migrate-then-serve), `scripts/backup.sh`.

The frontend is hosted separately (static host); this VPS serves only the API, so
point the domain (e.g. `api.example.com`) and the frontend's `VITE_API_URL` at it.

### 1. Prerequisites
- A VPS (e.g. Hetzner CX22) with Docker + Docker Compose.
- A **DNS A-record** for your API domain → the VPS public IP, created **before**
  first start. Caddy provisions the Let's Encrypt cert on first request; without
  the A-record (and ports 80+443 reachable) certificate issuance fails.

### 2. Secrets — never commit `.env.prod`
`.env*` is gitignored (only the `*.example` templates are tracked). On the VPS:

```bash
git clone <repo> && cd surfwinddate
cp env.prod.example .env.prod
# generate strong secrets:
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)" >> .env.prod   # then remove the placeholder line
echo "ADMIN_KEY=$(openssl rand -base64 48)"        >> .env.prod
# edit .env.prod: set DOMAIN and CORS_ORIGINS (your frontend URL)
```

`DATABASE_URL` is **assembled** from `POSTGRES_USER/PASSWORD/DB` in the compose
file (host = the `db` service), so the password lives in exactly one place.

### 3. First deploy
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python -m app.seed.seed   # once
```
The app container runs `alembic upgrade head` on start (see `entrypoint.sh`); Caddy
waits for the app to be **healthy** (`depends_on: condition: service_healthy`) before
routing, so a failed migration keeps the new app unhealthy instead of serving a
half-migrated schema. `restart: unless-stopped` on every service means a VPS reboot
brings the whole stack back automatically.

### 4. Health
```bash
curl https://<domain>/health
# {"status":"ok","db":"ok","redis":"ok"}
```
Per-dependency status. A dead **DB** → `status:"error"`, **HTTP 503**. A dead
**Redis** (non-critical cache) → `status:"degraded"`, **HTTP 200** — so an uptime
check / the proxy never confuses a broken cache with a broken server.

### 5. Backups (local, 14-day rotation)
The `backup` service runs `pg_dump` (+ a tar of the media volume) daily into
**`./backups/` on the host** — a bind mount, **not** a Docker volume, so
`docker compose down -v` (which wipes the named volumes) **cannot** delete backups.
Files: `db-<timestamp>.sql.gz`, `media-<timestamp>.tar.gz`; older than 14 days are
pruned. (Offsite copy — S3/R2 — is out of scope; add e.g. `rclone` on `./backups/`.)

Trigger one on demand: `docker compose … exec backup sh /usr/local/bin/backup.sh`.

### 6. Restore
```bash
# fresh DB, then pipe a dump in (tested end-to-end incl. PostGIS geography):
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db \
  sh -c 'dropdb -U "$POSTGRES_USER" --if-exists surfwind_restore && createdb -U "$POSTGRES_USER" surfwind_restore'
gunzip -c backups/db-<timestamp>.sql.gz | \
  docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db psql -U surf -d surfwind_restore
# to make it live: point POSTGRES_DB at the restored DB (or restore into the main DB while the app is down).
```

### 7. Redeploy
```bash
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```
Migrations run automatically. Compose recreates the app container (a few seconds of
downtime — true zero-downtime migrations are out of scope); the health gate ensures a
broken build/migration is reported unhealthy rather than silently serving errors.

### Not in this sprint
Offsite backups, monitoring/alerting, autoscaling, zero-downtime migrations, CI/CD.

## Tests

The suite runs against the real `TEST_DATABASE_URL` (PostGIS required) for the
migration/seed/API/geo/pipeline tests, **and** sets of pure-function tests for the
ERA5 and live paths that need no database or network. When the test database is
unreachable the DB-backed tests **skip** (rather than error) so the pure tests
still run:

```bash
pytest                            # full suite
pytest tests/test_era5_core.py    # ERA5 pipeline math only, no infra needed
pytest tests/test_live.py         # live/forecast logic only, no infra needed
pytest tests/test_scoring.py      # score engine: gates/gust/levels/climatology
pytest tests/test_search_core.py  # search logic only (text/geocode/rank/cluster)
pytest tests/test_open_axes.py    # time windows, coverage/intensity, region aggregate
pytest tests/test_similarity.py   # orientation mirroring, character/season, modes
pytest tests/test_admin_core.py   # readiness rules, n/a, provenance (no infra)
pytest tests/test_media_image_object.py  # canonical image object (no infra)
pytest tests/test_media_providers.py     # provider normalisation against frozen fixtures
pytest tests/test_media_search.py        # cache, budget, per-tab degradation (DB)
pytest tests/test_media_adopt.py         # both delivery paths, duplicates, demotion (DB)
pytest tests/test_media_gallery.py       # gallery order/remove/promote + worklist (DB)
```

Frontend logic is covered by vitest without a DOM (no jsdom, no
testing-library — deliberately: everything worth asserting is a pure function
in `src/lib/`). The one full click-through of the media picker lives in
`frontend/e2e/media-picker.spec.ts` and stubs every backend call.

The ERA5 tests use a mocked CDS client over a small synthetic hourly series and
cover the component maths, the daylight filter, histogram aggregation, display
stats, raw-file round-trip, the 52-week climatology, and recompute determinism.
The live tests use a mocked Open-Meteo client and cover model selection, cache
hit/miss (no second HTTP call within the TTL), confidence staffing, and the
10-day horizon cap. The score-engine tests run over synthetic values/histograms and
cover the kite + surf gates, gustiness downgrade, level offsets, the climatology
week/curve (with live↔climatology consistency), `describe_week` and confidence.
The search tests split into pure-logic tests (text matching,
point/area classification, ranking with distance damping, clustering, sport
filtering) and DB-gated integration tests (`tests/test_search_db.py`,
`tests/test_search_api.py`) that exercise the Laboe/area/geometry/toggle scenarios
against seeded PostGIS with a mocked geocoder + scorer. The open-axes tests
(`tests/test_open_axes.py`) cover time-window resolution, coverage-vs-intensity
ranking, open time/place, and the region aggregate (counting working spots rather
than averaging); `tests/test_open_axes_api.py` runs the reverse endpoints against
seeded PostGIS. The similarity tests (`tests/test_similarity.py`) cover orientation
mirroring, character/season distance, all three modes and the alternatives
running-filter; `tests/test_similarity_api.py` runs the endpoints over seed spots.
The admin tests (`tests/test_admin_core.py`) cover the readiness rules, `n/a`
counting, the applies-when gating and override provenance; `tests/test_admin_api.py`
walks the full create → curate → validate → live path plus override/audit/recompute/
revert against seeded PostGIS.

## Design notes / assumptions

The prompt references "Spezifikation v2 / Datenmodell v1" for the auxiliary
tables, which was not available; their columns are reasonable interpretations and
may be refined in later sprints. Notable choices:

- **UUID primary keys** via Postgres `gen_random_uuid()` (built-in, no extension).
- **GeoAlchemy2 `Geography(... , spatial_index=False)`** so the migration owns the
  GIST indexes explicitly (no implicit duplicate index).
- `watches` references the owning user via an opaque `user_ref` string — there is
  no `users` table in this sprint.
- `confidence` is a float in `[0, 1]`; `facing` is a compass bearing (`smallint`).
- `apply_overrides(spot)` (`app/services/overrides.py`) lays editor `overrides` on
  top of auto-computed fields and returns the effective values plus an
  `_overridden` list. Climatology-derived auto-fields arrive in a later sprint, so
  the "auto" baseline is currently the stored column values.
