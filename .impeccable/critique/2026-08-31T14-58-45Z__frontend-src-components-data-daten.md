---
target: Spot Daten page components
total_score: 23
max_score: 36
na_heuristics: 10
p0_count: 0
p1_count: 3
timestamp: 2026-08-31T14-58-45Z
slug: frontend-src-components-data-daten
---
## Design Health Score (Operate surface)

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Selected-hour highlight is `bg-ink/[0.06]` — ~invisible on near-black; the whole page syncs to a selection nobody can see. |
| 2 | Match System / Real World | 3 | Weather vocabulary + compass are natural; degree glyph is dropped everywhere (`21C`, `↑ 19C`). |
| 3 | User Control and Freedom | 3 | Pointer + keyboard selection, auto-reset-to-now on leave. Solid. |
| 4 | Consistency and Standards | 2 | 3–4 un-tokenized blues (#4F97D8, #5FA8C8, #5B7A99, #8FC4E6), two oranges (#E7A33A vs token #E7883A), inline `fontSize:9/10/11` bypassing the data-* type tokens, only one of five modules gets a card. |
| 5 | Error Prevention | 3 | Read-only data surface; little to prevent. |
| 6 | Recognition Rather Than Recall | 3 | Uppercase row/metric labels are all visible; good. |
| 7 | Flexibility and Efficiency | 2 | Horizontal scroll + focusable strip, but no visible unit affordance on the surface itself. |
| 8 | Aesthetic and Minimalist Design | 2 | Restrained, but everything floats on one flat black field with no grouping surfaces; the CompassDial's near-white disc is the single loudest object on the page — a hierarchy inversion. |
| 9 | Error Recovery | 3 | Plain-German empty states. |
| 10 | Help and Documentation | n/a | Instrument dashboard; no docs expected. |
| **Total** | | **23/36** | **Acceptable (64%)** |

## Design Specificity Verdict

**Strongly product-specific.** This is a bespoke weather instrument — hand-drawn meteogram strip, Catmull-Rom temperature curve with an interpolated "reveal", wave/wind/precip bars on a shared column grid, a sun-position arc, a rotating compass dial, all wired to one shared `SpotDataScope` selection. Nothing here is a generic dashboard template; the composition is authored for surf/wind forecasting. The gap is **execution consistency**, not specificity: a genuinely characterful layout is undercut by an unconsolidated color/type system and a lack of surface material.

**Deterministic scan:** `detect.mjs` over `frontend/src/components/data/daten` returned `[]` (clean) — no mechanical anti-patterns. Every issue below is a judgment call the detector can't see.

## Overall Impression

The bones are excellent and must not move (per brief: wireframe + content locked). What holds the page back from reading as a crisp instrument is three visual-material problems, all fixable without touching layout: (1) no grouping surfaces — five data modules bleed together on one black plane; (2) a fragmented accent-color system with 3–4 near-duplicate blues and two oranges; (3) a hierarchy inversion where the secondary compass disc is brighter than the hero temperature. Fix those and the same wireframe reads twice as fast.

## What's Working

- **The meteogram is real craft.** Fitted temperature bounds, smooth beziers, a shared column grid across wave/weather/temp/wind/direction/time, cursor-interpolated readout. This is the page's signature and it earns it.
- **Restraint + tabular-nums discipline.** Uppercase tracked micro-labels and consistent `tabular-nums` give it a legitimate instrument feel; numbers don't jitter.
- **Warm-neutral dark palette.** The `#0A0C0E` ground with `#F3F0EA` warm ink avoids the cold blue-gray cliché and keeps a faint editorial warmth.

## Priority Issues

**[P1] No grouping surfaces — the whole page is one flat black field.**
Only the wind-months module sits in a bordered card; the meteogram, today-summary, 8-day grid, and map+wind band float directly on `#0A0C0E` separated by whitespace alone. The eye has nothing to land on, so a data-dense page reads as one undifferentiated wall.
*Fix (wireframe-safe):* wrap each existing section group in a subtle instrument panel — `bg-band` (#14181C) or `--sw-surface` (#12161A), `border border-line`, `rounded-2xl`, consistent internal padding — at the exact positions/sizes they already occupy. Same wireframe, now with scannable containers. Optionally keep the meteogram edge-to-edge as the hero and panel the rest.
*Command:* `$impeccable layout`

**[P1] Fragmented data-color system — 3–4 blues, 2 oranges, none tokenized.**
Temperature line, forecast-low, precip, and rain glyph all use `#4F97D8`; the defined teal token is `#5FA8C8`; wave bars are `#5B7A99`; snow `#8FC4E6`; sun is `#E7A33A` while the orange token is `#E7883A`. These are eyeballed one-offs, not a system, so the data doesn't encode meaning consistently (is blue "temperature" or "water" or "cold"?).
*Fix:* define a small set of named data tokens in `daten-theme.css` (e.g. `--data-temp`, `--data-water`, `--data-wind`, `--data-sun`, `--data-cold`) and route every hardcoded hex through them. Decide one blue = one meaning. Visually near-identical, systemically night-and-day.
*Command:* `$impeccable colorize`

**[P1] Hierarchy inversion — the CompassDial is the brightest thing on the page.**
`CompassDial` hardcodes a near-white `#E9E9EA` filled disc with a `#15181C` arrow. On the near-black canvas this secondary wind-direction widget out-shouts the 56px hero temperature and the meteogram. Attention lands in the wrong corner.
*Fix:* invert its material to match the instrument — dark disc (`--sw-surface`), hairline `--sw-line` ring, ticks in `--sw-muted`, and the arrow in the shared wind/`--data-wind` accent so it belongs to the same family as the wind bars. Same size and position.
*Command:* `$impeccable quieter`

**[P2] Weak data-ink contrast on the primary bars.**
Wave bars (`#5B7A99`) sit only a hair above the black ground, and axis/unit micro-type is a scatter of raw `fontSize:9/10/11` in muted gray — small enough to strain at the bottom of the AA range. For a "good data optics" goal the marks that carry the data should read first.
*Fix:* lift bar fills toward their tokenized accents, standardize all chart micro-type on the existing `data-caption`/`data-value` tokens (drop the inline px), and give bars a consistent min-legible height/weight.
*Command:* `$impeccable typeset` then `$impeccable colorize`

**[P2] Selection feedback is nearly invisible.**
The selected-hour column highlight is `bg-ink/[0.06]` (6% white on black). The entire page reacts to this selection, yet the user can't see which hour is active.
*Fix:* raise the highlight to a legible band (a stronger ink tint or a `--data-wind`/teal-tinted column + a top tick), and strengthen the marker dot/readout so "what am I looking at" is obvious.
*Command:* `$impeccable colorize`

## Persona Red Flags

**Alex (Power User / data-heavy):** Scans for the active hour to compare across modules — the 6%-white selection band gives almost no anchor, so cross-referencing the meteogram against the sidebar means guessing. Micro-type at 9px slows a fast read.

**Sam (Accessibility):** Hi/Lo temps distinguished by color alone (ink vs `#4F97D8`) with no non-color cue. 9–10px muted-gray axis labels on near-black hover at the AA floor. The strip is keyboard-focusable (good), but the selected state it exposes is visually near-absent.

## Minor Observations

- Degree glyph dropped everywhere (`21C`, `↑ 19C`, `GEFÜHLT 18 C`) — a units-typography fix, though it brushes against the "no content change" line, so flagged for your call.
- Two radii tokens (`2xl`/`3xl`) both resolve to 8px — harmless, but the panels added in P1 should pick one name.
- `color-scheme: dark` is set on `.daten-dark` (good) — keep that when panels are added so form controls/scrollbars stay dark.

## Questions to Consider

- What if the meteogram stayed edge-to-edge as the hero while everything below sat in quiet instrument panels — would that sharpen the "one instrument, several gauges" read?
- If exactly one blue meant "temperature" and one meant "water," how much faster would the meteogram parse?
- What would the page feel like if the brightest pixel were always the hero number or the active selection — never a dial in the corner?
