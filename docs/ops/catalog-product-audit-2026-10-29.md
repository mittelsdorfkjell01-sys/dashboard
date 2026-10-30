# Catalogue and product audit — 2026-10-29

This is an evidence snapshot, not a product concept. Reproduce catalogue counts
with:

```powershell
python -m scripts.catalog_content_audit --api-base https://surfwinddata.com/api
python -m scripts.backtest_status
```

Both commands are read-only. The catalogue audit uses public GET endpoints and
does not open a database connection.

## Revision and access boundary

- Active worktree: `codex/launch-readiness-2026-10-27` at
  `05394e4a7f5e191a39892fb868f70ec49e7a6fd1`.
- Default branch: `origin/main` at
  `0e15da6a70fa8f70f96cd6e5fdf037005fd49c85`.
- The active branch is one commit ahead of `origin/main`.
- Pre-existing worktree changes under `.impeccable/`, `AGENTS.md`, and `.vscode/`
  were not changed by this work.
- Public catalogue and detail APIs were reachable read-only. Their deployed
  revision could not be proven, so runtime observations are not attributed to a
  commit.
- No production database or authenticated admin endpoint was queried. Draft and
  moderation counts in production are therefore unknown.

## Executable product inventory

| Area | Status | Evidence |
|---|---|---|
| Public spots, map and detail | complete baseline | `app/api/spots.py`, `frontend/src/pages/MapView.tsx`, `frontend/src/pages/SpotDetail.tsx` |
| Regions and search | complete baseline | `app/api/regions.py`, `app/api/search.py`, `frontend/src/pages/SearchResults.tsx` |
| Rider profile and travel radius | implemented | `app/models/rider.py`, `app/account/rider.py`, `frontend/src/pages/account/MeinSetup.tsx` |
| Recommendations | implemented; forecast quality is a separate gate | `app/api/recommendations.py`, `app/recommendations/service.py` |
| Favorites | implemented end to end | `app/models/favorite.py`, `app/api/account.py`, `frontend/src/pages/account/Favoriten.tsx` |
| Check-in | durable visit plus optional outcome/notes | `app/models/spot_visit.py`, `app/api/account.py`, `frontend/src/components/VisitedButton.tsx` |
| Visit history | implemented | `frontend/src/pages/account/BesuchteSpots.tsx` |
| User alerts | models only / incomplete flow | `app/models/watch.py`, `app/models/notification.py` |
| Community submission and moderation | implemented; approval creates a draft | `app/api/community.py`, `app/admin/moderation.py` |
| Stored multi-day trip | implemented after audit | `app/models/trip.py`, `app/account/trips.py`, `frontend/src/pages/account/Reiseplaner.tsx` |
| Forecast verification | harness and gates exist; no current all-product pass | `app/weather/verification.py`, `app/weather/live_wind_verification.py` |

## Catalogue counts kept separate

### Repository seed definitions

- 51 unique spot definitions: 11 `published`, 40 `draft`.
- 28 unique regions: 3 core plus 25 Europe definitions.
- Sport memberships (multi-membership): 28 kitesurf, 26 windsurf, 25 surf,
  12 wing.
- Existing database rows are skipped by the seed path, so these numbers are not
  a live-state assertion.

### Public runtime

- 46 spots, all returned as `published` and `editorial`.
- 30 published regions.
- Sport memberships (multi-membership): 32 kitesurf, 29 windsurf, 22 surf,
  19 wing.
- Production draft, pending community and rejected counts: **unknown**.

Public spot content coverage:

| Field | Count / 46 |
|---|---:|
| Description | 46 |
| Image with licence | 46 |
| Origin | 46 |
| Variant conditions | 32 |
| Editorial tide | 18 |
| Usable wind directions | 17 |
| Safety notice | 0 |
| Structured entry / launch area | 0 / 0 |
| Structured hazards / local rules | 0 / 0 |
| Editorial content source / last checked | 0 / 0 |

Public region coverage:

- 30/30 without a season object.
- 28 placeholder or example image URLs; one region without an image.
- Two without a description.
- Twenty single-spot regions and one zero-spot region (`lanzarote`).

## Confirmed trust findings

- `peniche-supertubos` publicly describes Ria Formosa, Tavira and Monte Gordo.
  This is a confirmed geography/copy conflict. The repository's Europe seed is
  already a different draft record; changing the seed would not repair the
  existing production row because seeding skips existing slugs.
- The deterministic audit flags eleven additional descriptions that mention
  beginners while structured `level` does not include `beginner`. These are
  review candidates, not automatic corrections: the surrounding text may refer
  to a neighboring area or qualified conditions.
- Migration `0086_spot_safety_notices` and the active branch contain 46 initial
  safety notices, but the public API returned zero. Deployment/migration state
  must be verified before treating the branch feature as live.

## Forecast evidence boundary

- Europe Wind Measurement is still active in shadow mode. A session check on
  2026-10-30 confirmed the configured end remains
  `2026-11-02T15:17:54+00:00`.
- Weather Forecast Verification, Weather Shadow Collector, Tide worker and
  LiveWind Shadow Operations most recently reported `skipped`.
- Wind forecast verification code scores raw forecasts by `0–48h`, `49–120h`
  and `121–240h` lead buckets. That implementation is not a passed result.
- No equivalent observation-based wave-accuracy result or tide-forecast
  accuracy result was found. Technical continuity and provider integrity gates
  are not accuracy evidence.

Therefore automated trip changes, guaranteed-day wording and forecast-triggered
alerts remain blocked. Manual planning, editorial content work and verified
climatology explanations do not depend on those gates.

## Release and rollback boundary

- No live data was changed by this audit.
- The known Supertubos row should be corrected through the authenticated admin
  workflow with a reviewed source, or temporarily unpublished. Do not run seed
  data against production as a repair mechanism.
- Before release, run the public audit again and compare the JSON result. A
  content repair is accepted only when the geography conflict disappears and
  the reviewed record retains its audit history.
- The code-only Sprint 1 warning can be rolled back by reverting
  `app/admin/content_review.py` plus its readiness/UI integrations. It does not
  change stored data.

## Implementation update — 2026-10-30

- Migrations `0087`–`0093` add field-level content provenance, region content
  review, manual trips, durable visits and fail-closed decision-support
  evidence. They remain pending production migration at this snapshot.
- The Supertubos repair is migration `0092`: exact UUID, slug and old-copy
  guards; a reviewed Turismo de Portugal description source; downgrade only
  restores unchanged migration text. The row remains `in_review` until the
  other required claims are sourced.
- The manual planner supports up to 31 days, one main spot plus ordered manual
  alternatives per day, day/travel/accommodation notes, checklist, copying,
  add-from-spot/favourites, content-change markers and a revocable read-only
  link. Private notes are excluded from shared plans by default.
- Visit history persists across reloads and accepts optional outcome/notes.
  Favourites expose a comparison using only stored structured values; unknown
  data remains explicitly unknown.
- Forecast sorting is fail-closed. No wind, wave or tide acceptance policy has
  been approved for this product capability, and thresholds belonging to
  LiveWind or sector correction are deliberately not reused. Catalogue/manual
  ordering is the fallback.
- German/English catalogue infrastructure, switcher, region journey, Q&A,
  planner, visits and favourites are implemented. Full public-site migration is
  still open: `npm --prefix frontend run i18n:report` reports 462 hard-coded
  strings in 97 public files. This is a tracked content/UX remainder, not a
  launch-ready bilingual claim.
- Vercel was checked through its API: `kjellmittelsdorf.de` was removed from the
  team domain inventory; `surfwinddata.com` and
  `dashboardsurfwind.vercel.app` remain verified on their respective projects.
- Verification after the final changes: `scripts/check.ps1 changed` passed;
  375 frontend tests passed; 178 focused backend/database tests passed with the
  local PostGIS and Redis services running.
