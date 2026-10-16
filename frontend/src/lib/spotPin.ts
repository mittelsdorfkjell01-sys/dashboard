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
