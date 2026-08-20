import type { Map as MapLibreMap } from "maplibre-gl";
import type { Spot } from "./types";
import { haversineKm } from "./mapLinks";

export type PublicMapTheme = "light" | "dark";

export const PUBLIC_MAP_STYLE_URL: Record<PublicMapTheme, string> = {
  light: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};

export const PUBLIC_MAP_PALETTE = {
  light: {
    water: "#D8E8ED", land: "#F3EFE7", urban: "#E9E3D9", park: "#DCE4D5",
    coast: "#78939A", boundary: "#9E948A", road: "#C9BBAA", roadMinor: "#DED4C8",
    label: "#241C17", secondary: "#6D655F", waterLabel: "#1C4E63",
  },
  dark: {
    water: "#102A35", land: "#1B292D", urban: "#26363A", park: "#263B37",
    coast: "#66828A", boundary: "#657276", road: "#66777B", roadMinor: "#485A5E",
    label: "#F1EDE7", secondary: "#AAB4B4", waterLabel: "#78B7D2",
  },
} as const;

export const PUBLIC_MAP_LAYER_RULES = {
  country: { minzoom: 2.8, maxzoom: 7 },
  state: { minzoom: 4.5, maxzoom: 10 },
  majorCity: { minzoom: 4.5, maxzoom: 10 },
  city: { minzoom: 6, maxzoom: 15 },
  town: { minzoom: 8, maxzoom: 16 },
  village: { minzoom: 10, maxzoom: 16 },
  hamlet: { minzoom: 12, maxzoom: 18 },
  roads: { major: 8, secondary: 12, minor: 13 },
  roadLabels: { major: 12, primary: 13, secondary: 14, minor: 15 },
  buildings: 15,
  localPoi: 14,
} as const;

const layerExists = (map: MapLibreMap, id: string) => Boolean(map.getLayer(id));

/** Apply Surfwinddata's restrained hierarchy to the real layer ids exposed by
 * CARTO's OpenMapTiles-compatible Voyager/Dark Matter styles. */
export function applyPublicMapStyle(map: MapLibreMap, theme: PublicMapTheme): void {
  const p = PUBLIC_MAP_PALETTE[theme];
  const paint = (id: string, property: string, value: unknown) => {
    if (layerExists(map, id)) map.setPaintProperty(id, property, value);
  };
  const zoom = (id: string, min: number, max = 24) => {
    if (layerExists(map, id)) map.setLayerZoomRange(id, min, max);
  };
  const hide = (id: string) => {
    if (layerExists(map, id)) map.setLayoutProperty(id, "visibility", "none");
  };
  const label = (id: string, color: string) => {
    if (!layerExists(map, id)) return;
    map.setPaintProperty(id, "text-color", color);
    map.setPaintProperty(id, "text-halo-color", theme === "light" ? "#F3EFE7" : "#152327");
    map.setPaintProperty(id, "text-halo-width", 1);
    map.setLayoutProperty(id, "text-allow-overlap", false);
  };

  paint("background", "background-color", p.land);
  paint("water", "fill-color", p.water);
  paint("water_shadow", "fill-color", p.coast);
  paint("landcover", "fill-color", p.land);
  paint("landuse", "fill-color", p.urban);
  paint("landuse_residential", "fill-color", p.urban);
  paint("park_national_park", "fill-color", p.park);
  paint("park_nature_reserve", "fill-color", p.park);
  paint("boundary_country_inner", "line-color", p.boundary);
  paint("boundary_country_outline", "line-color", p.boundary);
  paint("boundary_state", "line-color", p.boundary);
  paint("boundary_county", "line-color", p.boundary);

  for (const layer of map.getStyle().layers ?? []) {
    if (layer.type !== "line" || !("source-layer" in layer) || layer["source-layer"] !== "transportation") continue;
    paint(layer.id, "line-color", /minor|service|path|rail|taxiway/.test(layer.id) ? p.roadMinor : p.road);
  }

  for (const id of ["road_mot_fill_noramp", "road_trunk_fill_noramp", "road_pri_fill_noramp", "bridge_mot_fill", "bridge_trunk_fill", "bridge_pri_fill", "tunnel_mot_fill", "tunnel_trunk_fill", "tunnel_pri_fill"]) paint(id, "line-color", p.road);
  for (const id of ["road_sec_fill_noramp", "road_minor_fill", "road_service_fill", "road_path", "bridge_sec_fill", "bridge_minor_fill", "bridge_service_fill", "tunnel_sec_fill", "tunnel_minor_fill", "tunnel_service_fill"]) paint(id, "line-color", p.roadMinor);

  zoom("building", PUBLIC_MAP_LAYER_RULES.buildings);
  zoom("building-top", PUBLIC_MAP_LAYER_RULES.buildings);
  zoom("place_country_1", PUBLIC_MAP_LAYER_RULES.country.minzoom, PUBLIC_MAP_LAYER_RULES.country.maxzoom);
  zoom("place_country_2", PUBLIC_MAP_LAYER_RULES.country.minzoom, PUBLIC_MAP_LAYER_RULES.country.maxzoom);
  zoom("place_state", PUBLIC_MAP_LAYER_RULES.state.minzoom, PUBLIC_MAP_LAYER_RULES.state.maxzoom);
  for (const id of ["place_city_dot_r2", "place_city_dot_r4"]) zoom(id, PUBLIC_MAP_LAYER_RULES.majorCity.minzoom, 8);
  for (const id of ["place_city_dot_r7", "place_city_dot_z7", "place_capital_dot_z7"]) zoom(id, PUBLIC_MAP_LAYER_RULES.city.minzoom, 9);
  for (const id of ["place_city_r5", "place_city_r6"]) zoom(id, PUBLIC_MAP_LAYER_RULES.city.minzoom, PUBLIC_MAP_LAYER_RULES.city.maxzoom);
  zoom("place_town", PUBLIC_MAP_LAYER_RULES.town.minzoom, PUBLIC_MAP_LAYER_RULES.town.maxzoom);
  zoom("place_villages", PUBLIC_MAP_LAYER_RULES.village.minzoom, PUBLIC_MAP_LAYER_RULES.village.maxzoom);
  zoom("place_hamlet", PUBLIC_MAP_LAYER_RULES.hamlet.minzoom, PUBLIC_MAP_LAYER_RULES.hamlet.maxzoom);
  zoom("place_suburbs", 12, 17);
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
  for (const id of ["place_city_r5", "place_city_r6", "place_city_dot_r2", "place_city_dot_r4", "place_city_dot_r7", "place_city_dot_z7", "place_capital_dot_z7", "place_town", "place_villages", "place_hamlet", "place_suburbs", "roadname_major", "roadname_pri", "roadname_sec", "roadname_minor", "poi_park"]) label(id, p.label);
  for (const id of ["watername_ocean", "watername_sea", "watername_lake", "watername_lake_line", "waterway_label"]) {
    label(id, p.waterLabel);
    paint(id, "text-opacity", 0.72);
  }
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

export function clusterRadiusForZoom(zoom: number): number {
  if (zoom <= 5) return 64;
  if (zoom <= 7) return 52;
  if (zoom <= 9) return 42;
  if (zoom <= 10) return 32;
  return 3;
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
