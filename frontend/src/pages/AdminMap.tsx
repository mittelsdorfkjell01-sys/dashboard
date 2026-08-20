// Admin map: spots in the current viewport (incl. drafts), colour-coded by status — draft = light
// red, published = green, archived = grey. Markers link into the editor. Reads
// the same spots as everywhere else via a lightweight coordinates-only endpoint;
// it's an admin-only view, independent of the public map.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import Supercluster from "supercluster";
import { ApiError, archiveSpot, getAdminMapSpots, type AdminMapSpot } from "../lib/api";
import { statusLabel } from "../lib/labels";
import { PageHeader } from "../components/admin/ui";
import ConfirmToast from "../components/admin/ConfirmToast";
import { createAdminReturnState } from "../lib/adminNavigation";

const STATUS_COLOR: Record<string, string> = {
  published: "#4A8159", // grün
  draft: "#F87171", // hellrot
  archived: "#9CA3AF", // grau
};
const fallbackColor = "#9CA3AF";
type MapPoint = { spot: AdminMapSpot };
type Viewport = { bounds: [number, number, number, number]; zoom: number };

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

const clusterIcon = (count: number) =>
  L.divIcon({
    className: "swd-admin-cluster",
    html: `<span>${count}</span>`,
    iconSize: [42, 42],
    iconAnchor: [21, 21],
  });

export default function AdminMap() {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const editorState = createAdminReturnState(location, "Karte");
  const [spots, setSpots] = useState<AdminMapSpot[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Pending archive: set from a pin popup, confirmed via the top-right toast (✓).
  const [pending, setPending] = useState<{ id: string; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const requestSequence = useRef(0);
  // Archived spots are never drawn; visibility lives in the URL so returning
  // from an editor restores the same working view.
  const show = useMemo(() => ({
    published: params.get("published") !== "0",
    draft: params.get("draft") !== "0",
  }), [params]);

  const toggleVisibility = (key: "published" | "draft") => {
    const next = new URLSearchParams(params);
    if (show[key]) next.set(key, "0");
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const onArchive = async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      await archiveSpot(pending.id);
      setSpots((prev) =>
        prev.map((s) => (s.id === pending.id ? { ...s, status: "archived" } : s))
      );
      setPending(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Archivieren fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = { published: 0, draft: 0, archived: 0 };
    for (const s of spots) c[s.status] = (c[s.status] ?? 0) + 1;
    return c;
  }, [spots]);

  // Drawn spots: archived never shown; draft/published follow their toggle.
  const visibleSpots = useMemo(
    () =>
      spots.filter((s) => {
        if (s.status === "archived") return false;
        if (s.status === "published") return show.published;
        if (s.status === "draft") return show.draft;
        return true;
      }),
    [spots, show]
  );

  const center = useMemo<[number, number]>(() => {
    const lat = params.has("lat") ? Number(params.get("lat")) : Number.NaN;
    const lon = params.has("lon") ? Number(params.get("lon")) : Number.NaN;
    if (Number.isFinite(lat) && Number.isFinite(lon)) return [lat, lon];
    return [45, 10];
  }, [params]);

  const requestedZoom = params.has("z") ? Number(params.get("z")) : 6;
  const initialZoom = Number.isFinite(requestedZoom)
    ? Math.min(18, Math.max(2, requestedZoom))
    : 6;
  const [viewport, setViewport] = useState<Viewport>({
    bounds: [-180, -85, 180, 85],
    zoom: initialZoom,
  });
  const loadViewport = useCallback((next: Viewport) => {
    setViewport(next);
    setError(null);
    const sequence = ++requestSequence.current;
    getAdminMapSpots(next.bounds)
      .then((rows) => {
        if (sequence === requestSequence.current) setSpots(rows);
      })
      .catch((e) => {
        if (sequence === requestSequence.current) {
          setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.");
        }
      });
  }, []);
  const clusterIndex = useMemo(() => {
    const index = new Supercluster<MapPoint>({ radius: 54, maxZoom: 16 });
    return index.load(
      visibleSpots.map((spot) => ({
        type: "Feature" as const,
        properties: { spot },
        geometry: { type: "Point" as const, coordinates: [spot.lon, spot.lat] },
      }))
    );
  }, [visibleSpots]);
  const clusteredSpots = useMemo(
    () => clusterIndex.getClusters(viewport.bounds, Math.round(viewport.zoom)),
    [clusterIndex, viewport]
  );

  return (
    <div>
      <PageHeader
        title="Karte"
        actions={
          <div className="flex flex-wrap items-center gap-2 text-label">
            <LegendToggle
              color={STATUS_COLOR.published}
              label={`Veröffentlicht (${counts.published ?? 0} im Ausschnitt)`}
              active={show.published}
              onClick={() => toggleVisibility("published")}
            />
            <LegendToggle
              color={STATUS_COLOR.draft}
              label={`Entwurf (${counts.draft ?? 0} im Ausschnitt)`}
              active={show.draft}
              onClick={() => toggleVisibility("draft")}
            />
            <span className="text-admin-faint">Archiviert ({counts.archived ?? 0} im Ausschnitt) · ausgeblendet</span>
          </div>
        }
      />

      {error && (
        <div role="alert" className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger">
          {error}
        </div>
      )}

      <ConfirmToast
        open={pending !== null}
        message={`„${pending?.name ?? ""}" archivieren?`}
        busy={busy}
        onConfirm={onArchive}
        onCancel={() => setPending(null)}
      />

      <div data-lenis-prevent className="mt-4 h-[calc(100vh-220px)] min-h-[420px] overflow-hidden rounded-lg border border-admin-border">
        <MapContainer
          center={center}
          zoom={initialZoom}
          scrollWheelZoom
          className="h-full w-full"
        >
          <MapUrlState onViewport={loadViewport} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
          />
          {clusteredSpots.map((feature) => {
            const [lon, lat] = feature.geometry.coordinates;
            if ("cluster" in feature.properties && feature.properties.cluster) {
              return (
                <ClusterMarker
                  key={`cluster-${feature.properties.cluster_id}`}
                  position={[lat, lon]}
                  count={feature.properties.point_count}
                  expansionZoom={clusterIndex.getClusterExpansionZoom(
                    feature.properties.cluster_id
                  )}
                />
              );
            }
            const s = (feature.properties as MapPoint).spot;
            return (
            <Marker
              key={s.id}
              position={[s.lat, s.lon]}
              icon={pinIcon(STATUS_COLOR[s.status] ?? fallbackColor)}
              title={`Spot öffnen: ${s.name}`}
              alt={`Spot öffnen: ${s.name}`}
            >
              <Popup>
                {/* Inline colours: the Leaflet popup keeps a white background,
                    but the admin dark theme remaps `text-ink`/`text-muted` to
                    light — so set explicit dark colours here for legibility. */}
                <div className="min-w-[160px]">
                  <p className="text-label font-semibold" style={{ color: "#000" }}>
                    {s.name}
                  </p>
                  <p className="mt-0.5 text-caption" style={{ color: "#6B7280" }}>
                    {statusLabel(s.status)}
                  </p>
                  <div className="mt-2 flex items-center gap-3">
                    <Link
                      to={`/admin/spot/${s.id}/edit`}
                      state={editorState}
                      className="text-label font-medium hover:underline"
                      style={{ color: "#1E6E7E" }}
                    >
                      Bearbeiten →
                    </Link>
                    {s.status !== "archived" && (
                      <button
                        type="button"
                        onClick={() => setPending({ id: s.id, name: s.name })}
                        className="text-label font-medium text-admin-warning hover:underline"
                      >
                        Archivieren
                      </button>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}

function ClusterMarker({
  position,
  count,
  expansionZoom,
}: {
  position: [number, number];
  count: number;
  expansionZoom: number;
}) {
  const map = useMap();
  return (
    <Marker
      position={position}
      icon={clusterIcon(count)}
      eventHandlers={{ click: () => map.setView(position, expansionZoom) }}
      title={`${count} Spots anzeigen`}
      alt={`${count} Spots anzeigen`}
    />
  );
}

function MapUrlState({ onViewport }: { onViewport: (viewport: Viewport) => void }) {
  const [params, setParams] = useSearchParams();

  const map = useMapEvents({
    moveend(event) {
      const map = event.target;
      const center = map.getCenter();
      const bounds = map.getBounds();
      onViewport({
        bounds: [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
        zoom: map.getZoom(),
      });
      const next = new URLSearchParams(params);
      next.set("lat", center.lat.toFixed(5));
      next.set("lon", center.lng.toFixed(5));
      next.set("z", String(map.getZoom()));
      setParams(next, { replace: true });
    },
  });

  useEffect(() => {
    const bounds = map.getBounds();
    onViewport({
      bounds: [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
      zoom: map.getZoom(),
    });
  }, [map, onViewport]);

  return null;
}

// Legend entry that doubles as a show/hide toggle; dimmed + struck when off.
function LegendToggle({
  color,
  label,
  active,
  onClick,
}: {
  color: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={active ? "Ausblenden" : "Einblenden"}
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 transition-colors ${
        active
          ? "border-admin-border bg-admin-surface text-admin-fg2 hover:bg-admin-hover"
          : "border-transparent text-admin-faint line-through hover:text-admin-muted"
      }`}
    >
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: color, opacity: active ? 1 : 0.4 }}
      />
      {label}
    </button>
  );
}
