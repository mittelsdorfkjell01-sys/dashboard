import type { ExpressionSpecification, StyleSpecification } from "maplibre-gl";

/**
 * The spot map's ground, drawn after Apple Maps' standard (light) map:
 * warm off-white land, soft blue water, pale green parks, white streets with a
 * faint casing, warm yellow motorways and grey haloed names. Vector tiles from
 * OpenFreeMap (OpenMapTiles schema) — free, keyless and without request
 * limits; glyphs come from the same host. Both are in the CSP's connect-src.
 *
 * In dark mode (2026-11-22, "gedämpft") the same map is taken back: dark,
 * desaturated land a step above the house page, a blue-grey sea, dim streets,
 * light names on a dark halo. The place card (#1A1F24, hairline + float
 * shadow) still lifts off it. Before, the map stayed light in both themes and
 * stood out on the dark Spot-Info page.
 *
 * Basemap POIs are not drawn: the map's own pins (OpenStreetMap via Overpass,
 * with opening hours and details) are the only places on it.
 */
const TILES_URL = "https://tiles.openfreemap.org/planet";
const GLYPHS_URL = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";

const FONT = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];
const FONT_ITALIC = ["Noto Sans Italic"];

const NAME: ExpressionSpecification = ["coalesce", ["get", "name:de"], ["get", "name"]];

const LIGHT = {
  land: "#F4F2EE",
  urban: "#EEEBE6",
  park: "#D3EBC6",
  wood: "#C8E4B8",
  sand: "#F5EDD3",
  water: "#A9D3F2",
  waterLine: "#94C5EC",
  building: "#E6E2DC",
  buildingEdge: "#DAD5CE",
  roadCase: "#DEDAD3",
  road: "#FFFFFF",
  highway: "#FFD970",
  highwayCase: "#E9BC4C",
  rail: "#CFCBC4",
  path: "#D8D3CB",
  label: "#3C3C40",
  labelSoft: "#77777C",
  waterLabel: "#4D86B5",
  halo: "#FFFFFF",
};

const DARK: typeof LIGHT = {
  land: "#262A2E",
  urban: "#2A2E32",
  park: "#22302A",
  wood: "#1F2D25",
  sand: "#302E28",
  water: "#1C3443",
  waterLine: "#24465A",
  building: "#30343A",
  buildingEdge: "#383C42",
  roadCase: "#1E2125",
  road: "#3C4147",
  highway: "#7A6A3C",
  highwayCase: "#5A4F2E",
  rail: "#3A3E44",
  path: "#45494F",
  label: "#DCD8D2",
  labelSoft: "#9EA1A6",
  waterLabel: "#86AEC9",
  halo: "#1A1E22",
};

const roadWidth = (base: number, z18: number): ExpressionSpecification =>
  ["interpolate", ["exponential", 1.6], ["zoom"], 10, base, 18, z18];

const roadClass = (...classes: string[]): ExpressionSpecification =>
  ["match", ["get", "class"], classes, true, false];

export function standardStyle(theme: "light" | "dark" = "light"): StyleSpecification {
  const C = theme === "dark" ? DARK : LIGHT;
  return {
    version: 8,
    glyphs: GLYPHS_URL,
    sources: { base: { type: "vector", url: TILES_URL } },
    layers: [
      { id: "land", type: "background", paint: { "background-color": C.land } },
      {
        id: "urban", type: "fill", source: "base", "source-layer": "landuse",
        filter: roadClass("residential", "commercial", "retail", "industrial", "suburb", "neighbourhood"),
        paint: { "fill-color": C.urban },
      },
      {
        id: "wood", type: "fill", source: "base", "source-layer": "landcover",
        filter: roadClass("wood", "forest"),
        paint: { "fill-color": C.wood },
      },
      {
        id: "grass", type: "fill", source: "base", "source-layer": "landcover",
        filter: roadClass("grass", "meadow", "scrub", "wetland"),
        paint: { "fill-color": C.park, "fill-opacity": 0.8 },
      },
      {
        id: "sand", type: "fill", source: "base", "source-layer": "landcover",
        filter: roadClass("sand", "beach"),
        paint: { "fill-color": C.sand },
      },
      { id: "park", type: "fill", source: "base", "source-layer": "park", paint: { "fill-color": C.park } },
      {
        id: "pitch", type: "fill", source: "base", "source-layer": "landuse",
        filter: roadClass("pitch", "stadium", "playground", "cemetery", "garden"),
        paint: { "fill-color": C.park, "fill-opacity": 0.7 },
      },
      { id: "water", type: "fill", source: "base", "source-layer": "water", paint: { "fill-color": C.water } },
      {
        id: "waterway", type: "line", source: "base", "source-layer": "waterway",
        paint: { "line-color": C.waterLine, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 16, 2.5] },
      },
      {
        id: "building", type: "fill", source: "base", "source-layer": "building", minzoom: 14,
        paint: {
          "fill-color": C.building,
          "fill-outline-color": C.buildingEdge,
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 14, 0, 15, 1],
        },
      },
      {
        id: "path", type: "line", source: "base", "source-layer": "transportation", minzoom: 14,
        filter: roadClass("path", "track"),
        paint: { "line-color": C.path, "line-width": 1.2, "line-dasharray": [2, 1.5] },
      },
      {
        id: "rail", type: "line", source: "base", "source-layer": "transportation", minzoom: 11,
        filter: roadClass("rail", "transit"),
        paint: { "line-color": C.rail, "line-width": 1.4 },
      },
      {
        id: "road-minor-case", type: "line", source: "base", "source-layer": "transportation", minzoom: 13,
        filter: roadClass("minor", "service"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": C.roadCase, "line-width": roadWidth(1.5, 16) },
      },
      {
        id: "road-major-case", type: "line", source: "base", "source-layer": "transportation", minzoom: 8,
        filter: roadClass("primary", "secondary", "tertiary"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": C.roadCase, "line-width": roadWidth(2, 24) },
      },
      {
        id: "road-highway-case", type: "line", source: "base", "source-layer": "transportation", minzoom: 5,
        filter: roadClass("motorway", "trunk"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": C.highwayCase, "line-width": roadWidth(2.5, 28) },
      },
      {
        id: "road-minor", type: "line", source: "base", "source-layer": "transportation", minzoom: 13,
        filter: roadClass("minor", "service"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": C.road, "line-width": roadWidth(0.8, 13) },
      },
      {
        id: "road-major", type: "line", source: "base", "source-layer": "transportation", minzoom: 8,
        filter: roadClass("primary", "secondary", "tertiary"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": C.road, "line-width": roadWidth(1.2, 20) },
      },
      {
        id: "road-highway", type: "line", source: "base", "source-layer": "transportation", minzoom: 5,
        filter: roadClass("motorway", "trunk"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": C.highway, "line-width": roadWidth(1.5, 24) },
      },
      {
        id: "ferry", type: "line", source: "base", "source-layer": "transportation",
        filter: roadClass("ferry"),
        paint: { "line-color": C.waterLabel, "line-width": 0.8, "line-opacity": 0.25, "line-dasharray": [3, 3] },
      },
      {
        id: "water-name", type: "symbol", source: "base", "source-layer": "water_name",
        layout: { "text-field": NAME, "text-font": FONT_ITALIC, "text-size": 13, "text-max-width": 8 },
        paint: { "text-color": C.waterLabel, "text-halo-color": C.halo, "text-halo-width": 1 },
      },
      {
        id: "road-name", type: "symbol", source: "base", "source-layer": "transportation_name", minzoom: 14,
        // Ferry routes ("Kiel – Göteborg") are not street names; on the water
        // they were the loudest text on the map.
        filter: ["!", roadClass("ferry")],
        layout: {
          "symbol-placement": "line",
          "text-field": NAME,
          "text-font": FONT,
          "text-size": ["interpolate", ["linear"], ["zoom"], 14, 10.5, 18, 13],
          "text-rotation-alignment": "map",
        },
        paint: { "text-color": C.labelSoft, "text-halo-color": C.halo, "text-halo-width": 1.4 },
      },
      {
        id: "place-minor", type: "symbol", source: "base", "source-layer": "place", minzoom: 12,
        filter: roadClass("suburb", "neighbourhood", "hamlet", "quarter", "isolated_dwelling"),
        layout: {
          "text-field": NAME, "text-font": FONT, "text-size": 12,
          "text-transform": "uppercase", "text-letter-spacing": 0.08, "text-max-width": 8,
        },
        paint: { "text-color": C.labelSoft, "text-halo-color": C.halo, "text-halo-width": 1.4 },
      },
      {
        id: "place-village", type: "symbol", source: "base", "source-layer": "place", minzoom: 9,
        filter: roadClass("village"),
        layout: { "text-field": NAME, "text-font": FONT, "text-size": 13, "text-max-width": 8 },
        paint: { "text-color": C.label, "text-halo-color": C.halo, "text-halo-width": 1.5 },
      },
      {
        id: "place-town", type: "symbol", source: "base", "source-layer": "place",
        filter: roadClass("town", "city"),
        layout: {
          "text-field": NAME, "text-font": FONT_BOLD,
          "text-size": ["interpolate", ["linear"], ["zoom"], 8, 13, 14, 17], "text-max-width": 8,
        },
        paint: { "text-color": C.label, "text-halo-color": C.halo, "text-halo-width": 1.6 },
      },
    ],
  };
}
