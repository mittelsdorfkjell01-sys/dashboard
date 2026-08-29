---
target: Spot Detail Daten-Tab (SpotDetail.tsx + Data-Komponenten)
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-08-25T21-28-45Z
slug: frontend-src-pages-spotdetail-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Good live-region announcements, stale-data badges, `switching` opacity state — but LiveRow has no loading skeleton, unlike every other module. |
| 2 | Match System / Real World | 3 | German labels feel natural; `DirectionCompass`'s "Cross-onshore"/"Sideshore" labels break register by staying in English. |
| 3 | User Control and Freedom | 2 | No visible reset for the climatology custom filter beyond re-picking a preset; tab switching uses `navigate(..., {replace:true})`, so back-button history can skip the tab change. |
| 4 | Consistency and Standards | 3 | Section-header pattern (`text-caption uppercase tracking-wider`) and toggle-pill pattern reused well; but "Tide" appears twice with contradictory meaning (see P2). |
| 5 | Error Prevention | 2 | Climatology silently falls back "usable"→"all" on a 422 with no visible acknowledgment that the user's selection changed. |
| 6 | Recognition Rather Than Recall | 3 | Presets reduce recall burden; but sportMode/windUnit set once in the header silently reorders/reprioritizes cells several screens later with no reminder. |
| 7 | Flexibility and Efficiency | 2 | Deep-linkable climatology selection is a real power-user feature; but no in-page anchor nav across the 7 stacked sections, no shortcut to a synthesized answer. |
| 8 | Aesthetic and Minimalist Design | 3 | Clean divider rhythm per module; but 7 full-width unconditional sections (Meteogram → Map → Compass/Sun/Tide → Weather table → Climatology) trend toward kitchen-sink rather than single-glance minimal. |
| 9 | Error Recovery | 3 | Per-module error states are specific and graceful (map error boundary with external-map fallback, tide fallback copy). |
| 10 | Help and Documentation | 2 | Climatology methodology (ERA5, 3h-session rule, grid resolution) and tide-source attribution are dumped as dense inline captions instead of the `<details>` disclosure pattern already used elsewhere on the same page. |
| **Total** | | **26/40** | **Acceptable — significant improvements needed before users are happy** |

## Design Specificity Verdict

**LLM assessment**: This is not a reskinned generic weather widget set — the domain logic is genuinely authored for Surfwinddata. The tide curve is a deliberate cosine-eased interpolation across real event times rather than a canned sparkline, explicitly built because the API has no absolute-height data. The sun arc is intentionally a separate widget from the tide curve because "a day has one sunrise/sunset... a tide cycle has two highs and two lows, which an arc would misrepresent" (comment in `SunArc.tsx`). The wind-climatology module encodes a genuinely domain-specific metric — probability of "at least two wind days with three connected usable hours" — not a generic average. Where the page slides toward category-interchangeable territory is the surrounding visual chrome: LiveRow's stat grid, toggle pills, and bordered-section rhythm is competent "data dashboard" grammar that could sit unchanged in Windy, a stock ticker, or any analytics panel with only color-token swaps. The specificity lives in the data model and interaction logic, not in the visual language wrapping it.

**Deterministic scan**: `node .claude/skills/impeccable/scripts/detect.mjs --json` was run twice — first against the five originally-named files, then re-run (by me, correcting Assessment B's search miss) against all seven real files including `LiveRow.tsx` and `DirectionCompass.tsx` at their actual path `frontend/src/components/data/`. Both runs: **exit code 0, zero findings** (`[]`). Assessment B independently confirmed the detector is a real, populated rule engine (not a stub) by testing `--no-config` and running it against `Meteogram.tsx`, a file with a pre-existing subjective critique report — also zero findings there. This indicates the regex/static-analysis detector has weak or no coverage for the kind of issues these TSX components actually have (state-driven UX problems like missing loading states, redundant cells, information density) — it is not evidence the page is issue-free, just that this detector's ruleset doesn't reach these problems.

**Correction to Assessment B**: Assessment B reported "`DirectionCompass` and `LiveRow` do not exist in the codebase" — this is false; both exist at `frontend/src/components/data/LiveRow.tsx` and `frontend/src/components/data/DirectionCompass.tsx` (Assessment B's grep scope missed the `data/` subdirectory). I re-ran the detector against the corrected paths myself; the zero-findings result holds regardless.

**Visual overlays**: Not available. No browser automation tool was exposed to either sub-agent this session, so no live-page injection or console-based overlay was possible, and no screenshots were captured. This is a genuine evidence gap in this run — see Run Notes.

## Overall Impression

The Data tab is built by people who understand surf/wind data deeply and refuse to fake metrics the underlying data doesn't support — that discipline shows in the tide curve, the sun arc, and the climatology model. But the page has no synthesized answer to the one question a user actually opens it for: "is today good enough to go out?" Instead it hands over seven independently well-crafted but disconnected modules and expects the user to cross-reference wind speed, direction classification, and historical reliability by scrolling and mentally merging them. The biggest opportunity is architectural, not decorative: promote the synthesis that's implicit in the data (wind + direction classification + reliability) into one headline verdict, and give the loading state of the single highest-stakes module (LiveRow) the same care every other module already has.

## What's Working

1. **`buildTideCurve` in `TidePanel.tsx`** — cosine-eased interpolation across real event times, explicitly designed as "a relative rhythm, not an absolute-height chart" because the API has no height data. Honest, domain-correct design instead of a fabricated metric.
2. **`LocatorMapBoundary`** — a real React error boundary around the map with a graceful, actionable fallback ("Karte momentan nicht verfügbar" + external-map link) instead of a blank crash.
3. **Wind-climatology selection-state layering** (`selectionFromUrl` → `stored` → `normalizeSelection`, with a `directionExplicitRef` guard) — sophisticated, deliberate state-priority handling for a shareable, persistent filter that most dashboards of this complexity get wrong.

## Priority Issues

**[P0] No synthesized go/no-go signal.**
Why it matters: the core task — decide if conditions are good for a session — requires manually cross-referencing LiveRow's wind number, DirectionCompass's onshore/offshore classification, and WindClimatologyModule's historical reliability color, three separate widgets with no synthesis, some of them a full scroll apart.
Fix: add one status line/badge near the top of the Daten tab that pulls from data already computed elsewhere on the page (e.g. "Onshore, 18 kt — typical for this week").
Suggested command: `$impeccable shape` (to design the synthesis view) then `$impeccable layout`.

**[P1] LiveRow has no loading state.**
Why it matters: every other module (Meteogram, SpotMap, WeatherDetailsTable, TidePanel, climatology) shows a pulse/skeleton while loading; LiveRow renders immediately with `live` possibly null, producing a full grid of "-" placeholders indistinguishable from "no data exists here." This is the highest-stakes module on the page (live numbers) and the one place users can't tell loading from empty.
Fix: gate LiveRow on a loading flag with a skeleton matching the pattern already used elsewhere.
Suggested command: `$impeccable harden`.

**[P1] WeekDetail dumps 14 metrics flat with no grouping.**
Why it matters: `WindClimatologyModule.tsx`'s week-detail panel (`rows` array) renders 14 label/value rows simultaneously with zero visual grouping — a hard violation of the ≤4-items-per-group chunking guideline; a first-timer clicking a week bar meets a dense, undifferentiated stat table.
Fix: group into 2–3 labeled clusters (e.g. "Zuverlässigkeit," "Sessiondauer," "Konfidenz") or progressive-disclose the secondary percentile/probability rows behind a "mehr" toggle.
Suggested command: `$impeccable distill`.

**[P2] Redundant, contradictory "Tide" cell in LiveRow.**
Why it matters: LiveRow always renders a "Tide" cell hardcoded to `"-"` in both branches, even though a full `TidePanel` with real data sits lower on the page — the cell can never show a value by construction, trains users to ignore it, and reuses a label that means something different in the two places.
Fix: remove the dead cell, or wire it to a `next.high`/`next.low` countdown.
Suggested command: `$impeccable clarify`.

**[P3] Methodology copy buried as dense inline caption text.**
Why it matters: both TidePanel (FES2022/AVISO+ attribution) and WindClimatologyModule (ERA5, 3-hour session rule, grid resolution — all one paragraph) bury trust-relevant methodology in low-contrast caption prose nobody reads inline, while a `<details>` disclosure pattern already exists elsewhere on the same page (`SpotDetail.tsx`'s "Quellen" block) and isn't reused here.
Fix: move both into the existing `<details>` pattern for consistency and scannability.
Suggested command: `$impeccable clarify`.

## Persona Red Flags

**Alex (Power User)**: Appreciates the URL-shareable climatology filter and the kt/m-s unit toggle, but hits friction immediately at LiveRow's ambiguous loading state (P1) — on a slow connection Alex sees "-" everywhere and may assume the API is down. No in-page anchor navigation exists across the Daten tab's 7 stacked sections, so Alex can't jump straight to climatology or the compass without scrolling past Meteogram and Map first.

**Sam (Accessibility-Dependent)**: Mostly well-served — `aria-live` announces climatology changes, `role="img"` with generated `aria-label` on the tide curve, sun arc, and compass SVGs, `aria-pressed` on toggle/preset buttons, and `min-h-11`/`min-w-11` touch targets are consistent almost everywhere. But the WeekBar buttons in `WindClimatologyModule.tsx` are ~10–12px wide interactive targets inside an `overflow-x-auto` scroller — far below the 44px minimum used by the preset buttons in the same file, a glaring inconsistency for a motor-impaired or touch user trying to select a specific week. LiveRow's grid cells are also plain unlabeled `<div>`s with no semantic list/table structure, despite being the densest data-per-pixel module on the page.

**Casey (Mobile)**: The `[zoom:1] lg:[zoom:0.85]` CSS `zoom` hack in `SpotDetail.tsx` shrinks the desktop layout by 15% using a non-standard property with historically inconsistent cross-browser support and known hit-target offset issues — a fragile choice for a responsiveness mechanism. On mobile, WindClimatologyModule's horizontal week-scroller with ~10px-wide bars inside a horizontally-scrolling container is a well-known scroll-vs-tap interaction trap that will misfire regularly on touchscreens.

## Minor Observations

- `DirectionCompass.tsx`'s `CLASS_LABEL` keeps "Cross-onshore"/"Sideshore"/"Cross-offshore" as untranslated English terms in an otherwise fully German UI.
- `SunArc`'s `localDecimalHour` timezone approximation is explicitly flagged in a code comment as "not a legal/scientific time," but that caveat only reaches users as the vague caption "Näherungswert (±wenige Minuten)."
- `WeekChart` bails with a plain-text `role="alert"` if `weeks.length !== 52`, inconsistent with the styled error states used elsewhere on the page (map error boundary, tide fallback).
- The mechanical detector currently returns zero findings on every file in this component family (including a previously-flagged `Meteogram.tsx`), suggesting its ruleset doesn't reach state/interaction-driven UX issues like the ones above — worth a look independent of this critique.

## Questions to Consider

- If a user has 10 seconds on their phone before paddling out, what single element on this page answers "should I go?" Right now the honest answer is "none — read and mentally combine three separate widgets."
- Why does a dead, always-"-" Tide cell exist in LiveRow at all when a fully-realized TidePanel sits 400px below it — is this leftover scaffolding, and if so, what else on the page is similarly stale?
- The climatology module clearly received the most design care (URL persistence, direction auto-detection, accessible live region) — does LiveRow, the first thing users see and the one module with no loading state, need that same pass applied backward?
