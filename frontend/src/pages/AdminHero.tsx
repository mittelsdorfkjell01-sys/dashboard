// Admin "Hero" tab — curate the landing-hero reel. Every spot with a hero photo
// is listed as a 16:9 tile; a checkbox adds/removes it from the rotation that
// cycles full-screen on the landing (image.hero_reel). Clicking a tile opens the
// mobile-crop editor, because a landscape hero cropped to a phone's tall frame
// often needs a different focal point than the wide desktop one.

import { useEffect, useMemo, useState } from "react";
import {
  getAdminSpots,
  resolveMediaUrl,
  setSpotImageHeroReel,
  setSpotImageFocalMobile,
  type AdminSpotSummary,
  type SpotRead,
} from "../lib/api";
import { countryName } from "../lib/flags";
import { responsiveImageAttributes } from "../lib/heroSource";
import ImageFocalEditor from "../components/ImageFocalEditor";
import { Badge, Button } from "../components/admin/ui";

type HeroSpot = Pick<AdminSpotSummary, "id" | "name" | "region_name" | "region_country" | "image">;

/** object-position for the desktop tile preview, from the stored focal point. */
function focalStyle(spot: HeroSpot): React.CSSProperties {
  const f = spot.image?.focal;
  const rotation = Math.max(-5, Math.min(5, spot.image?.rotation ?? 0));
  return {
    objectPosition: f ? `${f.x}% ${f.y}%` : undefined,
    transform: rotation
      ? `rotate(${rotation}deg) scale(${1 + Math.abs(rotation) * 0.04})`
      : undefined,
  };
}

export default function AdminHero() {
  const [spots, setSpots] = useState<HeroSpot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<HeroSpot | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    getAdminSpots({ limit: 500, sort: "name" })
      .then((r) => {
        if (!alive) return;
        setSpots(r.items.filter((s) => s.image?.url));
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : "Laden fehlgeschlagen."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  // Merge a spot back in after a save (the endpoints return the full SpotRead).
  const applyUpdate = (updated: SpotRead) => {
    setSpots((list) => list.map((s) => (s.id === updated.id ? { ...s, image: updated.image } : s)));
    setEditing((cur) => (cur && cur.id === updated.id ? { ...cur, image: updated.image } : cur));
  };

  const toggleReel = async (spot: HeroSpot, next: boolean) => {
    const updated = await setSpotImageHeroReel(spot.id, next);
    applyUpdate(updated);
  };

  // Curated photos first, then the rest — same order as the reel would show.
  const ordered = useMemo(() => {
    return [...spots].sort((a, b) => {
      const ar = a.image?.hero_reel ? 0 : 1;
      const br = b.image?.hero_reel ? 0 : 1;
      return ar - br || a.name.localeCompare(b.name);
    });
  }, [spots]);

  const inReel = spots.filter((s) => s.image?.hero_reel).length;

  return (
    <div className="mx-auto max-w-[1200px]">
      <div className="mb-6">
        <h1 className="text-title font-semibold text-admin-fg">Hero-Rotation</h1>
        <p className="mt-1 max-w-[70ch] text-label text-admin-muted">
          Wähle per Haken, welche Hero-Bilder im Landing-Hero durchlaufen. Ist nichts
          ausgewählt, zeigt der Hero alle Spots mit Bild. Klick auf ein Bild öffnet den
          mobilen Bildausschnitt.
        </p>
        <div className="mt-3">
          <Badge tone={inReel > 0 ? "primary" : "neutral"}>
            {inReel} in der Rotation
          </Badge>
        </div>
      </div>

      {loading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-video animate-pulse rounded-lg bg-admin-hover" />
          ))}
        </div>
      )}

      {error && !loading && (
        <div role="alert" className="rounded-lg border border-admin-danger-border bg-admin-danger-bg px-4 py-3 text-label text-admin-danger">
          {error}
        </div>
      )}

      {!loading && !error && ordered.length === 0 && (
        <div className="rounded-lg border border-admin-border bg-admin-surface px-5 py-10 text-center text-label text-admin-muted">
          Noch keine Spots mit Hero-Bild.
        </div>
      )}

      {!loading && !error && ordered.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {ordered.map((spot) => {
            const on = Boolean(spot.image?.hero_reel);
            const region = [spot.region_name, countryName(spot.region_country ?? undefined)]
              .filter(Boolean)
              .join(" · ");
            return (
              <div key={spot.id} className="group flex flex-col">
                <div
                  className={`relative overflow-hidden rounded-lg border transition-colors ${
                    on ? "border-admin-primary ring-1 ring-admin-primary" : "border-admin-border"
                  }`}
                >
                  {/* Clicking the image → mobile crop editor. */}
                  <button
                    type="button"
                    onClick={() => setEditing(spot)}
                    aria-label={`Mobilen Ausschnitt für ${spot.name} wählen`}
                    className="block aspect-video w-full"
                  >
                    <img
                      {...responsiveImageAttributes(
                        resolveMediaUrl(spot.image?.url),
                        spot.image?.width,
                        "(max-width: 639px) 50vw, 25vw",
                      )}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                      style={focalStyle(spot)}
                    />
                  </button>

                  {/* Reel checkbox — top-left, over the photo. */}
                  <label
                    className="absolute left-2 top-2 flex cursor-pointer items-center gap-2 rounded-md bg-black/55 px-2 py-1 text-caption font-medium text-white backdrop-blur-sm"
                    title="In die Hero-Rotation aufnehmen"
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={(e) => void toggleReel(spot, e.target.checked)}
                      className="h-4 w-4 accent-admin-primary"
                    />
                    In Rotation
                  </label>

                  {spot.image?.focal_mobile && (
                    <span className="absolute bottom-2 right-2 rounded-md bg-black/55 px-2 py-0.5 text-caption font-medium text-white backdrop-blur-sm">
                      Mobil ✓
                    </span>
                  )}
                </div>

                <div className="mt-2 min-w-0">
                  <p className="truncate text-label font-medium text-admin-fg">{spot.name}</p>
                  {region && <p className="truncate text-caption text-admin-muted">{region}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <MobileCropDialog
          spot={editing}
          onClose={() => setEditing(null)}
          onToggleReel={(next) => toggleReel(editing, next)}
          onSaved={applyUpdate}
        />
      )}
    </div>
  );
}

function MobileCropDialog({
  spot,
  onClose,
  onToggleReel,
  onSaved,
}: {
  spot: HeroSpot;
  onClose: () => void;
  onToggleReel: (next: boolean) => Promise<void>;
  onSaved: (updated: SpotRead) => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const on = Boolean(spot.image?.hero_reel);
  // The mobile crop starts from the mobile focal, else the desktop one.
  const focal = spot.image?.focal_mobile ?? spot.image?.focal ?? null;

  return (
    <div
      className="fixed inset-0 z-[1400] flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Mobiler Ausschnitt · ${spot.name}`}
    >
      <div
        className="w-full max-w-[420px] overflow-hidden rounded-xl border border-admin-border bg-admin-surface shadow-admin-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-admin-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-ui font-semibold text-admin-fg">{spot.name}</h2>
            <p className="text-caption text-admin-muted">Mobiler Bildausschnitt (Hochformat)</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-admin-fg2 hover:bg-admin-hover"
          >
            ✕
          </button>
        </div>

        <div className="px-5 py-4">
          <ImageFocalEditor
            url={spot.image?.url ?? ""}
            width={spot.image?.width}
            focal={focal}
            aspect="9 / 16"
            onSave={async (x, y) => {
              const updated = await setSpotImageFocalMobile(spot.id, { x, y });
              onSaved(updated);
            }}
          />

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-admin-border pt-4">
            <label className="flex cursor-pointer items-center gap-2 text-label font-medium text-admin-fg">
              <input
                type="checkbox"
                checked={on}
                onChange={(e) => void onToggleReel(e.target.checked)}
                className="h-4 w-4 accent-admin-primary"
              />
              In der Hero-Rotation
            </label>
            <Button variant="secondary" onClick={onClose}>
              Fertig
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
