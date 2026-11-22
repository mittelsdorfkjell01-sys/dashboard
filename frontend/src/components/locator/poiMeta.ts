import type { MapPoi, MapPoiCategory } from "../../lib/api";

/**
 * One entry per OpenStreetMap category the spot map draws. `minZoom` staggers
 * them like Apple Maps does: what a rider needs first on arrival (the surf
 * school, a place to park) appears before the cafés and bars. Zooms are in
 * MapLibre's 512px convention (one less than the old Leaflet map's numbers).
 */
export const POI_META: Record<MapPoiCategory, {
  label: string;
  /** Lower draws first when two pins compete for the same place. */
  priority: number;
  minZoom: number;
  path: string;
}> = {
  surf_school: {
    label: "Surfschule", priority: 0, minZoom: 13.5,
    path: "M10.6 3.2c2.9 0 5.2 1.7 6.2 4.2-1.7-.9-3.6-1-5.2.2-1 .7-1.6 1.7-1.9 2.8H7.5c.4-4 1.6-7.2 3.1-7.2ZM2 13c1.6 0 2.4-1.2 4-1.2s2.4 1.2 4 1.2 2.4-1.2 4-1.2 2.4 1.2 4 1.2v2.2c-1.6 0-2.4-1.2-4-1.2s-2.4 1.2-4 1.2-2.4-1.2-4-1.2-2.4 1.2-4 1.2V13Z",
  },
  parking: {
    label: "Parkplatz", priority: 1, minZoom: 14,
    path: "M6 3.5h5.2a4 4 0 0 1 0 8H8.6v5H6v-13Zm2.6 2.4v3.3h2.6a1.65 1.65 0 0 0 0-3.3H8.6Z",
  },
  campsite: {
    label: "Campingplatz", priority: 2, minZoom: 14,
    path: "M10 2.8 18.2 17H1.8L10 2.8Zm0 7.4L7 17h6l-3-6.8Z",
  },
  cafe: {
    label: "Café", priority: 3, minZoom: 14.5,
    path: "M3.8 5.5h9.4V10a4.7 4.7 0 0 1-9.4 0V5.5Zm9.4 1.3h1.1a2.5 2.5 0 0 1 0 5h-1.5c.2-.5.3-1 .4-1.6h1.1a.9.9 0 0 0 0-1.8h-1.1V6.8ZM2.8 16h12.4v1.8H2.8V16Z",
  },
  bar: {
    label: "Bar", priority: 4, minZoom: 15,
    path: "M3.2 3.8h13.6L11.1 10.7V15h2.3v1.9H6.6V15h2.3v-4.3L3.2 3.8Z",
  },
};

/** POIs are fetched once the closest category could appear. */
export const POI_LOAD_ZOOM = Math.min(...Object.values(POI_META).map((meta) => meta.minZoom));
/** Names under the pins, as in Apple Maps, only once there is room for them. */
export const POI_LABEL_ZOOM = 15.5;

export function poiTitle(poi: Pick<MapPoi, "name" | "category">): string {
  return poi.name || `${POI_META[poi.category].label} ohne Namen`;
}

const DAY_WORDS: Record<string, string> = {
  Mo: "Mo", Tu: "Di", We: "Mi", Th: "Do", Fr: "Fr", Sa: "Sa", Su: "So",
  PH: "Feiertage", SH: "Schulferien", off: "geschlossen", closed: "geschlossen",
};

/**
 * OpenStreetMap opening hours, made readable without reinterpreting them:
 * German day names, one rule per line. Anything the simple form does not
 * cover (seasons, exceptions) stays as mapped. Whether a place is open right
 * now is decided separately and conservatively (openingStatus.ts).
 */
export function readableOpeningHours(raw: string): string[] {
  if (raw.trim() === "24/7") return ["Rund um die Uhr"];
  return raw
    .split(";")
    .map((rule) => rule.trim())
    .filter(Boolean)
    .map((rule) => rule
      .replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su|PH|SH|off|closed)\b/g, (word) => DAY_WORDS[word] ?? word)
      .replace(/(\p{L}{2})-(\p{L}{2})/gu, "$1–$2")
      .replace(/(\d{2}:\d{2})-(\d{2}:\d{2})/g, "$1–$2")
      .replace(/,(?=\S)/g, ", "));
}
