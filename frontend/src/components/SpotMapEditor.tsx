// Interactive map for the admin spot form (Sprint: admin UX). Two jobs in one:
//   1) Position picker — click the map or drag the pin to set the spot's lat/lon.
//   2) Preview framing — pan/zoom sets the map excerpt (center + zoom) that the
//      public spot page's wind/wave animation (SpotFlowMap) uses.
// Plus a "open in Google Maps" link to cross-check the exact location.

import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";

export interface MapView {
  center: [number, number];
  zoom: number;
}

const pinIcon = L.divIcon({
  className: "swd-pin",
  html: `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
        fill="#241C17" stroke="#ffffff" stroke-width="1.4"/>
      <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
    </svg>`,
  iconSize: [30, 38],
  iconAnchor: [15, 38],
});

const DEFAULT_CENTER: [number, number] = [54.4, 10.2];

function round(n: number, dp = 5): number {
  const f = 10 ** dp;
  return Math.round(n * f) / f;
}

// Captures clicks (set position) + move/zoom (set preview frame). No-ops while
// locked so a stray click/scroll can't nudge a finished spot.
function Events({
  locked,
  onPick,
  onView,
}: {
  locked: boolean;
  onPick: (lat: number, lon: number) => void;
  onView: (v: MapView) => void;
}) {
  const map = useMapEvents({
    click(e) {
      if (locked) return;
      onPick(round(e.latlng.lat), round(e.latlng.lng));
    },
    moveend() {
      if (locked) return;
      const c = map.getCenter();
      onView({ center: [round(c.lat), round(c.lng)], zoom: round(map.getZoom(), 2) });
    },
    zoomend() {
      if (locked) return;
      const c = map.getCenter();
      onView({ center: [round(c.lat), round(c.lng)], zoom: round(map.getZoom(), 2) });
    },
  });
  return null;
}

// Reactively enable/disable the map's pan/zoom handlers (MapContainer props are
// only read at init, so lock changes must be applied imperatively).
function LockController({ locked }: { locked: boolean }) {
  const map = useMap();
  useEffect(() => {
    const handlers = [
      map.dragging,
      map.scrollWheelZoom,
      map.doubleClickZoom,
      map.touchZoom,
      map.boxZoom,
      map.keyboard,
    ];
    handlers.forEach((h) => (locked ? h.disable() : h.enable()));
  }, [map, locked]);
  return null;
}

export default function SpotMapEditor({
  lat,
  lon,
  mapView,
  onPositionChange,
  onViewChange,
}: {
  lat: number | null;
  lon: number | null;
  mapView: MapView | null;
  onPositionChange: (lat: number, lon: number) => void;
  onViewChange: (v: MapView) => void;
}) {
  const hasPin = lat != null && lon != null && !Number.isNaN(lat) && !Number.isNaN(lon);
  const pin: [number, number] | null = hasPin ? [lat as number, lon as number] : null;

  // Start locked when a position already exists (editing) so a stray click can't
  // move it; unlocked for a fresh spot that still needs a position.
  const [locked, setLocked] = useState(hasPin);

  // Initial view (only used at mount): saved frame → pin → default.
  const initial = useMemo<MapView>(
    () => ({
      center: mapView?.center ?? pin ?? DEFAULT_CENTER,
      zoom: mapView?.zoom ?? (hasPin ? 14 : 6),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const gmaps = pin
    ? `https://www.google.com/maps/search/?api=1&query=${pin[0]},${pin[1]}`
    : "https://www.google.com/maps";

  return (
    // Same footprint as the public spot page's flow map (~480×360 in its grid
    // column), so what you frame here is what the spot page shows.
    <div className="max-w-[480px]">
      <div className="relative overflow-hidden rounded-2xl border border-line">
        <MapContainer
          center={initial.center}
          zoom={initial.zoom}
          zoomSnap={0.5}
          scrollWheelZoom={!locked}
          className="h-[360px] w-full"
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
          />
          <LockController locked={locked} />
          <Events locked={locked} onPick={onPositionChange} onView={onViewChange} />
          {pin && (
            <Marker
              key={locked ? "locked" : "unlocked"}
              position={pin}
              icon={pinIcon}
              draggable={!locked}
              eventHandlers={{
                dragend(e) {
                  const p = (e.target as L.Marker).getLatLng();
                  onPositionChange(round(p.lat), round(p.lng));
                },
              }}
            />
          )}
        </MapContainer>

        {/* Lock toggle */}
        <button
          type="button"
          onClick={() => setLocked((v) => !v)}
          className={`absolute right-2 top-2 z-[500] rounded-full border border-line px-3 py-1.5 text-[12px] font-medium ${
            locked
              ? "bg-teal text-white hover:bg-teal-hover"
              : "bg-white text-teal hover:bg-teal/5"
          }`}
        >
          {locked ? "🔒 Fixiert — Bearbeiten" : "✓ Fixieren"}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12px] text-muted">
        <span>
          {locked
            ? 'Fixiert: Position & Ausschnitt sind gesperrt. „Bearbeiten" zum Ändern.'
            : 'Auf die Karte klicken oder den Pin ziehen (Position). Verschieben/Zoomen legt den Vorschau-Rahmen fest. Danach „Fixieren".'}
        </span>
        <a
          href={gmaps}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded-lg border border-line px-2.5 py-1 font-medium text-teal hover:bg-teal/5"
        >
          In Google Maps öffnen ↗
        </a>
      </div>
    </div>
  );
}
