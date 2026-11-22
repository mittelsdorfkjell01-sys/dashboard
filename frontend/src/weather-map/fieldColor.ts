import { WIND_BINS } from "../lib/windScale";

/** "#A9B7C2" → [169, 183, 194]. */
function rgb(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

/**
 * The wind field's colours ARE the house wind scale (lib/windScale.ts) — the
 * same seven discrete bins the forecast bars, the meteogram and the legend
 * use, so 18 kn is the same colour wherever the site draws it.
 *
 * Until 2026-11-16 this file carried a second, continuous ramp of its own
 * (pale blue-grey → light blue → teal → green → yellow → orange). It looked
 * like a weather map, but it meant that the hourly bars inside the map's own
 * forecast sheet coloured 18 kn dark green while the field under them drew it
 * teal — one quantity, two colour languages, in contact on one screen. The
 * bins are deliberately discrete (see windScale.ts): the steps the field now
 * shows are exactly the steps the legend names.
 */
const STOPS = WIND_BINS.map((bin) => [bin.min, rgb(bin.hex)] as const);

export function fieldColor(speedKnots: number): [number, number, number] {
  return binColor(speedKnots);
}

/** The bin a speed falls in — no interpolation between bins, by design. */
function binColor(speedKnots: number): [number, number, number] {
  const value = Math.max(0, speedKnots);
  for (let index = STOPS.length - 1; index >= 0; index -= 1) {
    if (value >= STOPS[index][0]) return [...STOPS[index][1]] as [number, number, number];
  }
  return [...STOPS[0][1]] as [number, number, number];
}

export const FIELD_COLOR_STOPS = STOPS;

export const FIELD_LAYER_STYLES = {
  wind: { label: "Wind", unit: "kn", values: [0, 10, 20, 30, 40], stops: STOPS },
  waves: {
    label: "Wellen", unit: "m", values: [0, 0.5, 1, 2, 4, 8],
    stops: [[0, [52, 91, 160]], [0.5, [47, 139, 181]], [1, [54, 184, 174]], [2, [124, 196, 104]], [4, [225, 194, 72]], [6, [228, 121, 69]], [10, [156, 56, 93]]],
  },
  gust: { label: "Böen", unit: "kn", values: [0, 10, 20, 30, 40], stops: STOPS },
  temperature: {
    label: "Temperatur", unit: "°C", values: [-20, 0, 10, 20, 35],
    stops: [[-30, [64, 78, 156]], [-10, [70, 139, 194]], [0, [166, 216, 225]], [10, [228, 224, 171]], [20, [234, 161, 82]], [30, [202, 78, 70]], [45, [117, 45, 78]]],
  },
  precipitation: {
    label: "Niederschlag (akk.)", unit: "mm", values: [0, 1, 5, 15, 40],
    stops: [[0, [184, 205, 208]], [0.2, [112, 190, 184]], [1, [46, 157, 176]], [5, [45, 103, 168]], [15, [85, 62, 155]], [40, [151, 54, 128]], [100, [88, 31, 76]]],
  },
  pressure: {
    label: "Luftdruck", unit: "hPa", values: [960, 980, 1000, 1020, 1040],
    stops: [[940, [79, 70, 135]], [970, [71, 123, 167]], [990, [99, 173, 166]], [1010, [224, 213, 126]], [1030, [221, 143, 74]], [1060, [171, 69, 66]]],
  },
  clouds: {
    label: "Bewölkung", unit: "%", values: [0, 25, 50, 75, 100],
    stops: [[0, [91, 151, 184]], [25, [136, 177, 194]], [50, [176, 195, 199]], [75, [207, 210, 207]], [100, [237, 235, 228]]],
  },
} as const;

export function layerValue(layer: keyof typeof FIELD_LAYER_STYLES, arrays: Record<string, Float32Array>, index: number): number | undefined {
  if (layer === "wind" || layer === "gust") {
    const u = arrays.wind_u?.[index], v = arrays.wind_v?.[index];
    const value = layer === "gust" ? arrays.wind_gust?.[index] : Math.hypot(u, v);
    return value === undefined ? undefined : value * 1.943844;
  }
  if (layer === "waves") return arrays.total_wave_height?.[index];
  const variable = { temperature: "temperature_2m", precipitation: "precipitation", pressure: "pressure_msl", clouds: "cloud_cover" }[layer];
  return arrays[variable]?.[index];
}

export function layerColor(layer: keyof typeof FIELD_LAYER_STYLES, value: number): [number, number, number] {
  // Wind and gusts are the house scale, and the house scale does not
  // interpolate: a value belongs to a bin, and the bin has one colour.
  if (layer === "wind" || layer === "gust") return binColor(value);
  const stops = FIELD_LAYER_STYLES[layer].stops as readonly (readonly [number, readonly [number, number, number]])[];
  for (let index = 1; index < stops.length; index += 1) {
    const lower = stops[index - 1], upper = stops[index];
    if (value > upper[0]) continue;
    const ratio = Math.max(0, (value - lower[0]) / (upper[0] - lower[0]));
    return [0, 1, 2].map((channel) => Math.round(lower[1][channel] + (upper[1][channel] - lower[1][channel]) * ratio)) as [number, number, number];
  }
  return [...stops[stops.length - 1][1]] as [number, number, number];
}

export function layerOpacity(layer: keyof typeof FIELD_LAYER_STYLES, value: number): number {
  if (layer === "precipitation") {
    if (value <= 0.05) return 0;
    return Math.round(Math.min(170, 40 + Math.log1p(value) * 30));
  }
  if (layer === "clouds") return Math.round(Math.max(0, Math.min(95, value * 0.95)));
  if (layer === "pressure") return 95;
  if (layer === "temperature") return 110;
  if (layer === "waves") return Math.round(175 + Math.min(1, Math.max(0, value) / 6) * 35);
  // Wind and gusts cover the whole map, land as much as water (2026-10-11):
  // the air does not stop at the coast. Calm is drawn lighter than a gale so
  // the map underneath stays readable, and its colour is the pale blue-grey
  // at the foot of the scale — the old violet turned every continent lilac.
  // Lighter overall since 2026-10-12: at 120–215 of 255 the field veiled the
  // ground so thoroughly that the land under it read as blurred; 92–176 was
  // still a touch too much over the pale Positron land, so 72–150 (28–59 %).
  return Math.round(72 + Math.min(1, Math.max(0, value) / 40) * 78);
}
