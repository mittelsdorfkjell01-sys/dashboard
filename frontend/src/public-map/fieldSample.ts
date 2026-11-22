import type { DecodedFieldTile } from "../weather-map/fieldTile";

export const MS_TO_KN = 1.943844;

/** Which part of the sea state the wave mode shows (2026-11-19 redesign). */
export type WaveComponent = "total" | "swell" | "sea";

/**
 * Bilinear sample of every published array at one coordinate — the same maths
 * `FieldSource.sampleValues` uses for the point series, applied to the tiles
 * already on screen. Values are `undefined` where a neighbour has no data, so a
 * coast cell is never half-invented.
 *
 * `nearCoast` (2026-11-21, wave arrows "näher an die Küste"): instead of
 * dropping a point whose four neighbours are not all sea, weight only the sea
 * neighbours — the value of the nearest published sea cells. The caller must
 * then decide with the real coastline (the water mask) whether the point is
 * on water at all.
 */
export function sampleTiles(tiles: DecodedFieldTile[], longitude: number, latitude: number, nearCoast = false): Record<string, number | undefined> | null {
  for (const tile of tiles) {
    const z = tile.header.z;
    const worldX = ((longitude + 180) / 360) * 2 ** z;
    const clamped = Math.max(-85.05112878, Math.min(85.05112878, latitude));
    const worldY = ((1 - Math.asinh(Math.tan((clamped * Math.PI) / 180)) / Math.PI) / 2) * 2 ** z;
    if (Math.floor(worldX) !== tile.header.x || Math.floor(worldY) !== tile.header.y) continue;
    const overlap = tile.header.overlap ?? 0;
    const inner = tile.header.width - overlap * 2;
    const px = overlap + (worldX - tile.header.x) * inner - 0.5;
    const py = overlap + (worldY - tile.header.y) * inner - 0.5;
    const x0 = Math.floor(px), y0 = Math.floor(py), x1 = x0 + 1, y1 = y0 + 1;
    if (x0 < 0 || y0 < 0 || x1 >= tile.header.width || y1 >= tile.header.height) return null;
    const dx = px - x0, dy = py - y0, w = tile.header.width;
    const values: Record<string, number | undefined> = {};
    for (const [name, array] of Object.entries(tile.arrays)) {
      const a = array[y0 * w + x0], b = array[y0 * w + x1], c = array[y1 * w + x0], d = array[y1 * w + x1];
      if (Number.isFinite(a) && Number.isFinite(b) && Number.isFinite(c) && Number.isFinite(d)) {
        values[name] = (a * (1 - dx) + b * dx) * (1 - dy) + (c * (1 - dx) + d * dx) * dy;
      } else if (nearCoast) {
        let sum = 0, weight = 0;
        for (const [value, wgt] of [[a, (1 - dx) * (1 - dy)], [b, dx * (1 - dy)], [c, (1 - dx) * dy], [d, dx * dy]] as const) {
          if (Number.isFinite(value)) { sum += value * (wgt + 1e-3); weight += wgt + 1e-3; }
        }
        values[name] = weight > 0 ? sum / weight : undefined;
      } else values[name] = undefined;
    }
    return values;
  }
  return null;
}

export interface WindReading { knots: number; gustKnots?: number; /** where the wind goes, screen-free: east/north */ u: number; v: number }
export interface WaveReading { height: number; period?: number; /** unit vector where the waves go: east/north */ dx: number; dy: number }

export function windReading(values: Record<string, number | undefined> | null): WindReading | null {
  if (!values) return null;
  const u = values.wind_u, v = values.wind_v;
  if (u === undefined || v === undefined) return null;
  return { knots: Math.hypot(u, v) * MS_TO_KN, gustKnots: values.wind_gust === undefined ? undefined : values.wind_gust * MS_TO_KN, u, v };
}

/** "from" in degrees → unit vector of travel (east, north). */
function travel(fromDeg: number): { dx: number; dy: number } {
  const to = ((fromDeg + 180) * Math.PI) / 180;
  return { dx: Math.sin(to), dy: Math.cos(to) };
}

/**
 * One wave component at a sampled point. `total` reads the published travel
 * vector (`wave_u`/`wave_v`, whose length is the significant height); swell and
 * wind sea read their own height, period and "from" direction. Anything the
 * publication does not carry is `null` — never estimated from another part.
 */
export function waveReading(values: Record<string, number | undefined> | null, component: WaveComponent): WaveReading | null {
  if (!values) return null;
  if (component === "total") {
    const u = values.wave_u, v = values.wave_v;
    const height = values.total_wave_height ?? (u !== undefined && v !== undefined ? Math.hypot(u, v) : undefined);
    if (height === undefined || u === undefined || v === undefined) return null;
    // The arrow shows where the SWELL comes from (2026-11-21) wherever the
    // publication carries a primary-swell direction; the colour stays the
    // total sea. Without a swell direction it falls back to the mean
    // direction of the whole sea state.
    const swellFrom = values.primary_swell_direction;
    if (swellFrom !== undefined) return { height, period: values.primary_swell_period ?? values.total_wave_period, ...travel(swellFrom) };
    const length = Math.hypot(u, v) || 1;
    return { height, period: values.total_wave_period ?? values.primary_wave_period, dx: u / length, dy: v / length };
  }
  const prefix = component === "swell" ? "primary_swell" : "wind_sea";
  const height = values[`${prefix}_height`], from = values[`${prefix}_direction`];
  if (height === undefined || from === undefined) return null;
  return { height, period: values[`${prefix}_period`], ...travel(from) };
}

/** Compass bearing (0 = north, clockwise) of a travel vector (east, north). */
export function bearingOf(east: number, north: number): number {
  return ((Math.atan2(east, north) * 180) / Math.PI + 360) % 360;
}

const COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
export const compassName = (deg: number) => COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];

/**
 * The colour field reads `total_wave_height` (weather-map/fieldColor.ts). To
 * paint swell or wind sea with the SAME layer and scale, hand it tiles whose
 * height array is the component's — a view, not a copy of the other arrays.
 */
export function tilesForComponent(tiles: DecodedFieldTile[], component: WaveComponent): DecodedFieldTile[] {
  const name = component === "swell" ? "primary_swell_height" : component === "sea" ? "wind_sea_height" : "total_wave_height";
  return tiles.map((tile) => {
    // A blended tile (between two published hours) is one reused buffer whose
    // key never changes; the field layer caches textures by key, so the key
    // has to carry the instant or a scrub would keep painting the old blend.
    const instant = tile.key.endsWith("@blend") ? `@${tile.header.valid_time}` : "";
    if (component === "total") return instant ? { ...tile, key: `${tile.key}${instant}` } : tile;
    const source = tile.arrays[name];
    const height = source ?? new Float32Array(tile.arrays.total_wave_height?.length ?? 0).fill(Number.NaN);
    return { ...tile, key: `${tile.key}#${component}${instant}`, arrays: { ...tile.arrays, total_wave_height: height } };
  });
}

/** Wind tiles get the same instant-carrying key for blends. */
export function tilesForWind(tiles: DecodedFieldTile[]): DecodedFieldTile[] {
  return tiles.map((tile) => (tile.key.endsWith("@blend") ? { ...tile, key: `${tile.key}@${tile.header.valid_time}` } : tile));
}
