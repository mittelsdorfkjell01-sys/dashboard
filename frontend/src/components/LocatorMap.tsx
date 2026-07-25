import { useState } from "react";
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

/**
 * "Lage" — a real, interactive OpenStreetMap (Figma Frame_9): persistent
 * +/- zoom controls top-left, a "Maps" button below them that (like the
 * marker) opens the device's map app / Google Maps via `lib/mapLinks`.
 */
export default function LocatorMap({ coords }: { coords: [number, number] }) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const [lat, lng] = coords;
  const link = mapLinkProps(lat, lng);

  return (
    <div className="relative overflow-hidden rounded-3xl">
      <MapContainer center={coords} zoom={13} zoomControl={false} scrollWheelZoom ref={setMap} className="h-[420px] w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={coords} icon={pinIcon} />
      </MapContainer>

      <div className="pointer-events-none absolute left-4 top-4 z-[500] flex flex-col items-start gap-3">
        <div className="pointer-events-auto flex flex-col overflow-hidden rounded-full border border-line bg-white">
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
          className="pointer-events-auto rounded-full border border-line bg-white px-4 py-2 text-label font-medium text-ink transition-colors hover:bg-line/40"
        >
          Maps
        </a>
      </div>
    </div>
  );
}
