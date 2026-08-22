import type { Map as MapLibreMap, GeoJSONSource, LayerSpecification, FilterSpecification } from "maplibre-gl";
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

/** Every layer this module owns, grouped by role so a style/theme swap can
 *  restore them deterministically (see `ensurePublicSpotLayers`):
 *   - shadow/clusters/clusterCount/points/hover/selectedRing/selected: the
 *     spot + cluster marker stack (bottom to top).
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

const layerExists = (map: MapLibreMap, id: string) => Boolean(map.getLayer(id));

export function ensurePublicSpotLayers(map: MapLibreMap): void {
  if (!map.getSource(PUBLIC_SPOT_SOURCE_ID)) {
    map.addSource(PUBLIC_SPOT_SOURCE_ID, {
      type: "geojson", data: spotsToGeoJson([]), promoteId: "spotId",
      cluster: true, clusterRadius: PUBLIC_SPOT_CLUSTER_RADIUS, clusterMaxZoom: PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
    });
  }
  // A compact, restrained marker stack — no droplets, no permanent sport
  // icon, no multi-ring selection halo. Diameters: 18–20px normal spots,
  // 22–24px on hover/focus, 30/34/38px clusters (small/medium/large).
  const layers: LayerSpecification[] = [
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
        "circle-color": "#126B70", "circle-stroke-color": "#FFFDF8", "circle-stroke-width": 2,
      },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.clusterHover, type: "circle", source: PUBLIC_SPOT_SOURCE_ID,
      filter: ["==", ["get", "cluster_id"], -1],
      paint: {
        "circle-radius": ["+", ["step", ["get", "point_count"], 15, 10, 17, 50, 19], 3],
        "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#F06F4F", "circle-stroke-width": 2,
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
        "circle-color": "#126B70", "circle-stroke-color": "#FFFDF8", "circle-stroke-width": 2,
      },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.hover, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["==", ["get", "spotId"], ""],
      paint: { "circle-radius": 11, "circle-color": "#126B70", "circle-stroke-color": "#F06F4F", "circle-stroke-width": 2 },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.selectedRing, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["==", ["get", "spotId"], ""],
      paint: { "circle-radius": 13, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#F06F4F", "circle-stroke-width": 1.5, "circle-stroke-opacity": 0.55 },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.selected, type: "circle", source: PUBLIC_SPOT_SOURCE_ID, filter: ["==", ["get", "spotId"], ""],
      paint: { "circle-radius": 10, "circle-color": "#126B70", "circle-stroke-color": "#F06F4F", "circle-stroke-width": 2.5 },
    },
    {
      id: PUBLIC_SPOT_LAYER_IDS.names, type: "symbol", source: PUBLIC_SPOT_SOURCE_ID,
      minzoom: PUBLIC_MAP_LAYER_RULES.spotNames.minzoom, filter: ["!", ["has", "point_count"]],
      layout: { "text-field": ["get", "name"], "text-size": 11, "text-offset": [0, 1.55], "text-allow-overlap": false, "text-optional": true },
      paint: { "text-color": "#233638", "text-halo-color": "#FFFDF8", "text-halo-width": 1.2 },
    },
  ];
  for (const layer of layers) if (!map.getLayer(layer.id)) map.addLayer(layer);
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

export function applyPublicSpotTheme(map: MapLibreMap, theme: PublicMapTheme): void {
  const t = theme === "dark" ? PUBLIC_MAP_PALETTE.dark : PUBLIC_MAP_PALETTE.light;
  const paint = (id: string, property: string, value: unknown) => { if (layerExists(map, id)) map.setPaintProperty(id, property, value); };
  // Spot fill / label colours swap per theme; the coral selection accent and
  // warm marker border stay legible in both.
  for (const id of [PUBLIC_SPOT_LAYER_IDS.clusters, PUBLIC_SPOT_LAYER_IDS.points, PUBLIC_SPOT_LAYER_IDS.hover, PUBLIC_SPOT_LAYER_IDS.selected]) {
    paint(id, "circle-color", t.spot);
    paint(id, "circle-stroke-color", t.floating);
  }
  paint(PUBLIC_SPOT_LAYER_IDS.selectedRing, "circle-stroke-color", t.selection);
  paint(PUBLIC_SPOT_LAYER_IDS.hover, "circle-stroke-color", t.selection);
  paint(PUBLIC_SPOT_LAYER_IDS.clusterHover, "circle-stroke-color", t.selection);
  paint(PUBLIC_SPOT_LAYER_IDS.names, "text-color", t.label);
  paint(PUBLIC_SPOT_LAYER_IDS.names, "text-halo-color", t.floating);
}

// ---------------------------------------------------------------------------
// Palette — verbatim from the design brief. Dark is an independent set of
// values (not a filtered/darkened copy of light).
// ---------------------------------------------------------------------------
export const PUBLIC_MAP_PALETTE = {
  light: {
    water: "#D8E8E9", waterDeep: "#C9DEE1", land: "#F3EFE6", urban: "#ECE8DF", park: "#DCE5D8",
    coast: "#76979A", boundary: "#C8C5BA", label: "#233638", secondary: "#68797A",
    spot: "#126B70", selection: "#F06F4F", floating: "#FFFDF8",
    road: "#C9BBAA", roadMinor: "#DED4C8",
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
  country: { minzoom: 2.5, maxzoom: 10 },
  capital: { minzoom: 3.5, maxzoom: 12 },
  state: { minzoom: 4.5, maxzoom: 12 },
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

const setVisible = (map: MapLibreMap, ids: string[], visible: boolean) => {
  for (const id of ids) if (layerExists(map, id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
};

/** Enforce the editorial density independently of the upstream style's own
 * zoom metadata. This second gate is intentional: cached CARTO styles may be
 * attached before runtime zoom ranges are applied, while visibility changes
 * remain deterministic after every completed zoom. */
export function updatePublicMapLayerVisibility(map: MapLibreMap): void {
  const z = map.getZoom();
  setVisible(map, ["place_country_1", "place_country_2"], z >= PUBLIC_MAP_LAYER_RULES.country.minzoom && z < PUBLIC_MAP_LAYER_RULES.country.maxzoom);
  setVisible(map, ["place_capital_dot_z7"], z >= PUBLIC_MAP_LAYER_RULES.capital.minzoom && z < PUBLIC_MAP_LAYER_RULES.capital.maxzoom);
  setVisible(map, ["place_state"], z >= PUBLIC_MAP_LAYER_RULES.state.minzoom && z < PUBLIC_MAP_LAYER_RULES.state.maxzoom);
  setVisible(map, ["place_city_dot_r2", "place_city_dot_r4"], z >= PUBLIC_MAP_LAYER_RULES.majorCity.minzoom);
  setVisible(map, ["place_city_r5"], z >= PUBLIC_MAP_LAYER_RULES.majorCity.minzoom);
  setVisible(map, ["place_city_dot_r7", "place_city_dot_z7", "place_city_r6"], z >= PUBLIC_MAP_LAYER_RULES.city.minzoom);
  setVisible(map, ["place_town"], z >= PUBLIC_MAP_LAYER_RULES.town.minzoom);
  setVisible(map, ["place_villages"], z >= PUBLIC_MAP_LAYER_RULES.village.minzoom);
  setVisible(map, ["place_hamlet", "place_suburbs"], z >= PUBLIC_MAP_LAYER_RULES.hamlet.minzoom);

  for (const layer of map.getStyle().layers ?? []) {
    if (layer.type !== "line" || !("source-layer" in layer) || layer["source-layer"] !== "transportation") continue;
    const threshold = /minor|service|path|rail/.test(layer.id)
      ? PUBLIC_MAP_LAYER_RULES.roads.minor
      : /sec/.test(layer.id)
        ? PUBLIC_MAP_LAYER_RULES.roads.secondary
        : PUBLIC_MAP_LAYER_RULES.roads.major;
    setVisible(map, [layer.id], z >= threshold);
  }
}

/** Apply Surfwinddata's coastal-atlas palette + hierarchy to the real layer
 * ids exposed by CARTO's OpenMapTiles-compatible Voyager style. Every id
 * below was confirmed against the loaded style.json — nothing invented.
 * Layer groups controlled:
 *  - Water:  water, water_shadow, watername_* (ocean/sea/lake labels)
 *  - Land:   background, landcover, landuse(_residential), park_*
 *  - Roads:  every `transportation` source-layer line/label (road/bridge/
 *            tunnel case+fill variants, roadname_*)
 *  - Places: place_country/state/capital/city/town/villages/hamlet/suburbs
 *  - Misc:   boundary_*, building(-top), aeroway-*, poi_park (kept),
 *            poi_stadium + housenumber (hidden — no general POI clutter) */
export function applyPublicMapStyle(map: MapLibreMap, theme: PublicMapTheme): void {
  const p = PUBLIC_MAP_PALETTE[theme];
  const paint = (id: string, property: string, value: unknown) => { if (layerExists(map, id)) map.setPaintProperty(id, property, value); };
  const zoom = (id: string, min: number, max = 24) => { if (layerExists(map, id)) map.setLayerZoomRange(id, min, max); };
  const hide = (id: string) => { if (layerExists(map, id)) map.setLayoutProperty(id, "visibility", "none"); };
  const label = (id: string, color: string) => {
    if (!layerExists(map, id)) return;
    map.setPaintProperty(id, "text-color", color);
    map.setPaintProperty(id, "text-halo-color", p.floating);
    map.setPaintProperty(id, "text-halo-width", 1);
    map.setLayoutProperty(id, "text-allow-overlap", false);
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
  zoom("boundary_state", PUBLIC_MAP_LAYER_RULES.state.minzoom);
  zoom("boundary_county", 12);
  zoom("landuse_residential", 10);
  zoom("park_national_park", 11);
  zoom("park_nature_reserve", 9);
  zoom("aeroway-runway", PUBLIC_MAP_LAYER_RULES.buildings - 0.5);
  zoom("aeroway-taxiway", PUBLIC_MAP_LAYER_RULES.buildings);

  // Roads stay firmly subordinate: muted tones, later zoom onset than spots.
  for (const layer of map.getStyle().layers ?? []) {
    if (layer.type !== "line" || !("source-layer" in layer) || layer["source-layer"] !== "transportation") continue;
    const isMinor = /minor|service|path|rail/.test(layer.id);
    const isSecondary = /sec/.test(layer.id);
    paint(layer.id, "line-color", isMinor || isSecondary ? p.roadMinor : p.road);
    zoom(layer.id, isMinor ? PUBLIC_MAP_LAYER_RULES.roads.minor : isSecondary ? PUBLIC_MAP_LAYER_RULES.roads.secondary : PUBLIC_MAP_LAYER_RULES.roads.major);
  }
  for (const id of ["road_mot_fill_noramp", "road_trunk_fill_noramp", "road_pri_fill_noramp", "bridge_mot_fill", "bridge_trunk_fill", "bridge_pri_fill", "tunnel_mot_fill", "tunnel_trunk_fill", "tunnel_pri_fill"]) paint(id, "line-color", p.road);
  for (const id of ["road_sec_fill_noramp", "road_minor_fill", "road_service_fill", "road_path", "bridge_sec_fill", "bridge_minor_fill", "bridge_service_fill", "tunnel_sec_fill", "tunnel_minor_fill", "tunnel_service_fill"]) paint(id, "line-color", p.roadMinor);

  zoom("building", PUBLIC_MAP_LAYER_RULES.buildings);
  zoom("building-top", PUBLIC_MAP_LAYER_RULES.buildings);
  zoom("place_country_1", PUBLIC_MAP_LAYER_RULES.country.minzoom, PUBLIC_MAP_LAYER_RULES.country.maxzoom);
  zoom("place_country_2", PUBLIC_MAP_LAYER_RULES.country.minzoom, PUBLIC_MAP_LAYER_RULES.country.maxzoom);
  zoom("place_state", PUBLIC_MAP_LAYER_RULES.state.minzoom, PUBLIC_MAP_LAYER_RULES.state.maxzoom);
  zoom("place_capital_dot_z7", PUBLIC_MAP_LAYER_RULES.capital.minzoom, PUBLIC_MAP_LAYER_RULES.capital.maxzoom);
  if (layerExists(map, "place_capital_dot_z7")) {
    // CARTO's upstream layer includes regional capitals (`capital > 0`). The
    // overview deliberately keeps only national capitals (`capital = 2`).
    map.setFilter("place_capital_dot_z7", ["==", "capital", 2]);
  }
  for (const id of ["place_city_dot_r2", "place_city_dot_r4"]) zoom(id, PUBLIC_MAP_LAYER_RULES.majorCity.minzoom, PUBLIC_MAP_LAYER_RULES.majorCity.maxzoom);
  for (const id of ["place_city_dot_r7", "place_city_dot_z7"]) zoom(id, PUBLIC_MAP_LAYER_RULES.city.minzoom, PUBLIC_MAP_LAYER_RULES.city.maxzoom);
  zoom("place_city_r5", PUBLIC_MAP_LAYER_RULES.majorCity.minzoom, PUBLIC_MAP_LAYER_RULES.majorCity.maxzoom);
  zoom("place_city_r6", PUBLIC_MAP_LAYER_RULES.city.minzoom, PUBLIC_MAP_LAYER_RULES.city.maxzoom);
  zoom("place_town", PUBLIC_MAP_LAYER_RULES.town.minzoom, PUBLIC_MAP_LAYER_RULES.town.maxzoom);
  zoom("place_villages", PUBLIC_MAP_LAYER_RULES.village.minzoom, PUBLIC_MAP_LAYER_RULES.village.maxzoom);
  zoom("place_hamlet", PUBLIC_MAP_LAYER_RULES.hamlet.minzoom, PUBLIC_MAP_LAYER_RULES.hamlet.maxzoom);
  zoom("place_suburbs", PUBLIC_MAP_LAYER_RULES.hamlet.minzoom, PUBLIC_MAP_LAYER_RULES.hamlet.maxzoom);
  zoom("roadname_major", PUBLIC_MAP_LAYER_RULES.roadLabels.major);
  zoom("roadname_pri", PUBLIC_MAP_LAYER_RULES.roadLabels.primary);
  zoom("roadname_sec", PUBLIC_MAP_LAYER_RULES.roadLabels.secondary);
  zoom("roadname_minor", PUBLIC_MAP_LAYER_RULES.roadLabels.minor);
  zoom("poi_park", PUBLIC_MAP_LAYER_RULES.localPoi);
  hide("poi_stadium");
  hide("housenumber");

  for (const id of ["place_country_1", "place_country_2", "place_state", "place_continent"]) {
    label(id, p.label);
    if (layerExists(map, id)) map.setLayoutProperty(id, "text-field", ["coalesce", ["get", "name:de"], ["get", "name_de"], ["get", "name"]]);
  }
  for (const id of ["place_city_r5", "place_city_r6", "place_city_dot_r2", "place_city_dot_r4", "place_city_dot_r7", "place_city_dot_z7", "place_capital_dot_z7", "place_town", "place_villages", "place_hamlet", "place_suburbs", "roadname_major", "roadname_pri", "roadname_sec", "roadname_minor", "poi_park"]) {
    label(id, p.secondary);
    if (layerExists(map, id)) map.setLayoutProperty(id, "text-field", ["coalesce", ["get", "name"], ["get", "name:de"], ["get", "name_en"]]);
  }
  for (const id of ["watername_ocean", "watername_sea", "watername_lake", "watername_lake_line", "waterway_label"]) {
    label(id, p.coast);
    paint(id, "text-opacity", 0.8);
  }
  updatePublicMapLayerVisibility(map);
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
