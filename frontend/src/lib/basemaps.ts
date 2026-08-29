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
export const CARTO_VOYAGER = "rastertiles/voyager";
export const CARTO_VOYAGER_NOLABELS = "rastertiles/voyager_nolabels";

export const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

/** XYZ tile-URL template for a CARTO raster style, with the API key appended
 *  when one is configured. */
export function cartoTileUrl(style: string): string {
  const base = `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png`;
  return CARTO_KEY ? `${base}?key=${CARTO_KEY}` : base;
}
