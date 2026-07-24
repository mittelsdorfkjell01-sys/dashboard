// Shared "open in maps" logic for spot coordinates — used by SpotIdentityCard
// and (Sprint 2) LocatorMap. Native geo: URIs open Apple/Google Maps directly
// on mobile; desktop browsers have no geo: handler, so there we fall back to
// a Google Maps web link in a new tab.

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

/** A single Esri World Imagery tile URL covering `[lat, lng]` at `zoom` — for
 *  a lightweight static satellite backdrop (the gallery's empty state) where
 *  mounting a whole interactive map would be overkill. Esri's tile scheme is
 *  z/y/x (not z/x/y like most other providers). */
export function satelliteTileUrl(lat: number, lng: number, zoom: number): string {
  const n = 2 ** zoom;
  const x = Math.floor(((lng + 180) / 360) * n);
  const latRad = toRad(lat);
  const y = Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n);
  return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${zoom}/${y}/${x}`;
}
