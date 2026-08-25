# Map redesign — backend gaps (Editorial Marine Intelligence)

Companion to [`weather-waves-contract.md`](weather-waves-contract.md), which already documents the target
contract precisely. This file is the **frontend-facing gap list**: what the new map/spot/dashboard UI needs,
what exists today, and what has to be built before the corresponding UI layer can leave its "not available"
state. Written after a code-level audit (not a docs read) on 2026-08-24, ahead of the map redesign work.

Severity: 🔴 blocks a whole UI mode · 🟡 degrades a mode · ⚪ nice-to-have polish.

## 🔴 1. Spatial wind/wave field tiles

**UI need:** Phase 4/5 spatial wind and wave layers (colour fields, streamlines, isolines) on the overview map.

**Current state:** `GET /weather-fields/{wind,waves}` (`app/api/weather_fields.py`) unconditionally returns
`FieldAvailability(enabled=False)` — "No licensed gridded provider and publication snapshot are configured."
`app/spatial_fields/contracts.py` defines the manifest shape (`FieldManifest`, `FieldLayer`, u/v pairing,
bounds/zoom/format/units/scaling/quality/attribution/processing version) but there is no producer, no storage,
no CDN wiring, and no code path that ever populates a real `tile_url_template`.

**What's needed to ship:**
- A licensed gridded wind/wave provider (Copernicus Marine is namechecked as "planned" in the contract doc,
  not contracted).
- A tile/PNG-or-vector production pipeline against `weather-field-v1`, with credentials, storage/CDN, and an
  operating-cost decision (explicitly called out as unresolved in the contract doc).
- An `active_manifest` write path so `GET /weather-fields/wind` can return `enabled=True` for real.

**UI decision until then:** Wind/Wave map modes render **point data only** (per-spot markers + inspector).
No spatial colour field, no streamlines. The mode switcher itself stays enabled (point data is real and
useful); only the spatial-field sub-layer toggle is absent, not faked as a disabled button — it simply isn't
offered, since offering a control for a layer that can never activate is worse than not showing it.

## 🔴 2. Nearshore / surf-break engine

**UI need:** Phase 3/6 "Brandung" (surf) mode — breaking probability band, likely break zone, peel angle,
phase/group speed, incidence angle to coast normal.

**Current state:** `app/nearshore/contracts.py` defines `NearshoreInput`/`NearshoreOutput` and a
`NearshoreEngine` `Protocol` — **zero implementing classes exist anywhere in `app/`.**
`GET /weather-fields/nearshore` always reports the gate unpassed ("bathymetry, model and holdout validation
gates"). `app/forecast/shadow.py` has a real, working `coastline_normals()` (PCA-based tangent/normal
extraction from a water-mask raster) but it is wired only into the internal wind-shadow geodata pipeline
(`backfill_plan.py`, `shadow_service.py`) — never into a public nearshore/surf output, and it computes terrain
shelter geometry, not wave-breaking geometry.

**What's needed to ship:**
- A `NearshoreEngine` implementation (breaking-probability + likely-break-zone + peel/incidence angle from
  offshore wave state + versioned bathymetry + coastline).
- A bathymetry source better than "global ~100 m" — the contract doc explicitly disqualifies that resolution
  as "not classified as surf-break accurate."
- Pilot-spot validation against withheld observations before any spot's surf layer can publish (per the
  quality-levels section of the contract doc).

**UI decision until then:** The "Brandung" mode exists in the mode switcher (so users know it's a planned
capability) but is permanently disabled with a one-line reason ("Kein validiertes Nearshore-Modell für diesen
Spot"), everywhere, for every spot — never conditionally per-spot, because no spot has a real implementation to
be conditional on yet. No breaking line, band, or angle is ever drawn from a coast-normal-minus-wind-direction
approximation — the task's non-negotiables explicitly forbid deriving coastline/breaking geometry from
wind/wave direction as a substitute.

## 🟡 3. Wind u/v vector export

**UI need:** Streamline/particle rendering (once field tiles exist, gap 1) needs true vector components, not
just scalar speed+direction, to avoid re-deriving flow from a single angle.

**Current state:** `u`/`v` exist in the *internal* consensus computation (`app.weather.vectors.wind_to_uv`) and
in the *unbuilt* `FieldLayer.variable` enum (`wind_u`/`wind_v`) — never on `CurrentConditions`/`ForecastHour`.

**What's needed to ship:** Add `wind_u_ms`/`wind_v_ms` to the public point schema (`app/schemas/live.py`) — this
one is cheap (data already exists internally) and worth doing independent of gap 1, since it also lets the
point-only wind marker draw a slightly more honest arrow (todo: confirm whether the current scalar `dir` is
already vector-consistent enough that this is purely a nice-to-have for point rendering — likely yes, this
mainly matters for future field rendering).

## 🟡 4. `spatial_resolution_km` always null

**Current state:** The field exists on `ValueProvenance` but every write site (`app/live/service.py:394,704`)
hardcodes `None`. The provenance/inspector UI (Phase 7) has a field for this and will simply omit the row —
correct behaviour per the "no placeholder values" rule — but this is a real, fixable gap: the code has the
model resolution available at fetch time (Open-Meteo model docs list per-model grid spacing) and just isn't
threading it through.

**What's needed to ship:** Populate a static per-model resolution lookup (models are a known, small enum) at
the two write sites. Small, low-risk backend change — flagged here rather than silently added as a "small
required type/integration fix" during the frontend work, per the instruction to document rather than
opportunistically patch backend gaps.

## 🟡 5. Wave component population unverified

**Current state:** `WaveComponentsRead` (total_wave/wind_sea/primary_swell/secondary_swell) is fully specified
in the schema and *documented* as the canonical shape in the contract doc, but the audit did not trace whether
`_merge_hours`/`_marine_for_spot` in `app/live/service.py` populate all four sub-objects at runtime, or only
the legacy flat `swell`/`period`/`swell_dir` trio (with `waves` left null). **Must be confirmed with a live
response before the Wave-mode inspector commits to showing four separate readings** — if only primary swell is
actually populated, the UI shows total/wind-sea as "nicht verfügbar" rather than implying a false level of
decomposition.

## 🟡 6. No public station-list endpoint

**Current state:** Station measurements (gap-free — `WeatherStation`/`WeatherObservation` are real and
populate `LiveConditionsRead.measurement`) are only reachable nested inside a per-spot `/live` call. There is
no `GET /stations` or map-wide station listing.

**Impact on UI:** The overview map cannot show "these N spots have a live station reading right now" as its
own layer/filter without either (a) fetching `/live` per visible spot (expensive, defeats clustering) or (b) a
dedicated lightweight endpoint. Flagging as a gap rather than doing N+1 fetches from the frontend.

## ⚪ 7. Internal diagnostics dropped before the HTTP boundary

`app/live/service.py` computes `calibrated`, `model_run_quality`, `physics_version` into an `internal` dict
that Pydantic (`extra="ignore"` default, no `model_config` override anywhere in `app/schemas/live.py`) silently
strips before the response. `calibrated` already has a *separate* public top-level duplicate on
`ForecastSeriesRead`, so this is low-severity — noted for completeness, not blocking any UI phase.

## 🟡 8. No typical/prevailing wind direction field — and a mislabeling this uncovered

**Found while building the new spot map (Phase 6).** `frontend/src/lib/adapt.ts` mapped the backend's `facing`
field ("Strandausrichtung"/beach orientation — admin-set, `app/models/spot.py:77`, real and non-derived) to the
frontend's `windDir` property. `facing` is a **coastal bearing**, not a wind direction — the two were being
conflated exactly like the non-negotiables the redesign brief calls out ("keine Küstenrichtung aus
Wind-/Wellenrichtung"), just in the opposite direction (a coast value presented as a wind value). Fixed as part
of this work: `adapt.ts` now maps `facing` to the (already-existing, previously always-`undefined`) `coast`
field instead, and `windDir` is left unset.

**Consequence:** there is currently **no backend field for a typical/prevailing wind direction** at all — only
`typical_wind_kt` (speed) exists per spot. The "Windrichtung · 52 W" wind-rose module on the spot page
(`WindRose`, fed by `spot.windDir`) now always shows its empty state, correctly, rather than the beach bearing
it was silently showing before. Two ways forward: add a real typical-direction field (e.g. derived from the
wind-climatology histogram's dominant direction bucket), or retire the module — both are product decisions, not
something to guess at from the frontend.

## Summary for planning

| Gap | Blocks | Effort class |
|---|---|---|
| Spatial wind/wave tiles | Wind/Wave spatial layers | Large — new provider contract + pipeline |
| Nearshore engine | Brandung mode entirely | Large — new model + bathymetry sourcing + validation |
| Wind u/v export | Future field rendering only | Small |
| `spatial_resolution_km` | Inspector completeness | Small |
| Wave component population | Wave-mode inspector accuracy | Verification, then maybe small |
| Station-list endpoint | Map-wide "live station" filter | Small–Medium |
| Internal diagnostics dropped | Nothing user-facing | Trivial, optional |
| Typical wind direction field | WindRose module (currently always empty) | Small–Medium — needs a real data source decision |

The map redesign proceeds with point-data-only Wind/Wave modes and a permanently-disabled Brandung mode until
the two 🔴 items are resourced. No frontend workaround substitutes for them.
