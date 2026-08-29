# Repository map

This is the compact navigation index for humans and coding agents. It describes ownership and task routing; implementation details remain next to the code.

## Repository roles

| Repository | Role | Direction |
|---|---|---|
| `dashboard-main` | Canonical development source | Features and fixes start here |
| `surfwinddata-main` | Public/release mirror | Receives intentional merges or cherry-picks from dashboard |

Do not implement the same task independently in both working trees. Confirm and test it in `dashboard-main`, then synchronize explicitly when requested.
Before synchronization, run `./scripts/repo-drift.ps1 -Fetch`. A `diverged` result requires reviewing both commit lines instead of a blind merge.

## Runtime topology

```text
React/Vite browser
  -> FastAPI (`app/main.py`)
     -> PostgreSQL/PostGIS (`app/models`, Alembic)
     -> Redis caches/queues
     -> weather, tide, geodata and media providers
```

Local defaults: frontend `5173`, API `8000`, PostgreSQL `5432`, Redis `6379`.

## Backend ownership

| Area | Primary paths | Contract/tests |
|---|---|---|
| Public spots/map | `app/api/spots.py`, `app/public_catalog.py`, `app/schemas/spot.py` | `tests/test_api.py`, frontend public-map tests |
| Regions/search | `app/api/regions.py`, `app/api/search.py`, `app/search/` | `tests/test_api.py`, search tests |
| Admin catalogue | `app/api/admin.py`, `app/admin/` | `tests/test_admin_api.py`, admin service tests |
| Live/forecast | `app/live/`, `app/api/weather_fields.py`, `app/schemas/live.py` | `tests/test_live*.py`, weather contract tests |
| Weather physics | `app/weather/`, `app/nearshore/`, `app/spatial_fields/` | `tests/test_weather*.py`, spatial-field tests |
| Wind climatology | `app/wind_climatology*`, `app/api/admin_weather.py` | climatology and admin-weather tests |
| Tides | `app/tides/`, `app/api/admin_tides.py` | tide tests |
| Community/accounts | `app/api/community.py`, `app/api/account.py`, `app/account/` | community/account tests |
| Media | `app/api/admin_media.py`, `app/media/` | media tests |
| Persistence | `app/models/`, `app/db/`, `alembic/versions/` | migration and model tests |

## Frontend ownership

| Area | Primary paths | Focused tests |
|---|---|---|
| Public map | `frontend/src/pages/MapView.tsx`, `components/SpotMap.tsx`, `lib/publicMap.ts` | `lib/__tests__/publicMap.test.ts`, map E2E specs |
| Spot detail | `frontend/src/pages/SpotDetail.tsx`, `components/data/` | component/lib tests, spot-detail E2E |
| Public catalogue | `frontend/src/lib/api.ts`, `lib/adapt.ts`, `lib/hooks.ts` | adapter and hook tests |
| Admin | `frontend/src/adminRoutes.tsx`, `pages/Admin*.tsx`, `components/admin/` | admin E2E/specs |
| Shared UI | `frontend/src/components/`, `frontend/src/index.css` | closest component test plus build |
| Account | `frontend/src/pages/account/`, auth/account API helpers | account tests/E2E |

## Important data flows

### Public map catalogue

```text
MapView
  -> GET /spots/version (short edge cache)
  -> GET /spots?catalog_version=... (immutable versioned edge cache)
  -> SpotSummary
  -> adaptSpots
  -> GeoJSON in publicMap/SpotMap
```

### Spot detail weather

```text
SpotDetail
  -> public spot record
  -> live/forecast endpoints
  -> normalized API contract
  -> adapters and direction snapshots
  -> data components/meteogram
```

### Admin spot editing

```text
AdminSpotForm
  -> admin API
  -> validation/readiness/audit services
  -> SQLAlchemy models
  -> catalogue version changes
```

## Task routing

Use `./scripts/context.ps1 <area>` with one of:

- `spots`, `map`, `weather`, `admin`, `frontend`, `database`, `tests`, `changed`

Use `./scripts/check.ps1 <area>` with one of:

- `spots`, `map`, `weather`, `admin`, `frontend`, `backend`, `changed`

Start narrow. Expand only when imports, contracts, or failing tests prove a wider dependency.

## Excluded by default

Do not load these into agent context unless directly requested:

- `.git/`, `node_modules/`, `frontend/dist/`
- `data/`, `reports/`, screenshots and downloaded geodata/weather inputs
- `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`
- `.codex/*.log`, review transcripts and local runtime output
- `frontend/tsconfig.tsbuildinfo`
- `.env` and all credential/token files

## Validation ladder

1. Syntax/type or pure unit check closest to the edit.
2. Focused area test through `scripts/check.ps1`.
3. Frontend production build for cross-cutting TypeScript/UI changes.
4. Broader backend suite only for shared models, migrations, auth, or release validation.
5. E2E only when user-visible flows or browser integration changed.

Keep command output bounded. On failure, report the failing test, exception, and last relevant lines rather than the entire log.
