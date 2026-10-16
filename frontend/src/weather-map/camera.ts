/** Camera framing shared by every map that focuses a single spot. */

/** "Zoomed to the spot": close enough to read the coastline, wide enough that
 *  a model field (grid spacing of kilometres) still has something to draw. */
export const SPOT_FOCUS_ZOOM = 11;

/** A region is an area, not a place. */
export const REGION_FOCUS_ZOOM = 7;

/** Widest frame the field map stays useful at — below this the model grid is
 *  coarser than what the viewport implies. */
const MIN_FOCUS_ZOOM = 3;

/**
 * A frame that holds every given spot: the centre of their bounding box and a
 * zoom that fits its wider side. Deliberately approximate — it is a reading
 * frame, not a geodesy problem: one degree of longitude at zoom z spans
 * 360 / 2^z across the viewport, and the ×2 on latitude plus the half-step of
 * padding keep the outermost spots clear of the chrome at the map's edges.
 * `coords` are the spots' own [lat, lon] pairs; the returned centre is
 * [lon, lat], the order every map camera here takes.
 */
export function framingFor(coords: Array<[number, number]>): { center: [number, number]; zoom: number } | null {
  if (coords.length === 0) return null;
  const lats = coords.map(([lat]) => lat);
  const lons = coords.map(([, lon]) => lon);
  const south = Math.min(...lats), north = Math.max(...lats);
  const west = Math.min(...lons), east = Math.max(...lons);
  const center: [number, number] = [(west + east) / 2, (south + north) / 2];
  if (coords.length === 1) return { center, zoom: SPOT_FOCUS_ZOOM };
  const span = Math.max(east - west, (north - south) * 2, 0.05);
  const zoom = Math.log2(360 / span) - 0.5;
  return { center, zoom: Math.min(SPOT_FOCUS_ZOOM, Math.max(MIN_FOCUS_ZOOM, zoom)) };
}
