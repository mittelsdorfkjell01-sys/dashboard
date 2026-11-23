// Shared "open in maps" logic for spot coordinates — used by SpotHeaderCard
// and (Sprint 2) LocatorMap. Native geo: URIs open Apple/Google Maps directly
// on mobile; desktop browsers have no geo: handler, so there we fall back to
// a Google Maps web link in a new tab.

import { isDaytime } from "./sunTimes";

const isMobile = () =>
  typeof navigator !== "undefined" && /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

export function geoUri(lat: number, lng: number): string {
  return `geo:${lat},${lng}?q=${lat},${lng}`;
}

export function googleMapsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
}

/** href (+ target/rel for the desktop fallback) for a "open in maps" link,
 *  picked by device: geo: in place on mobile, Google Maps in a new tab
 *  everywhere else. */
export function mapLinkProps(
  lat: number,
  lng: number
): { href: string; target?: "_blank"; rel?: string } {
  if (isMobile()) return { href: geoUri(lat, lng) };
  return { href: googleMapsUrl(lat, lng), target: "_blank", rel: "noopener noreferrer" };
}

/**
 * Safari on macOS, iOS or iPadOS — the browser, not the device: Chrome,
 * Firefox, Edge and Opera on an iPhone or a Mac name themselves in the user
 * agent and get Google Maps (2026-11-21, was every Apple device). In-app
 * browsers without "Safari/" in the agent count as not Safari.
 */
export function isSafari(
  ua: string = typeof navigator === "undefined" ? "" : navigator.userAgent,
): boolean {
  return /Safari\//.test(ua)
    && /Macintosh|iPhone|iPad|iPod/.test(ua)
    && !/Chrome|Chromium|CriOS|FxiOS|EdgiOS|Edg\/|OPR|OPiOS|Android/.test(ua);
}

/** The maps app the hand-off links open, for their label. */
export function mapsAppName(): "Apple Karten" | "Google Maps" {
  return isSafari() ? "Apple Karten" : "Google Maps";
}

/**
 * Opens a place in the rider's maps app, where photos, reviews, current
 * hours and the route are one tap away — we show none of that ourselves.
 * Apple Maps searches `label` around the coordinate. Google Maps takes either
 * a text or a coordinate, never both: a name alone could land on a namesake
 * elsewhere, so it gets the name only together with an address.
 */
export function placeUrl(
  [lat, lng]: [number, number],
  { label, address }: { label?: string | null; address?: string | null } = {},
): string {
  if (isSafari()) {
    const params = new URLSearchParams({ ll: `${lat},${lng}` });
    if (label) params.set("q", label);
    return `https://maps.apple.com/?${params.toString()}`;
  }
  const query = label && address ? `${label}, ${address}` : `${lat},${lng}`;
  return `https://www.google.com/maps/search/?${new URLSearchParams({ api: "1", query }).toString()}`;
}

/**
 * Route hand-off to the rider's own maps app. We never compute a route: the
 * navigation app knows traffic, ferries and closures, and it is free. Safari
 * gets Apple Maps (maps.apple.com opens the app on iOS and macOS), every
 * other browser Google Maps. Without an origin both apps start from the
 * device's current position.
 */
export function directionsUrl(
  destination: [number, number],
  origin?: [number, number] | null,
): string {
  const [lat, lng] = destination;
  if (isSafari()) {
    const params = new URLSearchParams({ daddr: `${lat},${lng}`, dirflg: "d" });
    if (origin) params.set("saddr", `${origin[0]},${origin[1]}`);
    return `https://maps.apple.com/?${params.toString()}`;
  }
  const params = new URLSearchParams({ api: "1", destination: `${lat},${lng}`, travelmode: "driving" });
  if (origin) params.set("origin", `${origin[0]},${origin[1]}`);
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

export function formatCoords(lat: number, lng: number): string {
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

const EARTH_RADIUS_KM = 6371;
const toRad = (deg: number) => (deg * Math.PI) / 180;

/** Great-circle distance between two [lat, lng] points, in km — used for the
 *  LocatorMap's "N km von <Ort>" context label, computed from the spot's real
 *  coordinates and the region's real center (never invented). */
export function haversineKm(a: [number, number], b: [number, number]): number {
  const [lat1, lon1] = a;
  const [lat2, lon2] = b;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

const DAY_TILE_BASE = "https://a.basemaps.cartocdn.com/rastertiles/voyager";
const NIGHT_TILE_BASE = "https://a.basemaps.cartocdn.com/rastertiles/dark_all";

/** A single CARTO basemap tile (blue water, green parkland — day "Voyager" or
 *  night "Dark Matter", picked by whether it's actually daytime right now at
 *  `[lat, lng]`) covering that coordinate at `zoom` — for a lightweight static
 *  backdrop (the gallery's empty state) where mounting a whole interactive
 *  map would be overkill. Standard z/x/y tile scheme. `now` is only there so
 *  tests can pin the day/night pick to a specific moment. */
export function coloredTileUrl(lat: number, lng: number, zoom: number, now: Date = new Date()): string {
  const n = 2 ** zoom;
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = toRad(lat);
  const y = Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n);
  const base = isDaytime(lat, lng, now) ? DAY_TILE_BASE : NIGHT_TILE_BASE;
  return `${base}/${zoom}/${x}/${y}.png`;
}
