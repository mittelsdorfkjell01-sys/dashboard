import { WIND_BINS } from "../lib/windScale";
import { FIELD_LAYER_STYLES } from "../weather-map/fieldColor";

export type RGB = [number, number, number];
type Stop = readonly [number, RGB];

const hex = (value: string): RGB => {
  const n = Number.parseInt(value.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

/**
 * The map's wind colours flow (2026-11-20, asked for against the discrete
 * house bins of 2026-11-16): a continuous ramp whose anchors ARE the house
 * bin colours, placed at each bin's middle — so 18 kn on the map still sits
 * on the same green the bars use, it just no longer steps.
 */
export const WIND_STOPS: Stop[] = WIND_BINS.map((bin) => [
  bin.max === Infinity ? bin.min + 5 : (bin.min + bin.max) / 2,
  hex(bin.hex),
] as const);
WIND_STOPS.unshift([0, hex(WIND_BINS[0].hex)]);
WIND_STOPS.push([45, [150, 52, 62]]);

/**
 * The map's wave colours (2026-11-21, "nicht so dunkel, sondern wie die
 * Windkarte bei 5 Knoten — dieses Graublau"): a calm sea starts on the SAME
 * grey-blue the wind ramp shows at 5 kn instead of the shared ramp's deep
 * blue and stays grey-blue to ~1 m; colour (teal → green → yellow → orange)
 * only begins above that. Map-local — the shared
 * ramp (weather-map/fieldColor.ts) stays as it is for the embedded map.
 */
const SHARED_WAVE_STOPS: Stop[] = (FIELD_LAYER_STYLES.waves.stops as unknown as Array<readonly [number, readonly number[]]>)
  .map(([value, color]) => [value, [color[0], color[1], color[2]]] as const);
const shared = (metres: number) => ramp(SHARED_WAVE_STOPS, metres);
export const WAVE_STOPS: Stop[] = [
  [0, ramp(WIND_STOPS, 5)],
  [0.75, ramp(WIND_STOPS, 7.5)],
  [1.5, shared(1)],
  [2.5, shared(2)],
  [4, shared(4)],
  [6, shared(6)],
  [10, shared(10)],
];

export function ramp(stops: readonly Stop[], value: number): RGB {
  if (!Number.isFinite(value) || value <= stops[0][0]) return [...stops[0][1]] as RGB;
  for (let index = 1; index < stops.length; index += 1) {
    const [upper, top] = stops[index];
    if (value > upper) continue;
    const [lower, bottom] = stops[index - 1];
    const f = (value - lower) / (upper - lower || 1);
    return [0, 1, 2].map((c) => Math.round(bottom[c] + (top[c] - bottom[c]) * f)) as RGB;
  }
  return [...stops[stops.length - 1][1]] as RGB;
}

export const windRgb = (knots: number) => ramp(WIND_STOPS, knots);
export const waveRgb = (metres: number) => ramp(WAVE_STOPS, metres);
export const css = (c: RGB) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;

/**
 * Opacity 0–255. Wind covers land and sea alike, a touch stronger for a gale.
 * Waves get MORE intense the bigger the sea ("wo viele Wellen sind, soll der
 * Farbton intensiver sein"): a ripple is a veil, a big swell is solid colour.
 * The dark ground carries more colour than the light one before it reads as
 * muddy, so the dark ramp sits higher.
 */
// 2026-11-21 ("die Karte ist nicht gut sichtbar … Wellen-Kontrast auf 50 %"):
// both ramps lowered so coastlines, places and land stay readable through the
// colour; the wave field covers at most 50 % (was ~90 %).
export function windAlpha(knots: number, dark: boolean): number {
  const share = Math.min(1, Math.max(0, knots) / 35);
  return Math.round(dark ? 90 + share * 70 : 55 + share * 65);
}
export function waveAlpha(metres: number, dark: boolean): number {
  const share = Math.min(1, Math.sqrt(Math.max(0, metres) / 4));
  return Math.round(dark ? 35 + share * 93 : 25 + share * 103);
}
