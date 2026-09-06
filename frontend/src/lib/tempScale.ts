// Shared absolute temperature → colour scale (°C), used to tint the forecast
// high/low readouts. "Absolute" means a given temperature always maps to the
// same colour regardless of the visible day window, so colours stay comparable
// across days and weeks (no per-window rescaling). Mirrors windScale.ts as the
// single source of truth for this data encoding.
//
// The repo has no prior temperature colour token: --sw-data-temp is a single
// sky-blue hue for the meteogram temperature LINE, not a cool→warm scale — so
// the scale is defined here rather than reused from the theme tokens.

export type TempStop = [celsius: number, rgb: [number, number, number]];

// Stops deliberately reach past the realistic data window so values are covered
// without clamping artefacts. Tuned for legibility on the dark Daten canvas:
// the cool end stays light enough to read against the near-black ground, the
// warm end runs into amber/orange (the same family as --sw-orange).
export const TEMP_STOPS: TempStop[] = [
  [8, [127, 155, 196]], // cold   – cool blue-slate
  [14, [147, 167, 189]], // cool  – slate
  [20, [185, 194, 204]], // fresh – cool grey
  [24, [230, 228, 221]], // neutral – warm white
  [28, [240, 196, 116]], // warm
  [32, [242, 169, 74]], // amber
  [36, [238, 143, 60]], // hot
];

// The coolest tone on the scale (its cold end), for readouts that should always
// read as "cool" regardless of their value — e.g. the forecast daily low, which
// is always shown in this colour so a low never looks warm even on a hot day.
export const COLDEST_TEMP_COLOR = `rgb(${TEMP_STOPS[0][1][0]}, ${TEMP_STOPS[0][1][1]}, ${TEMP_STOPS[0][1][2]})`;

/**
 * Map a temperature in °C to its colour on the absolute scale, linearly
 * interpolating between the two surrounding stops and clamping outside the
 * range so extreme values still resolve to the coolest / hottest tone.
 */
export function tempColor(celsius: number): string {
  const stops = TEMP_STOPS;
  const clamped = Math.max(stops[0][0], Math.min(stops[stops.length - 1][0], celsius));
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (clamped <= t1) {
      const k = (clamped - t0) / (t1 - t0);
      const rgb = c0.map((value, channel) => Math.round(value + (c1[channel] - value) * k));
      return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
    }
  }
  const [r, g, b] = stops[stops.length - 1][1];
  return `rgb(${r}, ${g}, ${b})`;
}
