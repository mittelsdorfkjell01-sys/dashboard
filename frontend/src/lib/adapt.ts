// Adapts backend spot/region records into the frontend `Spot`/region shapes the
// presentational components already consume, so the UI didn't need a rewrite —
// only its data source changed (mock files → API).

import type { Spot } from "./types";
import { resolveMediaUrl, type Region, type SpotRead, type SpotSummary } from "./api";
import { countryName } from "./flags";

export function regionLabel(region?: Region): string {
  if (!region) return "";
  return [region.name, countryName(region.country)].filter(Boolean).join(", ");
}

/** Map a backend spot (+ its region) into the frontend `Spot`. */
export function adaptSpot(
  s: SpotSummary | SpotRead,
  region?: Region
): Spot {
  const coords: [number, number] | undefined = s.location
    ? [s.location.lat, s.location.lon]
    : undefined;

  const editorial = (s as SpotRead).editorial ?? null;
  const windRange = editorial?.wind_range as
    | [number, number]
    | undefined;
  const typicalWind = Array.isArray(windRange)
    ? Math.round((windRange[0] + windRange[1]) / 2)
    : 0;
  const description =
    typeof editorial?.description === "string" &&
    editorial.description.trim() &&
    editorial.description.trim().toLowerCase() !== "n/a"
      ? editorial.description.trim()
      : undefined;

  return {
    id: s.id, // backend UUID — also the route id
    uuid: s.id,
    slug: s.slug,
    name: s.name,
    region: regionLabel(region),
    regionId: s.region_id,
    wind: typicalWind,
    description,
    tags: [],
    // Empty string = "no image yet" → the UI renders a branded fallback (never
    // an external placeholder). A real upload fills this in later.
    image: resolveMediaUrl(s.image?.url) ?? "",
    hero: resolveMediaUrl(s.image?.url),
    heroFocal: s.image?.focal ?? null,
    heroCredit: s.image?.credit,
    heroLicense: s.image?.license,
    heroSource: s.image?.source,
    coords,
    windDir: s.facing ?? undefined,
    sports: s.sports,
    level: s.level,
    waterCharacter: s.water_character,
    style: s.style,
    facilities: s.facilities,
    climatology: (s as SpotRead).climatology ?? null,
    mapView:
      editorial?.map_view &&
      Array.isArray(editorial.map_view.center) &&
      typeof editorial.map_view.zoom === "number"
        ? {
            center: editorial.map_view.center as [number, number],
            zoom: editorial.map_view.zoom as number,
          }
        : null,
  };
}

export function adaptSpots(
  spots: (SpotSummary | SpotRead)[],
  regionsById: Map<string, Region>
): Spot[] {
  return spots.map((s) => adaptSpot(s, regionsById.get(s.region_id)));
}
