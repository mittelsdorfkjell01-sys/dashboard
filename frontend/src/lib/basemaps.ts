// CARTO basemap raster tiles (shared by every in-app Leaflet map).
//
// CARTO watermarks keyless tiles ("API KEY REQUIRED") under load; a free key
// (https://carto.com/basemaps/apikey) removes it and is passed as a `key`
// query parameter on the tile URL. The key is resolved at build time from the
// environment (root .env CARTO_API_KEY / VITE_CARTO_KEY / the deploy env) and
// injected as __CARTO_KEY__ — see vite.config.ts. Empty = keyless (dev fallback).
const CARTO_KEY = __CARTO_KEY__.trim();

// Style slugs on the CARTO raster CDN.
export const CARTO_POSITRON = "light_all"; // clean, desaturated, Airbnb-style
export const CARTO_POSITRON_NOLABELS = "light_nolabels"; // clean light base, no labels
export const CARTO_LIGHT_LABELS = "light_only_labels"; // dark place labels for a light base
export const CARTO_DARK_ALL = "dark_all"; // dark ground with its own labels
export const CARTO_DARK_NOLABELS = "dark_nolabels";
export const CARTO_DARK_LABELS = "dark_only_labels";
export const CARTO_VOYAGER = "rastertiles/voyager";
export const CARTO_VOYAGER_NOLABELS = "rastertiles/voyager_nolabels";
export const CARTO_VOYAGER_LABELS = "rastertiles/voyager_only_labels"; // dark, haloed place labels

export const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

/** XYZ tile-URL template for a CARTO raster style, with the API key appended
 *  when one is configured. `retina` asks for CARTO's @2x raster: twice the
 *  pixels for the same tile extent, which is what keeps coastlines, roads and
 *  labels sharp on a high-DPR screen instead of an upscaled 256px blur
 *  (2026-10-12: "bei Wind ist das Land verschwommen"). */
export function cartoTileUrl(style: string, options?: { retina?: boolean }): string {
  // Pin a single CDN host so the document-level preconnect is always reused.
  // Standard-resolution tiles keep the raster payload down where the extra
  // detail is not visible anyway.
  const suffix = options?.retina ? "@2x" : "";
  const base = `https://a.basemaps.cartocdn.com/${style}/{z}/{x}/{y}${suffix}.png`;
  return CARTO_KEY ? `${base}?key=${CARTO_KEY}` : base;
}

/** True where a CARTO @2x raster is worth its payload. */
export function prefersRetinaTiles(): boolean {
  return (typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1) > 1.25;
}
