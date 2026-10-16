import type { Spot } from "./types";
import { haversineKm } from "./mapLinks";

/**
 * Every spot dot on both public maps, in one colour: the dark house mark, a
 * plain ringless disc (2026-10-12 — both grounds are light again, so the mark
 * is dark; the light grey of the dark-map day disappeared on Voyager). The
 * dots used to be tinted by the live-wind scale and fell back to a near-white
 * neutral wherever a spot had no live reading, which read as "no spot here".
 * They now only say WHERE a spot is; what the wind does is the field's and the
 * forecast sheet's job. The wind scale stays the one source of truth for
 * charts — it is simply no longer used for map markers.
 */
export const SPOT_DOT_COLOR = "#1A1F24";

/** Minimal per-spot properties carried on a clustering feature — only what the
 *  marker/aria layer needs; the full Spot is looked up by `spotId` at render. */
export interface PublicSpotProperties {
  spotId: string;
  name: string;
  slug: string;
}

export type PublicSpotFeature = GeoJSON.Feature<GeoJSON.Point, PublicSpotProperties>;

/** Spots → GeoJSON point features (lng/lat order) for supercluster. Spots
 *  without coordinates are dropped. */
export function spotFeatures(spots: Spot[]): PublicSpotFeature[] {
  return spots.flatMap((spot) =>
    spot.coords
      ? [{
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [spot.coords[1], spot.coords[0]] },
          properties: { spotId: spot.id, name: spot.name, slug: spot.slug || "" },
        }]
      : [],
  );
}

// Fixed, deliberately chosen clustering: 44px catchment, singles from zoom 10.
export const PUBLIC_SPOT_CLUSTER_RADIUS = 44;
export const PUBLIC_SPOT_CLUSTER_MAX_ZOOM = 9;

export interface PublicMapUrlState { center: [number, number]; zoom: number; spot?: string }

export function parsePublicMapUrl(search: string): PublicMapUrlState | null {
  const q = new URLSearchParams(search);
  const lat = Number(q.get("lat"));
  const lon = Number(q.get("lon"));
  const zoom = Number(q.get("z"));
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(zoom) || lat < -85 || lat > 85 || lon < -180 || lon > 180 || zoom < 1 || zoom > 18) return null;
  return { center: [lon, lat], zoom, spot: q.get("spot") || undefined };
}

export function publicMapSearch(center: [number, number], zoom: number, spot?: string, current = ""): string {
  const q = new URLSearchParams(current);
  q.set("lat", center[1].toFixed(5));
  q.set("lon", center[0].toFixed(5));
  q.set("z", zoom.toFixed(2));
  if (spot) q.set("spot", spot); else q.delete("spot");
  // Remove legacy mode parameters now that the overview has one fixed layer.
  q.delete("mode");
  return `?${q.toString()}`;
}

export function sortViewportSpots(spots: Spot[], center: [number, number], selectedId?: string): Spot[] {
  return [...spots].sort((a, b) => {
    if (a.id === selectedId) return -1;
    if (b.id === selectedId) return 1;
    const distance = haversineKm(a.coords!, center) - haversineKm(b.coords!, center);
    return distance || (a.slug || a.name).localeCompare(b.slug || b.name, "de");
  });
}

export function spotCountLabel(count: number): string {
  return count === 1 ? "1 Spot im Kartenausschnitt" : `${count} Spots im Kartenausschnitt`;
}
