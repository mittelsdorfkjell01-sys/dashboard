// Admin map: every spot (incl. drafts), colour-coded by status — draft = light
// red, published = green, archived = grey. Markers link into the editor. Reads
// the same spots as everywhere else via a lightweight coordinates-only endpoint;
// it's an admin-only view, independent of the public map.

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import { ApiError, getAdminMapSpots, type AdminMapSpot } from "../lib/api";
import { statusLabel } from "../lib/labels";

const STATUS_COLOR: Record<string, string> = {
  published: "#4A8159", // grün
  draft: "#F87171", // hellrot
  archived: "#9CA3AF", // grau
};
const fallbackColor = "#9CA3AF";

/** Teardrop pin as a Leaflet divIcon, filled with the status colour. */
const pinIcon = (color: string) =>
  L.divIcon({
    className: "swd-admin-pin",
    html: `<svg width="28" height="36" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
          fill="${color}" stroke="#ffffff" stroke-width="1.4"/>
        <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
      </svg>`,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
    popupAnchor: [0, -32],
  });

export default function AdminMap() {
  const [spots, setSpots] = useState<AdminMapSpot[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminMapSpots()
      .then(setSpots)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen."));
  }, []);

  const center = useMemo<[number, number]>(() => {
    if (spots.length === 0) return [40.3, 9.3];
    return [
      spots.reduce((a, s) => a + s.lat, 0) / spots.length,
      spots.reduce((a, s) => a + s.lon, 0) / spots.length,
    ];
  }, [spots]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { published: 0, draft: 0, archived: 0 };
    for (const s of spots) c[s.status] = (c[s.status] ?? 0) + 1;
    return c;
  }, [spots]);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-ui font-semibold text-ink sm:text-editorial-4">Karte</h1>
          <p className="mt-1 text-label text-muted">
            Alle Spots — Marker anklicken, um zu bearbeiten.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-label">
          <Legend color={STATUS_COLOR.published} label={`Veröffentlicht (${counts.published ?? 0})`} />
          <Legend color={STATUS_COLOR.draft} label={`Entwurf (${counts.draft ?? 0})`} />
          <Legend color={STATUS_COLOR.archived} label={`Archiviert (${counts.archived ?? 0})`} />
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700">
          {error}
        </div>
      )}

      <div className="mt-4 h-[calc(100vh-220px)] min-h-[420px] overflow-hidden rounded-2xl border border-line">
        <MapContainer
          key={spots.length ? "loaded" : "init"}
          center={center}
          zoom={6}
          scrollWheelZoom
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
          />
          {spots.map((s) => (
            <Marker
              key={s.id}
              position={[s.lat, s.lon]}
              icon={pinIcon(STATUS_COLOR[s.status] ?? fallbackColor)}
            >
              <Popup>
                <div className="min-w-[160px]">
                  <p className="text-label font-semibold text-ink">{s.name}</p>
                  <p className="mt-0.5 text-caption text-muted">{statusLabel(s.status)}</p>
                  <Link
                    to={`/admin/spot/${s.id}/edit`}
                    className="mt-2 inline-block text-label font-medium text-teal hover:underline"
                  >
                    Bearbeiten →
                  </Link>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted">
      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
