import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import { formatCoords, mapLinkProps } from "../lib/mapLinks";
import { isDaytime } from "../lib/sunTimes";

const ZOOM = 15;

// CARTO's free raster basemaps (no key) — Voyager by day (blue water, green
// parkland, warm land tones), Dark Matter by night. Which one renders is
// decided once per page load from the spot's own real local time, not a
// hover toggle: the map should look like "right now, at this coast", not a
// stylistic gimmick.
const DAY_TILE_URL = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const NIGHT_TILE_URL = "https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png";
const TILE_SUBDOMAINS = "abcd";

/** Leaflet renders no tiles when its container was sized 0 at init. */
function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
  }, [map]);
  return null;
}

/** Leaflet's built-in scale bar (styled in index.css to sit quietly on a
 *  photo instead of looking like browser chrome) — one of the small things
 *  that keeps a static, non-interactive map from reading as a screenshot. */
function ScaleControl() {
  const map = useMap();
  useEffect(() => {
    const control = L.control.scale({ metric: true, imperial: false, position: "bottomright" });
    control.addTo(map);
    return () => {
      control.remove();
    };
  }, [map]);
  return null;
}

// A dot + expanding pulse ring (animation in index.css), not a pin: pins
// imply "tap to drop/move me", which this static locator never does.
const MARKER_BOX = 40;
const markerIcon = L.divIcon({
  className: "swd-locator-marker",
  html: `
    <span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:16px;height:16px;">
      <span class="swd-locator-pulse" style="position:absolute;inset:0;border-radius:9999px;background:#E0823C;"></span>
      <span style="position:relative;display:block;width:100%;height:100%;border-radius:9999px;background:#E0823C;border:2px solid #ffffff;box-shadow:0 1px 4px rgba(0,0,0,.35);"></span>
    </span>
  `,
  iconSize: [MARKER_BOX, MARKER_BOX],
  iconAnchor: [MARKER_BOX / 2, MARKER_BOX / 2],
});

/**
 * Quiet locator map: where the spot sits in the region (zoom ~15), not the
 * beach itself — that's `SpotFlowMap`'s job on the Daten tab. A colored
 * cartographic basemap (CARTO, free, no key) rather than a satellite photo —
 * blue water, green parkland — switching between its day and night variant
 * based on whether it's actually daytime right now at the spot's own
 * coordinates.
 *
 * Purely a picture, not an interactive map: no drag/scroll/zoom, no
 * wind/wave overlay. The whole card is one link to Google Maps / the
 * device's map app (same `mapLinks` logic as `SpotIdentityCard`), so there's
 * no separate control to tab to. A slow tile "drift" and a hover state
 * (slight zoom + a fading-in "open in Maps" pill) keep it from reading as a
 * static screenshot; both stand still under `prefers-reduced-motion`.
 */
export default function LocatorMap({
  coords,
  contextLabel,
}: {
  coords: [number, number];
  /** e.g. "6 km von Fehmarn" — omitted entirely when there's nothing real to
   *  show it (no region center on record), never a guessed distance. */
  contextLabel?: string | null;
}) {
  const [lat, lng] = coords;
  const link = mapLinkProps(lat, lng);
  const tileUrl = isDaytime(lat, lng) ? DAY_TILE_URL : NIGHT_TILE_URL;

  return (
    <a
      href={link.href}
      target={link.target}
      rel={link.rel}
      role="link"
      aria-label="Auf Google Maps öffnen"
      className="group relative block"
    >
      <div className="relative overflow-hidden rounded-3xl transition-transform duration-500 ease-out group-hover:scale-[1.02]">
        <div className="swd-locator-drift aspect-[16/9] w-full">
          <MapContainer
            center={coords}
            zoom={ZOOM}
            zoomControl={false}
            scrollWheelZoom={false}
            dragging={false}
            doubleClickZoom={false}
            touchZoom={false}
            keyboard={false}
            attributionControl={false}
            className="swd-locator-map h-full w-full"
          >
            <TileLayer url={tileUrl} subdomains={TILE_SUBDOMAINS} />
            <Marker position={coords} icon={markerIcon} />
            <ScaleControl />
            <InvalidateSize />
          </MapContainer>
        </div>

        {contextLabel && (
          <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-caption text-ink shadow-pill">
            {contextLabel}
          </span>
        )}

        <span className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-0 transition-opacity duration-300 group-hover:opacity-100">
          <span className="rounded-full bg-white/95 px-4 py-2 text-caption font-medium text-teal shadow-pill backdrop-blur">
            Auf Google Maps öffnen
          </span>
        </span>
      </div>

      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-caption tabular-nums text-teal">{formatCoords(lat, lng)}</p>
        <p className="text-[10px] text-muted/80">© OpenStreetMap, © CARTO</p>
      </div>
    </a>
  );
}
