import type { SpotOrigin } from "./api";

/** The one spot colour the pins and dots share (see publicMap's SPOT_DOT_COLOR
 *  for the flat map discs — the teardrop keeps the orange house pin). */
export const SPOT_PIN_COLOR = "#E0823C";

export const SPOT_PIN_SIZE: [number, number] = [30, 38];
/** Tip of the teardrop — the anchor every Leaflet marker using it needs. */
export const SPOT_PIN_ANCHOR: [number, number] = [15, 38];

/**
 * The orange teardrop pin, in one place instead of a copy per map.
 *
 * `origin` varies nothing but the fill: an editorial spot is the filled pin
 * we have always drawn, a community spot the same shape left open (white
 * body, the pin colour as its outline). That is authorship, not a quality
 * tier — a community spot passed the same review — so neither variant adds a
 * colour, a size or a second glyph.
 *
 * Callers that are not showing a published spot (the admin position editors)
 * simply omit `origin` and get the filled pin.
 */
export function spotPinSvg(origin: SpotOrigin = "editorial"): string {
  const community = origin === "community";
  const body = community ? "#ffffff" : SPOT_PIN_COLOR;
  const outline = community ? SPOT_PIN_COLOR : "#ffffff";
  const dot = community ? SPOT_PIN_COLOR : "#ffffff";
  return `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z" fill="${body}" stroke="${outline}" stroke-width="1.4"/>
  <circle cx="12" cy="10.5" r="3.4" fill="${dot}"/>
</svg>`;
}

/** Visible diameter of the spot mark on the Spot-Info map, ring included
 *  (the 16px editorial dot plus its 2px ring) — what the place pins keep
 *  clear of. */
export const SPOT_DOT_SIZE = 20;

/** The house mark (lib/icons EditorialMarkIcon) as markup, for the DOM marker. */
const EDITORIAL_MARK_PATH =
  "M12 2.5c4 0 6.7 2.7 6.7 7.3 0 4.7-3.4 9.9-6.7 12.7-3.3-2.8-6.7-8-6.7-12.7 0-4.6 2.7-7.3 6.7-7.3Zm0 4.8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z";

export type SpotDotVariant = "plain" | "editorial" | "community";

/** Same rule as /map's SpotMarks: origins are marked only once both exist. */
export function spotDotVariant(origin: SpotOrigin | undefined, originsMixed: boolean): SpotDotVariant {
  if (!originsMixed) return "plain";
  return origin === "community" ? "community" : "editorial";
}

/**
 * The spot mark of the Spot-Info map (2026-11-22): the same small dot as the
 * public map (/map, `.swd-pm-dot`) — 12px in the ink of the theme with a ring
 * of its opposite (white dot on the dark map, dark dot on the light one),
 * 16px with the house mark for an editorial spot, open for a community spot.
 * Before, it was a 32px orange dot in a peach halo, a second spot language.
 * Colours come from map.css (`--map-dot`, `--map-dot-ring`).
 */
export function spotDotHtml(variant: SpotDotVariant): string {
  const mark = variant === "editorial"
    ? `<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" clip-rule="evenodd" d="${EDITORIAL_MARK_PATH}"/></svg>`
    : "";
  return `<span class="swd-locator-dot is-${variant}" aria-hidden="true">${mark}</span>`;
}
