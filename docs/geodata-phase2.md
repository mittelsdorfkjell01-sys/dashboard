# Geoprofile phase 2 — directional shadow features

Status 2026-08-12, algorithm `swd-shadow-v2-sectors16-rays9`. Phase 2 is implemented as an internal, versioned feature engine. Its five-spot Copernicus pilot remains externally blocked because local CDSE/CCM credentials and licence-enabled access are absent. This is not reported as successful live processing.

## Strict production boundary

`app/forecast/shadow.py` is not imported by `publisher.py` or `physics.py`. Shadow profiles use separate tables and `active_shadow`; they cannot become the productive `SpotGeoProfileVersion` referenced by snapshots. No fetch, roughness, coastline, terrain-horizon or exposure value is a wind multiplier. The public API remains ten days, product “Surfwinddata Forecast”, with the same Open-Meteo transition fallback.

## Geometry

- 16 meteorological source-direction sectors: 0° north, 90° east, through 337.5°.
- Nine rays per sector over the inner 80%: offsets −9° through +9°.
- The ray goes from the analysis anchor toward the wind source; there is no 180° reversal.
- Scales: 30 m to 250 m, 60 m to 2 km, 180 m to 20 km and 600 m to 100 km.
- Local metric CRS comes from phase 1; high latitudes use polar stereographic.

## Features

Each ray retains first certain land, continuous water, transitions, ocean/lake/river fractions, coverage, NoData and four distance-ring water fractions. An open ray is stored as right-censored with no exact first-land value. Sector aggregation retains 10th/median/90th percentiles, censored/open fraction and at least six valid rays.

Water anchors are searched only within 250 m and never alter the persisted spot coordinate. WBM boundaries provide multi-scale 0.5/2/5 km tangents and normal candidates with PCA stability; a river is `not_applicable`, not a fake coastline. Ambiguous geometry is `conflicted`.

WorldCover’s eleven original classes remain primary. Coarse groups and a dimensionless shadow roughness index are diagnostic only. Forest, mangrove and built-up inputs set `possible_double_counting` because Copernicus DEM is a DSM. No exact z0 is claimed.

Terrain rays retain maximum positive geometric horizon angle, blocker distance and relative height through 20 km, including Earth-curvature adjustment. These remain separate fields rather than a wind factor. Production use later requires HEM/EDM/FLM quality gating and observation-backed calibration.

## Persistence and quality

Migration `0034_geodata_shadow_phase2` adds immutable `spot_geo_shadow_profiles` and individually indexed `spot_geo_shadow_sectors`. Identity hashes spot, coordinate, algorithm, pinned datasets and asset hashes. Identical input reuses a version. A new shadow profile activates only if it is ready, not D, and is not structurally worse than the current shadow profile. Component/sector statuses are `valid`, `degraded`, `unavailable`, `conflicted` and `not_applicable`.

## Access and pilot

The gate checks credentials before data bytes, then product instance, request count, known sizes and asset/run/day limits. Auth and licence blocks are terminal and are not retried. Defaults: five spots, two downloads, two computations, 256 MiB/asset, 1 GiB/run, 2 GiB/Berlin day, 10 GiB cache, 200 requests and three retries.

Run:

```powershell
python scripts/geodata_phase2_pilot.py
```

The committed report is `reports/geodata-phase2-pilot.*`: all five spots are `blocked_credentials`, with 0 requests and 0 bytes. Lo Stagnone is explicitly a lagoon; the lake branch is covered synthetically.

## Next gate

After local CCM registration and licence acceptance, resolve exact OData product metadata and layer asset sizes first. Only if the written plan fits all limits should one five-spot DEM/WBM/HEM/EDM/FLM pilot run. Phase 3 can begin only after plausible real sectors and cache/load evidence; it remains a bounded, tile-centred backfill, not public activation.
