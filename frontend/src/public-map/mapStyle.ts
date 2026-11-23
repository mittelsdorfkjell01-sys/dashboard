import type { ExpressionSpecification, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import type { ExplorerMode } from "../weather-map/fieldUrlState";

/**
 * The ground of the public map (2026-11-19 redesign): ONE light vector style
 * for all three modes, derived from the Spot-Info locator's Apple-standard
 * palette (components/locator/standardStyle.ts) but taken much further back —
 * the field colours are the information here, the ground only says where land
 * and water are. OpenFreeMap vector tiles, keyless; already in the CSP.
 *
 * The style is split in two maps that share one camera: the GROUND under the
 * field canvases and the NAMES above them, so place names stay legible on top
 * of a full-colour wind field. Each mode only retunes paint, so switching mode
 * never reloads a tile.
 */
const TILES_URL = "https://tiles.openfreemap.org/planet";
const GLYPHS_URL = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
const FONT = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];
const FONT_ITALIC = ["Noto Sans Italic"];
const NAME: ExpressionSpecification = ["coalesce", ["get", "name:de"], ["get", "name"]];

const classIn = (...classes: string[]): ExpressionSpecification => ["match", ["get", "class"], classes, true, false];
const roadWidth = (base: number, z16: number): ExpressionSpecification => ["interpolate", ["exponential", 1.6], ["zoom"], 9, base, 16, z16];

/** Per mode: Spots shows the full (still quiet) ground; under Wind the land
 *  steps back a little so the field carries; under Waves the land is almost
 *  flat, because waves only exist on the sea.
 *
 *  Since 2026-11-20 the map follows the site theme (asked for explicitly; it
 *  was light in both themes before). The dark ground is the house dark page
 *  family (#0E1114 → #1A1F24) with a blue-grey sea, so the wind and wave
 *  colours keep their contrast and nothing reads as soot. */
export type MapTheme = "light" | "dark";

export const GROUND = {
  light: {
    spots: { land: "#F2EFE9", water: "#CFE2EC", coast: "#B9CCD5", green: "#E3ECD9", road: "#FFFFFF", border: "#C9C3BA" },
    wind: { land: "#ECE9E3", water: "#D6E3EA", coast: "#BCC9CF", green: "#E6E8DF", road: "#F7F6F3", border: "#C9C3BA" },
    // Waves (2026-11-21, revised: "wie bei 8 Knoten"): the land wears the
    // grey-blue the WIND map shows at ~8 kn (house ramp at 8 kn over the wind
    // land at the field's opacity, nudged a touch bluer), so switching
    // Wind → Wellen keeps one ground; the sea a step bluer still.
    waves: { land: "#C4D0D8", water: "#B6CAD8", coast: "#9DB0BD", green: "#C4D0D8", road: "#D4DDE3", border: "#AAB6BF" },
  },
  dark: {
    // Land sits BELOW the panel surface (#1A1F24), so the floating chrome
    // still reads as lifted off the map.
    spots: { land: "#111518", water: "#142733", coast: "#2E4450", green: "#141A17", road: "#262B30", border: "#353A3F" },
    wind: { land: "#101316", water: "#13222D", coast: "#2B3D47", green: "#131816", road: "#22272C", border: "#32373C" },
    // Dark: the same wind-at-8-kn grey-blue, which also lifts the wave map out
    // of near-black (2026-11-21, "heller").
    waves: { land: "#3A4A57", water: "#263847", coast: "#556776", green: "#3A4A57", road: "#475663", border: "#586470" },
  },
} as const;

const NAMES = {
  light: { water: "#4E7488", country: "#6B625B", town: "#3D332C", village: "#6B625B", halo: "rgba(255,255,255,0.92)", coast: "rgba(61,51,44,0.26)" },
  dark: { water: "#7FA3B8", country: "#9B928A", town: "#E4DED6", village: "#B5ADA4", halo: "rgba(14,17,20,0.9)", coast: "rgba(241,237,231,0.32)" },
} as const;

/** Water white on black: the mask that cuts the wave colour at the real coast. */
export function waterMaskStyle(): StyleSpecification {
  return {
    version: 8,
    sources: { base: { type: "vector", url: TILES_URL } },
    layers: [
      { id: "land", type: "background", paint: { "background-color": "#000000" } },
      { id: "water", type: "fill", source: "base", "source-layer": "water", paint: { "fill-color": "#ffffff", "fill-antialias": true } },
    ],
  };
}

export function groundStyle(mode: ExplorerMode, theme: MapTheme = "light"): StyleSpecification {
  const c = GROUND[theme][mode];
  return {
    version: 8,
    sources: { base: { type: "vector", url: TILES_URL } },
    layers: [
      { id: "land", type: "background", paint: { "background-color": c.land } },
      { id: "green", type: "fill", source: "base", "source-layer": "landcover", filter: classIn("wood", "forest", "grass"), paint: { "fill-color": c.green, "fill-opacity": 0.7 } },
      { id: "water", type: "fill", source: "base", "source-layer": "water", paint: { "fill-color": c.water } },
      { id: "coast", type: "line", source: "base", "source-layer": "water", paint: { "line-color": c.coast, "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.4, 10, 1] } },
      { id: "road", type: "line", source: "base", "source-layer": "transportation", minzoom: 8, filter: classIn("motorway", "trunk", "primary", "secondary"), layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": c.road, "line-width": roadWidth(0.6, 8) } },
      { id: "boundary", type: "line", source: "base", "source-layer": "boundary", filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1]], paint: { "line-color": c.border, "line-width": 0.8, "line-dasharray": [3, 2] } },
    ],
  };
}

/** Names only, drawn above the field. Country names at low zoom, towns from
 *  6, villages from 10 — sparse, because the spot pills also need room. */
export function namesStyle(theme: MapTheme = "light"): StyleSpecification {
  const n = NAMES[theme];
  return {
    version: 8,
    glyphs: GLYPHS_URL,
    sources: { base: { type: "vector", url: TILES_URL } },
    layers: [
      // The coastline ABOVE the colour field, so the land stays readable
      // under a full wind field (2026-11-20).
      { id: "coastline", type: "line", source: "base", "source-layer": "water", paint: { "line-color": n.coast, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.4, 10, 0.8] }, layout: { visibility: "none" } },
      {
        id: "water-name", type: "symbol", source: "base", "source-layer": "water_name", minzoom: 4,
        layout: { "text-field": NAME, "text-font": FONT_ITALIC, "text-size": 12, "text-max-width": 8 },
        paint: { "text-color": n.water, "text-halo-color": n.halo, "text-halo-width": 0 },
      },
      {
        id: "country", type: "symbol", source: "base", "source-layer": "place", maxzoom: 6,
        filter: classIn("country"),
        layout: { "text-field": NAME, "text-font": FONT, "text-size": 12, "text-transform": "uppercase", "text-letter-spacing": 0.12, "text-max-width": 7 },
        paint: { "text-color": n.country, "text-halo-color": n.halo, "text-halo-width": 0 },
      },
      {
        id: "town", type: "symbol", source: "base", "source-layer": "place", minzoom: 6,
        filter: classIn("city", "town"),
        layout: { "text-field": NAME, "text-font": FONT_BOLD, "text-size": ["interpolate", ["linear"], ["zoom"], 6, 11, 12, 14], "text-max-width": 8 },
        paint: { "text-color": n.town, "text-halo-color": n.halo, "text-halo-width": 0 },
      },
      {
        id: "village", type: "symbol", source: "base", "source-layer": "place", minzoom: 10,
        filter: classIn("village"),
        layout: { "text-field": NAME, "text-font": FONT, "text-size": 12, "text-max-width": 8 },
        paint: { "text-color": n.village, "text-halo-color": n.halo, "text-halo-width": 0 },
      },
    ],
  };
}

type PaintKey = "background-color" | "fill-color" | "line-color" | "text-color" | "text-halo-color";
function setter(map: MapLibreMap) {
  return (layer: string, prop: PaintKey, value: string) => { if (map.getLayer(layer)) map.setPaintProperty(layer, prop, value); };
}

/** Retune an already loaded ground map to another mode or theme (no tile reload). */
export function applyGround(map: MapLibreMap, mode: ExplorerMode, theme: MapTheme = "light") {
  const c = GROUND[theme][mode];
  const set = setter(map);
  set("land", "background-color", c.land);
  set("green", "fill-color", c.green);
  set("water", "fill-color", c.water);
  set("coast", "line-color", c.coast);
  set("road", "line-color", c.road);
  set("boundary", "line-color", c.border);
}

export function applyNames(map: MapLibreMap, theme: MapTheme) {
  const n = NAMES[theme];
  const set = setter(map);
  set("coastline", "line-color", n.coast);
  for (const [layer, color] of [["water-name", n.water], ["country", n.country], ["town", n.town], ["village", n.village]] as const) {
    set(layer, "text-color", color);
    set(layer, "text-halo-color", n.halo);
  }
}

/** The coastline over the field is for the wind map only: on Spots the ground
 *  already shows the coast, on Waves the colour itself stops at it. */
export function showCoastline(map: MapLibreMap, visible: boolean) {
  if (map.getLayer("coastline")) map.setLayoutProperty("coastline", "visibility", visible ? "visible" : "none");
}
