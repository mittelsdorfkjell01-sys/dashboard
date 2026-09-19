# Repository routing and validation

## Review triggers

Trigger this skill for semantic changes in:

- app/live/**, app/weather/**, or app/forecast/**;
- app/models/forecast_system.py, app/models/weather_profile.py, app/models/weather_verification.py, or app/db/schema.py;
- app/schemas/live.py;
- app/api/spots.py, app/api/admin_weather.py, app/api/cron.py, or app/api/weather_fields.py;
- related Alembic migrations, .env.example, vercel.json, workflows, providers, caches, workers, schedulers, and runbooks;
- scripts/activate_sectors.py, scripts/run_sector_producer.py, scripts/verification_report.py, and weather/forecast workers;
- frontend/src/lib/api.ts, spotMapReading.ts, forecastNormalization.ts, directionSnapshot.ts, SpotDataScope, SpotDetail, LocatorMap, WindSidebar, SpotMap, MapView, SpotCard, and other public weather consumers;
- weather tests and fixtures.

Also trigger on changed fields or concepts such as wind, gust, direction, u/v, measurement, nowcast, forecast, station, calibration, sector, GWA, terrain, microscale, provenance, validity, freshness, or stale state. Paths are an optimization, not the semantic boundary.

## Impact expansion

When one layer changes, trace these adjacent layers:

| Changed area | Expand the review to |
|---|---|
| Schema or response model | Route assignment, serializer, cache payload, OpenAPI, frontend type, adapter, component, fixture |
| Physics/profile/sector code | Live serving, forecast publisher, correction ledger, context/version hash, activation, verification, cache invalidation |
| Station or calibration code | Import, eligibility, selection, training cohort, holdout, serving, snapshots, admin decisions, invalidation |
| Timestamp or cache code | Provider issue/capture, model run, valid time, age/stale calculation, expiry, CDN behavior, UI label |
| Migration or constraint | ORM model, publisher values, upgrade/rollback behavior, PostgreSQL integration tests |
| Live serving or cache code | Single and batch endpoints, cache hit and miss, model-nowcast and measurement caches, endpoint parity |
| Forecast serving or cache code | Publisher, active immutable snapshot, public Redis cache, cold/transitional fallback, verification |
| GWA/terrain/microscale code | Candidate provenance, `combined_correction` GWA/microscale composition, runtime application count, family blend, clamps, gate evaluation |
| Public frontend weather code | The ownership and forbidden surfaces in display-contract.md, adapters, labels, timestamps, source attribution |

## Validation matrix

Choose the narrowest relevant set, then expand when a cross-layer contract changed.

| Concern | Existing test areas to inspect or run |
|---|---|
| Data-kind and live contract | tests/test_live.py, tests/test_live_api.py, tests/test_live_measurement_contract.py, tests/test_public_weather_cache.py, tests/test_weather_contract_v4.py |
| Timestamp identity | tests/test_weather_time_identity.py plus affected provider, cache, and endpoint tests |
| Snapshots and freshness | tests/test_forecast_system.py, tests/test_forecast_snapshot_quality.py, tests/test_forecast_publication_cache.py, tests/test_forecast_refresh_worker.py, tests/test_forecast_honest_label.py |
| Verification and calibration | tests/test_forecast_verification_harness.py, tests/test_weather_verification.py, tests/test_sector_calibration.py |
| Sector/GWA/microscale | tests/test_sector_runner.py, tests/test_sector_gate_guard.py, tests/test_combined_wind_correction.py, tests/test_gwa_producer.py, tests/test_microscale.py, tests/test_wind_sector_blend.py |
| API/frontend equality | Relevant backend endpoint tests plus frontend/src/lib/__tests__/spotMapReading.test.ts, directionSnapshot.test.ts, forecastNormalization.test.ts, frontend/src/state/SpotDataScope.test.ts, affected component/E2E tests, and the frontend build |
| Persistence | tests/test_migration.py and affected persistence tests against local PostgreSQL/PostGIS only; do not substitute SQLite |

Run scripts/check.ps1 weather when available. It is a foundational smoke selection, not the complete weather-integrity suite: inspect the script and add every affected test from this matrix.

## Minimum regression scenarios

Add or identify evidence for every affected scenario:

1. Open-Meteo current remains a model nowcast, while a station measurement, LiveWind, and adaptive forecast retain independent speed, direction, u/v, timestamps, product kind, and source labels.
2. Station analysis rejects stale, future, blocked, and over-distance data; weights eligible observations by all available relevance dimensions; and raises uncertainty when they disagree.
3. An older source capture wrapped by a new generation remains old/stale.
4. A published forecast impulse is frozen against later observations, decays monotonically with lead time, reaches zero at its configured horizon, and leaves separately validated persistent corrections intact.
5. GWA level and microscale roughness/fetch compose once into their candidate provenance, and the resolved active sector correction is applied exactly once at runtime.
6. Every active correction publishes a database-valid state and cannot bypass its governance threshold.
7. Changing an active calibration or sector version invalidates or republishes affected output.
8. Training and holdout observations are disjoint by stable identity and time.
9. Single/batch and warm/cold LiveWind paths agree; snapshot, public-cache, and honest fallback forecast paths preserve the same product semantics.
10. The frontend displays each product only on surfaces permitted by display-contract.md and shows the source and timestamp belonging to the exact value shown.
11. Backend serialization retains every weather field that the frontend contract declares.

## Continuous enforcement

The project-local metadata allows implicit skill discovery, and the root AGENTS.md routes relevant reviews to this skill. This provides consistent agent-assisted reviews but is not a required GitHub status check.

For automatic enforcement, add a separately authorized workflow or GitHub integration on pull_request opened, synchronize, reopened, and ready_for_review events. Run deterministic tests in CI and make the weather-integrity result a required branch-protection check. A path filter may skip clearly visual-only changes, but the review itself must perform semantic impact expansion.
