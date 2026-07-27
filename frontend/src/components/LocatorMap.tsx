import { useEffect, useState } from "react";
import { MapContainer, Marker, TileLayer } from "react-leaflet";
import L, { type Map as LeafletMap } from "leaflet";
import { mapLinkProps } from "../lib/mapLinks";
import { MinusIcon, PlusIcon } from "../lib/icons";

/** Orange teardrop pin — standard OSM look per the Figma spec (Frame_9),
 *  not the satellite/photo-map treatment used elsewhere on the old design. */
const pinIcon = L.divIcon({
  className: "swd-pin",
  html: `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
        fill="#E0823C" stroke="#ffffff" stroke-width="1.4"/>
      <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
    </svg>`,
  iconSize: [30, 38],
  iconAnchor: [15, 38],
});

const HANDLERS = ["dragging", "scrollWheelZoom", "doubleClickZoom", "touchZoom", "boxZoom", "keyboard"] as const;

/**
 * "Lage" — the locator map (Figma Frame_9). Interaction is **click-to-activate**:
 * it starts locked (so scrolling the page never gets hijacked and there's no
 * hover overlay/warning); the first click enables pan/zoom, and a second click
 * on the map locks it again. The +/- zoom and "Maps" controls always work.
 */
export default function LocatorMap({ coords }: { coords: [number, number] }) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const [active, setActive] = useState(false);
  const [lat, lng] = coords;
  const link = mapLinkProps(lat, lng);

  // Enable/disable the interaction handlers to match the active state.
  useEffect(() => {
    if (!map) return;
    for (const h of HANDLERS) active ? map[h].enable() : map[h].disable();
  }, [map, active]);

  // While active, a plain click (not a drag) locks the map again.
  useEffect(() => {
    if (!map || !active) return;
    const lock = () => setActive(false);
    map.on("click", lock);
    return () => {
      map.off("click", lock);
    };
  }, [map, active]);

  return (
    <div className="relative overflow-hidden rounded-3xl">
      <MapContainer
        center={coords}
        zoom={13}
        zoomControl={false}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        touchZoom={false}
        boxZoom={false}
        keyboard={false}
        ref={setMap}
        className="h-[440px] w-full sm:h-[540px]"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />
        <Marker position={coords} icon={pinIcon} />
      </MapContainer>

      {/* Locked: a transparent catcher that activates on click — no text, no
          hover styling, so hovering the map changes nothing. */}
      {!active && (
        <button
          type="button"
          aria-label="Karte aktivieren"
          onClick={() => setActive(true)}
          className="absolute inset-0 z-[450] bg-transparent"
        />
      )}

      <div className="pointer-events-none absolute left-4 top-4 z-[500] flex flex-col items-start gap-3">
        <div className="pointer-events-auto flex flex-col overflow-hidden rounded-2xl border border-line bg-white">
          <button
            type="button"
            aria-label="Vergrößern"
            onClick={() => map?.zoomIn()}
            className="grid h-11 w-11 place-items-center text-teal transition-colors hover:bg-line/40"
          >
            <PlusIcon className="text-[20px]" />
          </button>
          <span className="mx-2 h-px bg-line" />
          <button
            type="button"
            aria-label="Verkleinern"
            onClick={() => map?.zoomOut()}
            className="grid h-11 w-11 place-items-center text-teal transition-colors hover:bg-line/40"
          >
            <MinusIcon className="text-[20px]" />
          </button>
        </div>

        <a
          href={link.href}
          target={link.target}
          rel={link.rel}
          className="pointer-events-auto rounded-2xl border border-line bg-white px-4 py-2 text-label font-medium text-ink transition-colors hover:bg-line/40"
        >
          Maps
        </a>
      </div>
    </div>
  );
}
