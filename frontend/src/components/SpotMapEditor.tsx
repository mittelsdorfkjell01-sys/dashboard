// Position + frame editor for the admin spot form. It renders the SAME base map
// as the public Daten-tab flow map (SpotFlowMap): identical CARTO
// `voyager_nolabels` tiles, the same 4/5→21/9 aspect, the same 256px Leaflet
// zoom, the same orange pin and the same default framing (centre = pin,
// zoom = 14.5). So what an operator frames here is exactly the excerpt visitors
// see on the Daten page — pin and cut-out match, and reopening the form shows
// precisely what was saved.
//
//   1) Position picker — click the map or drag the pin to set the spot's lat/lon.
//   2) Frame — pan/zoom sets the excerpt (centre + zoom) stored in
//      editorial.map_view and consumed by SpotFlowMap.
//
// Locking prevents a stray click/scroll from nudging a finished spot.

import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";

export interface MapView {
  /** [lat, lon] — matches editorial.map_view.center. */
  center: [number, number];
  /** Leaflet (256px) zoom — matches editorial.map_view.zoom + SpotFlowMap. */
  zoom: number;
}

// Orange teardrop pin — the same marker the public maps use.
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

const DEFAULT_CENTER: [number, number] = [54.4, 10.2];
const DEFAULT_ZOOM = 14.5; // = SpotFlowMap's MAP_ZOOM, so un-framed spots match.

function round(n: number, dp = 5): number {
  const f = 10 ** dp;
  return Math.round(n * f) / f;
}

// Captures clicks (set position) + move/zoom (set the frame). No-ops while
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

// Reactively enable/disable pan/zoom (MapContainer props are only read at init).
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

// The wrapper uses `aspect-ratio`, so the map's pixel height only settles after
// layout — recompute Leaflet's size once mounted so tiles fill the box.
function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    const id = requestAnimationFrame(() => map.invalidateSize());
    return () => cancelAnimationFrame(id);
  }, [map]);
  return null;
}

// Keep the pin in view when its coordinates *change* after mount (e.g. the
// operator typed lat/lon instead of clicking the map). Skips the first run so an
// intentional off-centre frame loaded from the server is never disturbed, and
// only recentres when the pin actually falls outside the current view.
function PinFollower({ pin }: { pin: [number, number] | null }) {
  const map = useMap();
  const first = useRef(true);
  const key = pin ? `${pin[0]},${pin[1]}` : "";
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (!pin) return;
    if (!map.getBounds().contains(pin)) {
      map.setView(pin, map.getZoom() < 12 ? DEFAULT_ZOOM : map.getZoom());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
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

  // Initial view (mount only): saved frame → pin → default. Matches SpotFlowMap's
  // default (centre = pin, zoom = 14.5) so an un-framed spot already lines up.
  const initial = useMemo<MapView>(
    () => ({
      center: mapView?.center ?? pin ?? DEFAULT_CENTER,
      zoom: mapView?.zoom ?? (hasPin ? DEFAULT_ZOOM : 6),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const gmaps = pin
    ? `https://www.google.com/maps/search/?api=1&query=${pin[0]},${pin[1]}`
    : "https://www.google.com/maps";

  return (
    // Same footprint/aspect as the Daten-tab flow map, so what you frame here is
    // exactly the excerpt the Daten page shows.
    <div>
      <div className="relative aspect-[4/5] w-full overflow-hidden rounded-lg border border-admin-border sm:aspect-[21/9]">
        <MapContainer
          center={initial.center}
          zoom={initial.zoom}
          zoomSnap={0.5}
          zoomControl={false}
          scrollWheelZoom={!locked}
          attributionControl={false}
          className="h-full w-full"
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
          />
          <InvalidateSize />
          <PinFollower pin={pin} />
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
          className={`absolute right-2 top-2 z-[500] rounded-md border px-3 py-1.5 text-[12px] font-medium transition-colors ${
            locked
              ? "border-admin-primary bg-admin-primary text-admin-primary-fg hover:bg-admin-primary-hover"
              : "border-admin-border bg-admin-surface text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg"
          }`}
        >
          {locked ? "🔒 Fixiert — Bearbeiten" : "✓ Fixieren"}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12px] text-admin-muted">
        <span>
          {locked
            ? 'Fixiert: Position & Ausschnitt sind gesperrt. „Bearbeiten" zum Ändern.'
            : 'Auf die Karte klicken oder den Pin ziehen (Position). Verschieben/Zoomen legt den Ausschnitt fest — genau so erscheint er auf der Daten-Seite. Danach „Fixieren".'}
        </span>
        <a
          href={gmaps}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded-md border border-admin-border bg-admin-surface px-2.5 py-1 font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
        >
          In Google Maps öffnen ↗
        </a>
      </div>
    </div>
  );
}
