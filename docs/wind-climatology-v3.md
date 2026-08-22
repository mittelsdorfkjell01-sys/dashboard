# Wind climatology V3 — shadow specification

Status: phases 1–3, shadow only. V2 remains the public contract.

## Product question and fixed parameters

V3 answers: “How likely is it in this seasonal week, at this spot, to get usable wind sessions regularly inside the selected wind window?” It does not pool twenty years of qualifying daylight hours as V2 does.

- Source: Open-Meteo Historical Weather API, ERA5, hourly 10 m wind.
- Period: latest twenty fully completed calendar years.
- Default window: `15 <= speed < 20 kt`.
- Future variants: integer lower bounds 5–40 kt; integer upper bounds through 40 kt and an open upper bound (`null`, displayed as `40+`); step 1 kt.
- Daylight is required. No smoothing, rolling mean, interpolation or visual post-processing is permitted.
- Public V2, region seasons and `best_months` remain unchanged in this phase.

## Definitions

| Term | Binding definition |
|---|---|
| Qualified wind hour | A present, valid hourly ERA5 value in daylight, inside `[min,max)` (or `>= min` for an open upper bound), and—only in `usable` mode—with a present direction inside a reviewed usable sector. |
| Suitable direction | Meteorological **from** direction in at least one canonical reviewed window. Missing direction never matches. |
| Session | At least three consecutive real UTC hours on the same local calendar day. Missing, night, speed/direction mismatch or local midnight ends the run. A longer run is one session. |
| Usable wind day | A local calendar day containing at least one complete session. |
| Successful week-year | A seasonal week in one year containing at least two usable wind days. |
| Valid week-year | At least 95% of its expected real hourly timestamps have the values required by the direction mode. Missing values are not calm wind. |
| Weekly reliability | `successful_years / sample_years * 100`, where the denominator contains valid week-years only. |
| Seasonal week | One of 52 fixed month/day-position buckets; not necessarily an ISO calendar week. |
| Quality | `high` for 18–20 valid years, `limited` for 15–17, `insufficient` below 15. Insufficient weeks expose no publishable reliability. |

## Stable 52-week calendar

Every month/day is projected into leap-year 2000. Let `p` be its zero-based ordinal in that 366-day template. The one-based seasonal week is:

`min(52, floor(p * 52 / 366) + 1)`

February 29 has its own position. Common years simply lack that date; March–December retain the same positions in every year. Every real date maps exactly once, all 52 buckets occur, and bucket sizes are seven or eight calendar days. Expected hours are calculated from local-midnight UTC boundaries, so 23/25-hour DST days are honest. No week is smoothed into a neighbour.

## Time, continuity and daylight

Provider timestamps are Unix instants, validated as unique and strictly increasing, and converted to UTC internally. The spot timezone returned by Open-Meteo determines local day and seasonal week. Session continuity is exactly one real hour in UTC and the same local date. This prevents DST from manufacturing adjacency. Solar elevation at the real spot coordinate uses the existing NOAA-based `app.era5.solar.daylight_mask`; night values remain present for completeness but cannot qualify.

## Direction contract and compatibility

The canonical V3 representation is an ordered JSON array of `{start_deg,end_deg}` meteorological-from windows in `[0,360)`. A start greater than the end wraps through north; disjoint windows are supported.

Canonical source in phases 1–3 is enabled `SpotWeatherSector` rows from an active `SpotWeatherProfile` with `reviewed_at != null`. Legacy `spots.editorial.usable_wind_directions` and `usable_directions` are inventoried but are not silently promoted: existing values lack an explicit review state and include historic compass/list formats. They continue to serve V1/V2 scoring. A later curator migration may copy verified legacy values into reviewed weather sectors. With no reviewed sectors V3 creates only `all`; it never treats missing directions as “all suitable”.

## Weekly metrics

Every selected variant returns exactly 52 unmodified values:

- `sample_years`, `successful_years`, `reliability_percent`;
- probabilities of at least one, two and three usable wind days;
- median usable wind days;
- median, 25th and 75th percentile session hours;
- median longest session;
- quality status.

The primary success threshold is two usable days. Percentiles and medians operate across valid years for that same seasonal week. Values are suppressed when fewer than 15 years qualify.

## Completeness and validation

- Expected counts use all real local-calendar hours in each week-year, including DST.
- `all` completeness requires speed; `usable` completeness requires speed and direction.
- Null, non-finite and absent timestamps reduce completeness and break sessions.
- At least 95% is required. This accepts bounded provider gaps while preventing missing periods from becoming calm wind.
- Exactly twenty completed calendar years, correct units, ERA5 model, grid coordinates, timezone, equal arrays, monotone unique timestamps and direction range are validated before aggregation.

## Storage and API contract

V3 uses additive `wind_climatology_v3_runs`, referencing the existing `WindClimatologyCell`. It is separate from V2 because V2's `annual_aggregates` (48 month sections with pooled 1-kt bins) cannot reconstruct local-day sessions, directions or year regularity.

All valid slider combinations are prepared during the background run. Each selected variant is stored as a small deterministic gzip JSON artifact (`BYTEA`) with SHA-256 in an indexed child row. This avoids large JSONB and avoids decompressing the whole cube for one slider position. Approximately 666 rows without directions (1,332 with `usable`) are bounded by the fixed product range. A request reads and decompresses exactly one artifact. Future shared cache key:

`wind-climatology-v3:{active_run_id}:{min}:{max|plus}:{all|usable}`

The selection request never calls Open-Meteo, starts a job or reprocesses raw history. The artifact is immutable and versioned by its run. The configuration hash includes period, algorithm, spot/requested/actual grid coordinates, canonical direction windows, three-hour session rule, quality thresholds and variant range.

Protected shadow routes:

- `POST /admin/weather/spots/{id}/wind-climatology-v3/runs`
- `GET /admin/weather/spots/{id}/wind-climatology-v3/status`
- `GET /admin/weather/spots/{id}/wind-climatology-v3/variant?min_wind_kn=15&max_wind_kn=20&direction_mode=all` (`open_upper=true` selects the unbounded variant)
- `GET /admin/weather/spots/{id}/wind-climatology-v3/compare`

Only a successful ready run is activated. Enqueue/processing/failure does not deactivate the last successful run. The active partial unique index enforces one active V3 run per spot; the inflight configuration index prevents duplicate equivalent work. Errors and warnings stay internal. Shadow responses state `public_effect: none`.

## Inventory and transition

| Existing element | Decision | Reason |
|---|---|---|
| Open-Meteo/ERA5 client | Extend | Reuse provider/retry path; add validated direction. |
| Twenty completed years | Keep | Binding product decision. |
| Daylight calculation | Keep | Existing UTC solar implementation is suitable. |
| Automatic/manual grid cell | Keep | V3 references `WindClimatologyCell`. |
| V2 1-kt speed bins | Replace for V3 | Bins alone cannot reconstruct sessions; V2 stays intact. |
| `WindClimatologyCell` | Keep | Correct shared spatial selection. |
| `WindClimatologyRun` | Keep as V2 | Public V2 must not change. |
| V2 `annual_aggregates`/`public_data` | Keep as V2 | Not sufficient for V3 semantics. |
| New V3 run/artifact | Add | Versioned session/reliability cube. |
| V1 `spots.climatology` | Unchanged; later remove | Still used by scoring/search/region paths. |
| `spots.best_months` | Unchanged; later reassess | Phase 4 must explicitly migrate region/public meaning. |
| Legacy usable directions | Keep for old paths | Not auto-trusted for V3. |
| Reviewed weather sectors | Extend as canonical V3 source | Explicit review state and wrap-capable degrees. |
| V1 `Era5Job` | Unchanged; later retire | Separate legacy raw-file pipeline. |
| Dashboard operations | Unchanged in phases 1–3 | Only protected API is added. |
| Public V2 endpoint/chart | Unchanged | Required shadow isolation. |
| Region season | Unchanged | Phase 4 decision. |

## Pilot and phase-4 gate

The reproducible read-only pilot is `python -m scripts.wind_climatology_v3_pilot`; configuration is in `config/wind-climatology-v3-pilots.json`. It writes only aggregated reports, never raw history or V3 database rows. See `reports/wind-climatology-v3-pilot.{md,json}`.

Phase 4 requires: reviewed canonical direction sectors for representative spots; accepted artifact/runtime budget; migration applied in a non-production test database; dashboard controls/status; product copy and uncertainty design; explicit decision for region seasons, `best_months`, V1 removal and public V2-to-V3 rollout. A production backfill and deployment require separate approval.

## Phase 4 — administrative dashboard

Phase 4 exposes V3 only inside the authenticated admin bundle. The spot editor contains a compact status summary and links to one V3 detail route. That route owns the 16-sector meteorological-from editor, review status, automatic/manual grid selection, idempotent recalculation and the precomputed 52-week variant preview. The operations page has a separate canonical V3 section; existing `Era5Job` and V1/V2 data are explicitly labelled Legacy.

The direction editor persists through the existing `SpotWeatherProfile` / `SpotWeatherSector` source. Draft sectors do not affect V3. A reviewed effective sector change writes a spot audit entry and enqueues the new configuration; an identical save does neither. Grid changes use the existing `WindClimatologyCell`, write an audit entry and enqueue V3 without deactivating an active run. No additional Phase-4 table is required: migration 0039 remains additive and backward compatible, existing spots default to no reviewed directions and automatic cell selection, and rollback of the dashboard code leaves V1/V2 and stored V3 artifacts intact.

The preview reads one immutable prepared variant per selection. It never requests provider data or starts computation. It rejects artifacts that do not contain exactly 52 weeks and hides a filtered comparison if `usable` would increase reliability or session hours over `all`.

Phase 4 does not decide region seasons, `best_months`, V1 removal or the public V2-to-V3 rollout. Those remain explicit later-phase product decisions. It also does not deploy, migrate production, run a catalogue backfill or add all-spots worker infrastructure.
