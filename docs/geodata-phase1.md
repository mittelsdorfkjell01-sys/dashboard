# Automatic geoprofiles — phases 0 and 1

Status: 2026-08-12. Raster attributes are diagnostic/shadow inputs and do not change the public forecast, weights, fetch, roughness, thermal or coastal corrections.

## Official source register

The executable register is `app/forecast/geodata_catalog.py`; database copies are immutable by `(key, version)`.

| Key | Exact instance | Version | Access | CRS / datum | Licence |
|---|---|---|---|---|---|
| `cop-dem-glo30` | `COP-DEM_GLO-30-DGED` (GLO-30-F) | 2024_1 | CDSE OData/S3; registered CCM user and accepted licence | WGS84-G1150 / EGM2008 (EPSG:3855) | free GLO-30-F licence; mandatory WorldDEM attribution |
| `cop-dem-glo90` | `COP-DEM_GLO-90-DGED` (GLO-90-F) | 2024_1 | same; fallback | WGS84-G1150 / EGM2008 | free GLO-90-F licence |
| `worldcover-2021` | `ESA_WorldCover_10m_2021_v200` | v200 | public HTTPS/S3, no authentication | EPSG:4326 | CC BY 4.0 |
| `copernicus-glc100` | Collection 3, epoch 2019 | v3.0.1 | registered fallback only, disabled | EPSG:4326 | Copernicus data policy |

Copernicus DEM is a digital surface model (DSM), not a terrain-only DTM. Buildings and vegetation can affect elevation. DGED is floating GeoTIFF in 1° cells; longitude spacing varies at high latitude. Quality layers are WBM, HEM, EDM and FLM. WBM values are land 0, ocean 1, lake 2 and river 3. The handbook specifies WGS84-G1150, EGM2008, metres and RasterPixelIsPoint.

WorldCover v200 is a model classification, not perfect local truth. It supplies 11 classes in 3° × 3° COGs (EPSG:4326, NoData 0), covering global land except Antarctica and north of 82.75°N. InputQuality is a separate 60 m three-band product. Phase 1 keeps original classes and descriptive groups over metric 0–250 m, 250 m–2 km and 2–5 km rings.

## Local setup and access

Install requirements, migrate to `0033_geodata_phase1`, and configure `GEODATA_CACHE_DIR`. WorldCover requires no secret. GLO-30/GLO-90 require a CDSE account, CCM enabled in the identity profile, licence acceptance, and locally configured `COPERNICUS_CDSE_CLIENT_ID` / `COPERNICUS_CDSE_CLIENT_SECRET`. Secrets must never enter source, reports or logs. Registration or acceptance is never automated.

No local CDSE credentials were configured for the documented run. The real DEM/WBM request was therefore correctly blocked; fixtures and metadata contracts remain testable. No unofficial mirror is used.

## Cache and safety

Large rasters are not stored in PostgreSQL. `RasterCache` uses explicit HTTPS assets, optional Range headers, run/asset/temp limits, at most three jittered retries, per-key locks, temporary files and atomic rename. A server ignoring Range is rejected. Derived WorldCover windows are reusable compressed NPZ files; SHA-256, size, version and profile references are persisted. Restrictive foreign keys protect referenced assets.

Defaults: two downloads, two profiles, 10 MB/run, 50 MB/Berlin day, 8 MB/asset, 20 MB temporary and 1 GB cache. Daily accounting and cross-process locks need a shared worker/cache before horizontal scaling; current locks are process-local.

## Profile and activation

Identity includes spot, coordinate hash, `swd-geo-v2` and pinned dataset versions. WorldCover COG blocks are window-read, transformed into local UTM (polar stereographic outside UTM), cropped metrically and summarized. DEM fixture analysis derives elevation statistics, relief, slope/aspect, ruggedness, WBM surface and nearest water/land. Categories use nearest-neighbour semantics.

A WorldCover-only partial profile is C; complete primary inputs are A; fallback/local uncertainty is B; unusable inputs are D. D never activates. Component qualities are separate. Geoprofile and physics remain separate, SRTM remains a diagnostic height fallback, and the public correction contract is unchanged.

## Preflight and backfill

```powershell
python scripts/geodata_preflight.py --output reports/geodata-preflight.json --cache-dir data/geodata-preflight-cache
python scripts/forecast_backfill.py --batch-size 10 --dry-run
```

Preflight hard-codes exactly five published representatives, probes one 64 KiB COG range per spot sequentially, refuses full downloads, activates nothing, and writes JSON plus Markdown. The temporary cache was removed after verification and is reproducible. Backfill is preview-first, capped at ten and shows WorldCover/DEM tile groups plus CDSE access obstacles. External I/O occurs only in the existing post-commit job runner.

## Phase 2

`PHASE2_SECTORS` reserves sixteen meteorological 22.5° sectors without fake values. Next: multiple rays, censored water fetch to 100 km, first land, continuous water, multi-scale coastline tangent/normal, effective roughness, terrain horizon/blocker and conservative shelter. Activation requires measurement-backed shadow comparison; an automatic profile is not measurement validation.
