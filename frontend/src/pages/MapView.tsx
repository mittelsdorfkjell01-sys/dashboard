import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L, { type Map as LeafletMap } from "leaflet";
import Header from "../components/Header";
import SpotCard from "../components/SpotCard";
import { CloseIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { useSpots, useSpotsLive } from "../lib/hooks";

/** Navy teardrop pin as a Leaflet divIcon. */
const pinIcon = L.divIcon({
  className: "swd-pin",
  html: `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
        fill="#241C17" stroke="#ffffff" stroke-width="1.4"/>
      <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
    </svg>`,
  iconSize: [30, 38],
  iconAnchor: [15, 38],
  popupAnchor: [0, -34],
});

export default function MapView() {
  const navigate = useNavigate();
  const [map, setMap] = useState<LeafletMap | null>(null);
  const { data: spots } = useSpots();

  const withCoords = useMemo(
    () => (spots ?? []).filter((s) => s.coords),
    [spots]
  );
  const stripSpots = withCoords.slice(0, 5);
  const { data: live } = useSpotsLive(stripSpots.map((s) => s.id));
  const center = useMemo<[number, number]>(() => {
    if (withCoords.length === 0) return [40.3, 9.3];
    return [
      withCoords.reduce((a, s) => a + s.coords![0], 0) / withCoords.length,
      withCoords.reduce((a, s) => a + s.coords![1], 0) / withCoords.length,
    ];
  }, [withCoords]);

  return (
    <div data-lenis-prevent className="relative h-screen w-screen overflow-hidden">
      <Header showAccount={false} />
      <h1 className="sr-only">Spot-Karte</h1>

      <MapContainer
        key={withCoords.length ? "loaded" : "init"}
        center={center}
        zoom={7}
        zoomControl={false}
        scrollWheelZoom
        ref={setMap}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />

        {withCoords.map((spot) => (
          <Marker key={spot.id} position={spot.coords!} icon={pinIcon}>
            <Popup className="spot-popup" autoClose={false} closeOnClick={false}>
              <div className="w-[200px]">
                <SpotCard spot={spot} compact />
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Top-right controls: close (→ landing) + zoom */}
      <div className="pointer-events-none absolute right-4 top-4 z-[900] flex flex-col items-end gap-3 sm:right-6 sm:top-6">
        <button
          type="button"
          aria-label="Zur Startseite"
          onClick={() => navigate("/")}
          className="pointer-events-auto grid h-11 w-11 place-items-center rounded-2xl border border-line bg-white text-teal transition-colors hover:bg-line/40"
        >
          <CloseIcon className="text-[20px]" />
        </button>

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
      </div>

      {/* Recommended strip — evenly distributed across the full width */}
      <div className="absolute inset-x-0 bottom-0 z-[600] pb-5 pt-10">
        <div className="mx-auto flex max-w-[1400px] gap-x-6 overflow-x-auto no-scrollbar px-4 sm:overflow-visible sm:px-8">
          {stripSpots.map((spot) => (
            <div key={spot.id} className="w-[160px] shrink-0 sm:w-auto sm:min-w-0 sm:flex-1">
              <SpotCard spot={spot} compact live={live?.get(spot.id)} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
