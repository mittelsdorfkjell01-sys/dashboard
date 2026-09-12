# Repository routing and validation

## Review triggers

Trigger this skill for semantic changes in:

- app/live/**, app/weather/**, or app/forecast/**;
- app/models/forecast_system.py or app/models/weather_verification.py;
- app/schemas/live.py;
- app/api/spots.py, app/api/admin_weather.py, app/api/cron.py, or app/api/weather_fields.py;
- related Alembic migrations, configuration, providers, caches, workers, schedulers, and runbooks;
- frontend/src/lib/api.ts, forecast normalization, direction snapshots, SpotDataScope, and public map/data consumers;
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
| GWA/terrain/microscale code | Candidate provenance, replacement-versus-composition rule, family blend, clamps, gate evaluation |

## Validation matrix

Choose the narrowest relevant set, then expand when a cross-layer contract changed.

| Concern | Existing test areas to inspect or run |
|---|---|
| Data-kind and live contract | tests/test_live.py, tests/test_live_api.py, tests/test_observation_contract.py, tests/test_weather_contract_v4.py |
| Snapshots and freshness | tests/test_forecast_system.py, tests/test_forecast_publication_cache.py, tests/test_forecast_refresh_worker.py, tests/test_forecast_honest_label.py |
| Verification and calibration | tests/test_forecast_verification_harness.py, tests/test_weather_verification.py, tests/test_sector_calibration.py |
| Sector/GWA/microscale | tests/test_sector_runner.py, tests/test_gwa_producer.py, tests/test_microscale.py, tests/test_wind_sector_blend.py |
| API/frontend equality | Relevant backend endpoint tests plus frontend normalization, direction, data-scope, and component tests; run the frontend build |
| Persistence | Local PostgreSQL/PostGIS only; do not substitute SQLite |

Run scripts/check.ps1 weather when available, but do not assume its current selection covers all forecast modules or cross-layer frontend changes.

## Minimum regression scenarios

Add or identify evidence for every affected scenario:

1. A fresh station observation and a model value retain independent speed, direction, u/v, timestamps, and source labels.
2. Station selection chooses the nearest eligible fresh high-quality observation deterministically and rejects stale, future, blocked, and over-distance data.
3. An older source capture wrapped by a new generation remains old/stale.
4. Every active correction publishes a database-valid state and cannot bypass its governance threshold.
5. Changing an active calibration or sector version invalidates or republishes affected output.
6. Training and holdout observations are disjoint by stable identity and time.
7. The frontend displays the source and timestamp belonging to the exact value shown.
8. Backend serialization retains every weather field that the frontend contract declares.

## Continuous enforcement

For automatic coverage, invoke this review on pull_request opened, synchronize, reopened, and ready_for_review events. Run deterministic tests in CI and make the weather-integrity result a required branch-protection check. A path filter may skip clearly visual-only changes, but the review itself must perform semantic impact expansion.
