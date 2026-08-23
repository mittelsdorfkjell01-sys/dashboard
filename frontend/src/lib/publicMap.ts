import type { GeoJSONSource, GeoJSONSourceSpecification, LayerSpecification, FilterSpecification, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import type { Spot } from "./types";
import { haversineKm } from "./mapLinks";

export type PublicMapTheme = "light" | "dark";

// A single keyless CARTO Voyager vector style for both themes — the palette
// below repaints it, so Surfwinddata never runs its own tile pipeline.
export const PUBLIC_MAP_STYLE_URL: Record<PublicMapTheme, string> = {
  light: "https://tiles.basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  dark: "https://tiles.basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
};

export const PUBLIC_SPOT_SOURCE_ID = "public-spots";

/** Every layer this module owns, grouped by role (bottom to top):
 *   - shadow/clusters/clusterCount/points/hover/selectedRing/selected: the
 *     spot + cluster marker stack.
 *   - names: collision-driven spot name labels (zoom-gated, see
 *     `PUBLIC_MAP_LAYER_RULES`). Hovered/selected/focused names are shown via
 *     the accessible HTML marker capsule instead (always visible, no GL
 *     collision risk) — see MapView's `.swd-map-a11y-marker`. */
export const PUBLIC_SPOT_LAYER_IDS = {
  shadow: "public-spot-shadow",
  clusters: "public-spot-clusters",
  clusterHover: "public-spot-cluster-hover",
  clusterCount: "public-spot-cluster-count",
  points: "public-spot-points",
  hover: "public-spot-hover",
  selectedRing: "public-spot-selected-ring",
  selected: "public-spot-selected",
  names: "public-spot-names",
} as const;

export interface PublicSpotProperties {
  spotId: string;
  slug: string;
  name: string;
  region: string;
  country: string;
  image: string;
  windKt: number | null;
}

export type PublicSpotFeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Point, PublicSpotProperties>;

export function spotsToGeoJson(spots: Spot[]): PublicSpotFeatureCollection {
  return {
    type: "FeatureCollection",
    features: spots.flatMap((spot) => spot.coords ? [{
      type: "Feature" as const,
      id: spot.id,
      geometry: { type: "Point" as const, coordinates: [spot.coords[1], spot.coords[0]] },
      properties: {
        spotId: spot.id,
        slug: spot.slug || "",
        name: spot.name,
        region: spot.regionName || "",
        country: spot.regionCountry || "",
        image: spot.image || "",
        windKt: spot.typicalWindKt ?? null,
      },
    }] : []),
  };
}

// Fixed, deliberately chosen clustering: 44px catchment, singles from zoom 10.
export const PUBLIC_SPOT_CLUSTER_RADIUS = 44;
export const PUBLIC_SPOT_CLUSTER_MAX_ZOOM = 9;

export function publicSpotSource(): GeoJSONSourceSpecification {
  return {
    type: "geojson", data: spotsToGeoJson([]), promoteId: "spotId",
    cluster: true, clusterRadius: PUBLIC_SPOT_CLUSTER_RADIUS, clusterMaxZoom: PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
  };
}

/** The spot/cluster marker stack, pre-coloured for `theme` — a compact,
 *  restrained system: no droplets, no permanent sport icon, no multi-ring
 *  selection halo. Diameters: 18–20px normal spots, 22–24px on hover/focus,
 *  30/34/38px clusters (small/medium/large). */
export function publicSpotLayers(theme: PublicMapTheme): LayerSpecification[] {
  const t = PUBLIC_MAP_PALETTE[theme];
  return [
    {
      id: PUBLIC_SPOT_LAYER_IDS.shadow, type: "circle", source: PUBLIC_SPOT_SOURCE_ID,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 8.5, 14, 11],
        "circle-color": "#0B1416", "circle-opacity": 0.14, "circle-blur": 0.9, "circle-translate": [0, 1],
      },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.clusters, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["has", "point_count"],
      paint: {
        "circle-radius": ["step", ["get", "point_count"], 15, 10, 17, 50, 19],
        "circle-color": t.spot, "circle-stroke-color": t.floating, "circle-stroke-width": 2,
      },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.clusterHover, type: "circle", source: PUBLIC_SPOT_SOURCE_ID,
      filter: ["==", ["get", "cluster_id"], -1],
      paint: {
        "circle-radius": ["+", ["step", ["get", "point_count"], 15, 10, 17, 50, 19], 3],
        "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": t.selection, "circle-stroke-width": 2,
      },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.clusterCount, type: "symbol", source: PUBLIC_SPOT_SOURCE_ID, filter: ["has", "point_count"],
      layout: { "text-field": ["get", "point_count"], "text-size": 12, "text-font": ["Noto Sans Regular"], "text-allow-overlap": true },
      paint: { "text-color": "#FFFFFF" },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.points, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 8.5, 8, 9, 14, 9.5],
        "circle-color": t.spot, "circle-stroke-color": t.floating, "circle-stroke-width": 2,
      },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.hover, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["==", ["get", "spotId"], ""],
      paint: { "circle-radius": 11, "circle-color": t.spot, "circle-stroke-color": t.selection, "circle-stroke-width": 2 },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.selectedRing, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["==", ["get", "spotId"], ""],
      paint: { "circle-radius": 13, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": t.selection, "circle-stroke-width": 1.5, "circle-stroke-opacity": 0.55 },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.selected, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["==", ["get", "spotId"], ""],
      paint: { "circle-radius": 10, "circle-color": t.spot, "circle-stroke-color": t.selection, "circle-stroke-width": 2.5 },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.names, type: "symbol", source: PUBLIC_SPOT_SOURCE_ID,
      minzoom: PUBLIC_MAP_LAYER_RULES.spotNames.minzoom, filter: ["!", ["has", "point_count"]],
      layout: { "text-field": ["get", "name"], "text-size": 11, "text-offset": [0, 1.55], "text-allow-overlap": false, "text-optional": true },
      paint: { "text-color": t.label, "text-halo-color": t.floating, "text-halo-width": 1.2 },
    },
  ];
}

export function setPublicSpotData(map: MapLibreMap, spots: Spot[]): void {
  (map.getSource(PUBLIC_SPOT_SOURCE_ID) as GeoJSONSource | undefined)?.setData(spotsToGeoJson(spots));
}

export function setPublicSpotSelection(map: MapLibreMap, hovered?: string, selected?: string): void {
  const match = (id?: string) => ["==", ["get", "spotId"], id || ""] as FilterSpecification;
  if (map.getLayer(PUBLIC_SPOT_LAYER_IDS.hover)) map.setFilter(PUBLIC_SPOT_LAYER_IDS.hover, match(hovered));
  for (const id of [PUBLIC_SPOT_LAYER_IDS.selectedRing, PUBLIC_SPOT_LAYER_IDS.selected]) if (map.getLayer(id)) map.setFilter(id, match(selected));
}

export function setPublicClusterHover(map: MapLibreMap, clusterId?: number): void {
  if (!map.getLayer(PUBLIC_SPOT_LAYER_IDS.clusterHover)) return;
  map.setFilter(PUBLIC_SPOT_LAYER_IDS.clusterHover, ["==", ["get", "cluster_id"], clusterId ?? -1]);
}

// ---------------------------------------------------------------------------
// Palette — light water/land lightened per feedback (2026-08-22): water now
// reads as a clear, bright sky-blue rather than a muted teal-grey, and land
// is a touch lighter so the water/land contrast still carries the coastline
// without either tone looking heavy. Dark is an independent set of values
// (not a filtered/darkened copy of light).
// ---------------------------------------------------------------------------
export const PUBLIC_MAP_PALETTE = {
  light: {
    water: "#BFE3F5", waterDeep: "#A9D6ED", land: "#F8F5EE", urban: "#F1ECE1", park: "#E2EADD",
    coast: "#6FA9C4", boundary: "#D2CEC2", label: "#233638", secondary: "#6C7A82",
    spot: "#126B70", selection: "#F06F4F", floating: "#FFFDF8",
    road: "#D3C6B4", roadMinor: "#E5DACB",
  },
  dark: {
    water: "#0C2E34", waterDeep: "#0A262B", land: "#19272A", urban: "#202E30", park: "#20332F",
    coast: "#52777A", boundary: "#3A4A4C", label: "#EDE9DF", secondary: "#A8B8B7",
    spot: "#6AC2C0", selection: "#FF8160", floating: "#172326",
    road: "#3E4C4E", roadMinor: "#2C3739",
  },
} as const;

// ---------------------------------------------------------------------------
// Zoom / label hierarchy — deliberately earlier than a generic street map:
// regions and coastal towns should read before the visitor has zoomed all
// the way to street level. Values below are the source of truth; the table
// in the design brief is the derivation, not a second spec.
// ---------------------------------------------------------------------------
export const PUBLIC_MAP_LAYER_RULES = {
  // Country/region names deliberately stay off the initial world/continent
  // overview (2026-08-23 feedback) — they only read once you've zoomed well
  // past the "where in the world" view and into a specific area.
  country: { minzoom: 7, maxzoom: 10 },
  capital: { minzoom: 3.5, maxzoom: 12 },
  state: { minzoom: 8, maxzoom: 12 },
  majorCity: { minzoom: 5.5, maxzoom: 16 },
  city: { minzoom: 8, maxzoom: 17 },
  town: { minzoom: 10.5, maxzoom: 18 },
  village: { minzoom: 10.5, maxzoom: 19 },
  hamlet: { minzoom: 12.5, maxzoom: 20 },
  roads: { major: 8.5, secondary: 11.5, minor: 13 },
  roadLabels: { major: 9.5, primary: 10, secondary: 12, minor: 13.5 },
  buildings: 15.5,
  localPoi: 13.5,
  spotNames: { minzoom: 11 },
} as const;

/** Real layer ids exposed by CARTO's OpenMapTiles-compatible Voyager style,
 *  grouped by the label stage they belong to. Confirmed against the loaded
 *  style.json — nothing invented. Layers not present (an optional CARTO
 *  layer having been renamed/removed upstream) are silently skipped by
 *  `buildPublicMapStyle`. */
const PLACE_LAYER_ZOOM: Record<string, { minzoom: number; maxzoom: number }> = {
  place_country_1: PUBLIC_MAP_LAYER_RULES.country, place_country_2: PUBLIC_MAP_LAYER_RULES.country,
  place_capital_dot_z7: PUBLIC_MAP_LAYER_RULES.capital,
  place_state: PUBLIC_MAP_LAYER_RULES.state,
  place_city_dot_r2: PUBLIC_MAP_LAYER_RULES.majorCity, place_city_dot_r4: PUBLIC_MAP_LAYER_RULES.majorCity, place_city_r5: PUBLIC_MAP_LAYER_RULES.majorCity,
  place_city_dot_r7: PUBLIC_MAP_LAYER_RULES.city, place_city_dot_z7: PUBLIC_MAP_LAYER_RULES.city, place_city_r6: PUBLIC_MAP_LAYER_RULES.city,
  place_town: PUBLIC_MAP_LAYER_RULES.town,
  place_villages: PUBLIC_MAP_LAYER_RULES.village,
  place_hamlet: PUBLIC_MAP_LAYER_RULES.hamlet, place_suburbs: PUBLIC_MAP_LAYER_RULES.hamlet,
};
const ROAD_NAME_ZOOM: Record<string, number> = {
  roadname_major: PUBLIC_MAP_LAYER_RULES.roadLabels.major,
  roadname_pri: PUBLIC_MAP_LAYER_RULES.roadLabels.primary,
  roadname_sec: PUBLIC_MAP_LAYER_RULES.roadLabels.secondary,
  roadname_minor: PUBLIC_MAP_LAYER_RULES.roadLabels.minor,
};
const PRIMARY_LABEL_IDS = ["place_country_1", "place_country_2", "place_state", "place_continent"];
const SECONDARY_LABEL_IDS = [
  "place_city_r5", "place_city_r6", "place_city_dot_r2", "place_city_dot_r4", "place_city_dot_r7", "place_city_dot_z7",
  "place_capital_dot_z7", "place_town", "place_villages", "place_hamlet", "place_suburbs",
  "roadname_major", "roadname_pri", "roadname_sec", "roadname_minor", "poi_park",
];
const WATER_LABEL_IDS = ["watername_ocean", "watername_sea", "watername_lake", "watername_lake_line", "waterway_label"];
const ROAD_FILL_MAJOR = ["road_mot_fill_noramp", "road_trunk_fill_noramp", "road_pri_fill_noramp", "bridge_mot_fill", "bridge_trunk_fill", "bridge_pri_fill", "tunnel_mot_fill", "tunnel_trunk_fill", "tunnel_pri_fill"];
const ROAD_FILL_MINOR = ["road_sec_fill_noramp", "road_minor_fill", "road_service_fill", "road_path", "bridge_sec_fill", "bridge_minor_fill", "bridge_service_fill", "tunnel_sec_fill", "tunnel_minor_fill", "tunnel_service_fill"];

type MutableLayer = LayerSpecification & { paint?: Record<string, unknown>; layout?: Record<string, unknown>; minzoom?: number; maxzoom?: number; filter?: unknown };

/** Pure transform: takes the CARTO Voyager style document as fetched (not
 * yet attached to a map) and returns Surfwinddata's coastal-atlas version —
 * palette, zoom/label hierarchy and the spot/cluster layer stack all baked
 * directly into the document. Because this runs *before* `new
 * maplibregl.Map()` is ever called, the browser's very first paint already
 * shows the finished style — there is no intermediate frame of raw Voyager
 * to flash, and no post-load repaint pass (~40 imperative `setPaintProperty`
 * calls) needed on every load or theme switch.
 *
 * Layer groups controlled:
 *  - Water:  water, water_shadow, watername_* (ocean/sea/lake labels)
 *  - Land:   background, landcover, landuse(_residential), park_*
 *  - Roads:  every `transportation` source-layer line/label (road/bridge/
 *            tunnel case+fill variants, roadname_*)
 *  - Places: place_country/state/capital/city/town/villages/hamlet/suburbs
 *  - Misc:   boundary_*, building(-top), aeroway-*, poi_park (kept),
 *            poi_stadium + housenumber (hidden — no general POI clutter) */
export function buildPublicMapStyle(base: StyleSpecification, theme: PublicMapTheme): StyleSpecification {
  const p = PUBLIC_MAP_PALETTE[theme];
  const layers: MutableLayer[] = (base.layers ?? []).map((l) => ({ ...l, paint: { ...(l as MutableLayer).paint }, layout: { ...(l as MutableLayer).layout } }));
  const byId = new Map(layers.map((l) => [l.id, l]));

  const paint = (id: string, prop: string, value: unknown) => { const l = byId.get(id); if (l) l.paint = { ...l.paint, [prop]: value }; };
  const layout = (id: string, prop: string, value: unknown) => { const l = byId.get(id); if (l) l.layout = { ...l.layout, [prop]: value }; };
  const zoomRange = (id: string, min: number, max = 24) => { const l = byId.get(id); if (l) { l.minzoom = min; l.maxzoom = max; } };
  const hide = (id: string) => layout(id, "visibility", "none");
  const label = (id: string, color: string) => {
    if (!byId.has(id)) return;
    paint(id, "text-color", color);
    paint(id, "text-halo-color", p.floating);
    paint(id, "text-halo-width", 1);
    layout(id, "text-allow-overlap", false);
  };

  // Land / water — water reads clearly stronger than a generic street map;
  // land stays warm and quiet; coastlines are the sharpest boundary on the
  // map (clearer than country borders).
  paint("background", "background-color", p.land);
  paint("water", "fill-color", p.water);
  // `water_shadow` is a full-coverage layer in this style (not a thin
  // coastal rim) — paint it with the deeper water tone, not the coastline
  // color, or the whole ocean reads as saturated grey instead of pale water.
  paint("water_shadow", "fill-color", p.waterDeep);
  paint("landcover", "fill-color", p.land);
  paint("landuse", "fill-color", p.urban);
  paint("landuse_residential", "fill-color", p.urban);
  paint("park_national_park", "fill-color", p.park);
  paint("park_nature_reserve", "fill-color", p.park);
  paint("boundary_country_inner", "line-color", p.boundary);
  paint("boundary_country_outline", "line-color", p.boundary);
  paint("boundary_state", "line-color", p.boundary);
  paint("boundary_county", "line-color", p.boundary);
  zoomRange("boundary_state", PUBLIC_MAP_LAYER_RULES.state.minzoom);
  zoomRange("boundary_county", 12);
  zoomRange("landuse_residential", 10);
  zoomRange("park_national_park", 11);
  zoomRange("park_nature_reserve", 9);
  zoomRange("aeroway-runway", PUBLIC_MAP_LAYER_RULES.buildings - 0.5);
  zoomRange("aeroway-taxiway", PUBLIC_MAP_LAYER_RULES.buildings);

  // Roads stay firmly subordinate: muted tones, later zoom onset than spots.
  for (const l of layers) {
    if (l.type !== "line" || !("source-layer" in l) || (l as { "source-layer"?: string })["source-layer"] !== "transportation") continue;
    const isMinor = /minor|service|path|rail/.test(l.id);
    const isSecondary = /sec/.test(l.id);
    paint(l.id, "line-color", isMinor || isSecondary ? p.roadMinor : p.road);
    zoomRange(l.id, isMinor ? PUBLIC_MAP_LAYER_RULES.roads.minor : isSecondary ? PUBLIC_MAP_LAYER_RULES.roads.secondary : PUBLIC_MAP_LAYER_RULES.roads.major);
  }
  for (const id of ROAD_FILL_MAJOR) paint(id, "line-color", p.road);
  for (const id of ROAD_FILL_MINOR) paint(id, "line-color", p.roadMinor);

  zoomRange("building", PUBLIC_MAP_LAYER_RULES.buildings);
  zoomRange("building-top", PUBLIC_MAP_LAYER_RULES.buildings);
  for (const [id, range] of Object.entries(PLACE_LAYER_ZOOM)) zoomRange(id, range.minzoom, range.maxzoom);
  if (byId.has("place_capital_dot_z7")) {
    // CARTO's upstream layer includes regional capitals (`capital > 0`). The
    // overview deliberately keeps only national capitals (`capital = 2`).
    const l = byId.get("place_capital_dot_z7")!;
    l.filter = ["==", "capital", 2];
  }
  for (const [id, min] of Object.entries(ROAD_NAME_ZOOM)) zoomRange(id, min);
  zoomRange("poi_park", PUBLIC_MAP_LAYER_RULES.localPoi);
  hide("poi_stadium");
  hide("housenumber");

  for (const id of PRIMARY_LABEL_IDS) {
    label(id, p.label);
    layout(id, "text-field", ["coalesce", ["get", "name:de"], ["get", "name_de"], ["get", "name"]]);
  }
  for (const id of SECONDARY_LABEL_IDS) {
    label(id, p.secondary);
    layout(id, "text-field", ["coalesce", ["get", "name"], ["get", "name:de"], ["get", "name_en"]]);
  }
  for (const id of WATER_LABEL_IDS) {
    label(id, p.coast);
    paint(id, "text-opacity", 0.8);
  }

  return {
    ...base,
    sources: { ...base.sources, [PUBLIC_SPOT_SOURCE_ID]: publicSpotSource() },
    layers: [...layers, ...publicSpotLayers(theme)],
  };
}

export async function fetchPublicMapStyle(theme: PublicMapTheme): Promise<StyleSpecification> {
  const resp = await fetch(PUBLIC_MAP_STYLE_URL[theme]);
  if (!resp.ok) throw new Error(`Kartenstil konnte nicht geladen werden (${resp.status}).`);
  const base = (await resp.json()) as StyleSpecification;
  return buildPublicMapStyle(base, theme);
}

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
