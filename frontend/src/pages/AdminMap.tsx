// Admin map: every spot (incl. drafts), colour-coded by status — draft = light
// red, published = green, archived = grey. Markers link into the editor. Reads
// the same spots as everywhere else via a lightweight coordinates-only endpoint;
// it's an admin-only view, independent of the public map.

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import { ApiError, archiveSpot, getAdminMapSpots, type AdminMapSpot } from "../lib/api";
import { statusLabel } from "../lib/labels";
import { PageHeader } from "../components/admin/ui";
import ConfirmToast from "../components/admin/ConfirmToast";

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
  // Pending archive: set from a pin popup, confirmed via the top-right toast (✓).
  const [pending, setPending] = useState<{ id: string; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  // Archived spots are never drawn; draft/published can be toggled off.
  const [show, setShow] = useState({ published: true, draft: true });

  useEffect(() => {
    getAdminMapSpots()
      .then(setSpots)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen."));
  }, []);

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
    const base = visibleSpots.length ? visibleSpots : spots;
    if (base.length === 0) return [40.3, 9.3];
    return [
      base.reduce((a, s) => a + s.lat, 0) / base.length,
      base.reduce((a, s) => a + s.lon, 0) / base.length,
    ];
    // Only recompute on first load, not on every toggle (avoid map jumps).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spots]);

  return (
    <div>
      <PageHeader
        title="Karte"
        description="Marker anklicken zum Bearbeiten. Archivierte Spots werden nicht angezeigt."
        actions={
          <div className="flex flex-wrap items-center gap-2 text-label">
            <LegendToggle
              color={STATUS_COLOR.published}
              label={`Veröffentlicht (${counts.published ?? 0})`}
              active={show.published}
              onClick={() => setShow((s) => ({ ...s, published: !s.published }))}
            />
            <LegendToggle
              color={STATUS_COLOR.draft}
              label={`Entwurf (${counts.draft ?? 0})`}
              active={show.draft}
              onClick={() => setShow((s) => ({ ...s, draft: !s.draft }))}
            />
            <span className="text-admin-faint">Archiviert ({counts.archived ?? 0}) · ausgeblendet</span>
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
          {visibleSpots.map((s) => (
            <Marker
              key={s.id}
              position={[s.lat, s.lon]}
              icon={pinIcon(STATUS_COLOR[s.status] ?? fallbackColor)}
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
                      className="text-label font-medium hover:underline"
                      style={{ color: "#1E6E7E" }}
                    >
                      Bearbeiten →
                    </Link>
                    {s.status !== "archived" && (
                      <button
                        type="button"
                        onClick={() => setPending({ id: s.id, name: s.name })}
                        className="text-label font-medium hover:underline"
                        style={{ color: "#B45309" }}
                      >
                        Archivieren
                      </button>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
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
