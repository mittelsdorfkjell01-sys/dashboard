// Edit a region like a spot: description, hero image (manual URL or upload),
// Windmonate (season JSON, auto-generated but correctable), model default, and
// which spots belong to it (reassign in/out — fixes wrong auto-assignment).

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  assignSpotRegion,
  bulkAssignSpotRegion,
  deleteRegion,
  getAdminSpots,
  getRegion,
  getRegions,
  resolveMediaUrl,
  setRegionImageFocal,
  setRegionImageManual,
  updateRegion,
  uploadRegionImage,
  type Region,
  type SpotSummary,
} from "../lib/api";
import { validateHeroFile } from "../components/ImageUpload";
import ImageFocalEditor from "../components/ImageFocalEditor";
import ConflictDialog from "../components/admin/ConflictDialog";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import { Button, Input, Textarea } from "../components/ui";

const label = "text-label font-medium text-ink";
const MONTHS_SHORT = [
  "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
  "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
];

export default function AdminRegionForm() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [region, setRegion] = useState<Region | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [allSpots, setAllSpots] = useState<SpotSummary[]>([]);

  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [description, setDescription] = useState("");
  const [bestMonths, setBestMonths] = useState<number[]>([]);
  const [imgUrl, setImgUrl] = useState("");
  const [imgCredit, setImgCredit] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflictOpen, setConflictOpen] = useState(false);
  const [spotSearch, setSpotSearch] = useState("");
  const [dragOver, setDragOver] = useState(false);
  // Bulk transfer: checkbox selections in each column + the target region for
  // moving spots *out* of this region.
  const [selIn, setSelIn] = useState<Set<string>>(new Set());
  const [selOut, setSelOut] = useState<Set<string>>(new Set());
  const [moveOutTarget, setMoveOutTarget] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);

  const flash = (m: string) => {
    setNotice(m);
    setTimeout(() => setNotice(null), 2500);
  };

  const loadRegion = async () => {
    if (!id) return;
    const r = await getRegion(id);
    setRegion(r);
    setName(r.name);
    setCountry(r.country ?? "");
    setDescription(r.description ?? "");
    setBestMonths(
      Array.isArray(r.season?.best_months) ? (r.season!.best_months as number[]) : []
    );
  };

  const loadSpots = async () => {
    if (!id) return;
    // One fetch; `spots` (this region) and `otherSpots` are both derived below.
    const all = await getAdminSpots({ limit: 500 });
    setAllSpots(all.items);
  };

  useEffect(() => {
    getRegions().then(setRegions).catch(() => {});
    loadRegion().catch((e) =>
      setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.")
    );
    loadSpots().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const spots = useMemo(
    () => allSpots.filter((s) => s.region_id === id),
    [allSpots, id]
  );
  const otherSpots = useMemo(
    () => allSpots.filter((s) => s.region_id !== id),
    [allSpots, id]
  );
  const regionName = (rid: string) =>
    regions.find((r) => r.id === rid)?.name ?? "—";

  // `force` skips the optimistic-locking token (conflict dialog → overwrite).
  const doSaveFields = async (force: boolean) => {
    if (!id) return;
    setBusy(true);
    setError(null);
    // Preserve any other season keys; only the best-months selection is edited.
    const season = {
      ...(region?.season ?? {}),
      best_months: [...bestMonths].sort((a, b) => a - b),
    };
    try {
      const updated = await updateRegion(id, {
        name: name.trim() || undefined,
        country: country.trim() ? country.trim() : null,
        description: description.trim() ? description.trim() : null,
        season,
        expected_updated_at: force ? undefined : region?.updated_at,
      });
      setRegion(updated);
      flash("Region gespeichert.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflictOpen(true);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const saveFields = (e: FormEvent) => {
    e.preventDefault();
    void doSaveFields(false);
  };

  const saveImageUrl = async () => {
    if (!id || !imgUrl.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await setRegionImageManual(id, {
        url: imgUrl.trim(),
        credit: imgCredit.trim(),
      });
      setRegion(r);
      setImgUrl("");
      flash("Titelbild gesetzt.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bild setzen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const uploadImage = async (file: File | null) => {
    if (!id || !file) return;
    if (!imgCredit.trim()) {
      setError("Für den Upload bitte einen Credit angeben.");
      return;
    }
    const res = await validateHeroFile(file);
    if (!res.ok) {
      setError(res.reason ?? "Bild erfüllt die Vorgaben nicht.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await uploadRegionImage(id, file, imgCredit.trim());
      setRegion(r);
      flash("Titelbild hochgeladen.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const reassign = async (spotId: string, regionId: string) => {
    setBusy(true);
    setError(null);
    try {
      await assignSpotRegion(spotId, regionId);
      await loadSpots();
      flash("Spot verschoben.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verschieben fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const bulkMove = async (ids: string[], regionId: string) => {
    if (ids.length === 0 || !regionId) return;
    setBusy(true);
    setError(null);
    try {
      const { moved } = await bulkAssignSpotRegion(ids, regionId);
      setSelIn(new Set());
      setSelOut(new Set());
      await loadSpots();
      flash(`${moved} Spot(s) verschoben.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verschieben fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = (set: Set<string>, sid: string) => {
    const next = new Set(set);
    next.has(sid) ? next.delete(sid) : next.add(sid);
    return next;
  };

  const onDelete = async () => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await deleteRegion(id);
      navigate("/admin/regions");
    } catch (err) {
      setDeleteOpen(false);
      setError(err instanceof ApiError ? err.message : "Löschen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  if (!region) {
    return <div className="mx-auto max-w-[820px] text-ui text-muted">Lädt…</div>;
  }

  return (
    <div className="mx-auto max-w-[820px]">
      <button
        type="button"
        onClick={() => navigate("/admin/regions")}
        className="text-label text-muted hover:text-teal"
      >
        ← Regionen
      </button>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold text-ink">
          Region bearbeiten — {region.name}
        </h1>
        <a
          href={`/region/${region.slug}`}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-teal/30 px-3 py-1.5 text-label font-medium text-teal hover:bg-teal/5"
        >
          Vorschau ansehen ↗
        </a>
      </div>

      {notice && (
        <div className="mt-4 rounded-lg bg-green/10 px-3 py-2 text-label font-medium text-green">
          {notice}
        </div>
      )}
      {error && (
        <div role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700">
          {error}
        </div>
      )}

      {/* Editorial */}
      <form onSubmit={saveFields} className="mt-6 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className={label}>Name</span>
            <Input className="mt-1.5" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block">
            <span className={label}>Land</span>
            <Input
              className="mt-1.5"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="z. B. DE"
            />
          </label>
        </div>
        <label className="block">
          <span className={label}>Beschreibung</span>
          <Textarea
            className="mt-1.5 min-h-[120px] resize-y"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Beschreibung der Region…"
          />
        </label>
        <div className="block">
          <span className={label}>Beste Monate (Windmonate)</span>
          <span className="ml-2 text-caption text-muted">
            Monate anklicken, in denen die Region am besten läuft
          </span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {MONTHS_SHORT.map((m, i) => {
              const month = i + 1;
              const on = bestMonths.includes(month);
              return (
                <button
                  key={month}
                  type="button"
                  onClick={() =>
                    setBestMonths((prev) =>
                      prev.includes(month)
                        ? prev.filter((x) => x !== month)
                        : [...prev, month]
                    )
                  }
                  className={`rounded-lg px-3 py-1.5 text-label font-medium ${
                    on
                      ? "bg-teal text-white"
                      : "border border-line bg-white text-ink hover:bg-teal/5"
                  }`}
                >
                  {m}
                </button>
              );
            })}
          </div>
        </div>
        {error && (
          <div role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-label font-medium text-red-700">
            {error}
          </div>
        )}
        <Button type="submit" disabled={busy}>
          Speichern
        </Button>
      </form>

      {/* Hero image */}
      <section className="mt-10">
        <h2 className="text-base font-semibold text-ink">Titelbild</h2>
        <div className="mt-3 flex flex-wrap items-start gap-4">
          {region.image?.url ? (
            <img
              src={resolveMediaUrl(region.image.url)}
              alt=""
              className="h-24 w-40 rounded-lg object-cover"
            />
          ) : (
            <div className="grid h-24 w-40 place-items-center rounded-lg bg-band text-caption text-muted">
              Kein Bild
            </div>
          )}
          <div className="min-w-[240px] flex-1 space-y-2">
            <Input
              value={imgCredit}
              onChange={(e) => setImgCredit(e.target.value)}
              placeholder="Credit / Urheber (für Upload Pflicht)"
            />
            <div className="flex gap-2">
              <Input
                value={imgUrl}
                onChange={(e) => setImgUrl(e.target.value)}
                placeholder="Bild-URL setzen"
              />
              <button
                type="button"
                disabled={busy || !imgUrl.trim()}
                onClick={saveImageUrl}
                className="shrink-0 rounded-lg border border-teal/30 px-3 py-2 text-label font-medium text-teal hover:bg-teal/5 disabled:opacity-50"
              >
                Setzen
              </button>
            </div>
            <div>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => uploadImage(e.target.files?.[0] ?? null)}
                className="text-label text-ink"
              />
              <p className="mt-1 text-caption text-muted">
                Upload: min. 3840×2000 px, Querformat, JPG/PNG.
              </p>
            </div>
          </div>
        </div>

        {/* Focal-point / crop editor */}
        {region.image?.url && (
          <div className="mt-4 max-w-[560px]">
            <p className={label}>Ausschnitt wählen</p>
            <div className="mt-1.5">
              <ImageFocalEditor
                url={region.image.url}
                focal={region.image.focal}
                onSave={async (x, y) => {
                  if (!id) return;
                  const r = await setRegionImageFocal(id, x, y);
                  setRegion(r);
                }}
              />
            </div>
          </div>
        )}
      </section>

      {/* Spots — drag from the right pool into this region */}
      <section className="mt-10">
        <h2 className="text-base font-semibold text-ink">Spots zuordnen</h2>
        <p className="mt-1 text-label text-muted">
          Einzeln per Drag &amp; Drop aus „Andere Spots" in „Diese Region", oder
          mehrere ankreuzen und gebündelt verschieben — in beide Richtungen.
        </p>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {/* Left: spots in this region (drop zone) */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const sid = e.dataTransfer.getData("text/plain");
              if (sid && id) void reassign(sid, id);
            }}
            className={`rounded-2xl border p-3 ${
              dragOver ? "border-teal bg-teal/5" : "border-line bg-white"
            }`}
          >
            <p className="px-1 text-label font-semibold text-ink">
              Diese Region ({spots.length})
            </p>
            <div className="mt-2 space-y-2">
              {spots.length === 0 ? (
                <p className="px-1 py-6 text-center text-label text-muted">
                  Spot hierher ziehen …
                </p>
              ) : (
                spots.map((s) => (
                  <label
                    key={s.id}
                    className="flex cursor-pointer items-center gap-2 rounded-lg bg-band px-3 py-2 text-ui text-ink"
                  >
                    <input
                      type="checkbox"
                      checked={selIn.has(s.id)}
                      onChange={() => setSelIn((prev) => toggle(prev, s.id))}
                    />
                    {s.name}
                  </label>
                ))
              )}
            </div>
            {selIn.size > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                <span className="text-caption text-muted">{selIn.size} gewählt →</span>
                <select
                  value={moveOutTarget}
                  onChange={(e) => setMoveOutTarget(e.target.value)}
                  className="rounded-lg border border-line bg-white px-2 py-1 text-label text-ink"
                >
                  <option value="">— Zielregion —</option>
                  {regions
                    .filter((r) => r.id !== id)
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                </select>
                <button
                  type="button"
                  disabled={busy || !moveOutTarget}
                  onClick={() => bulkMove([...selIn], moveOutTarget)}
                  className="rounded-lg border border-teal/30 px-3 py-1 text-label font-medium text-teal hover:bg-teal/5 disabled:opacity-50"
                >
                  Verschieben
                </button>
              </div>
            )}
          </div>

          {/* Right: pool of all other spots (searchable, selectable, draggable) */}
          <div className="rounded-2xl border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2 px-1">
              <p className="text-label font-semibold text-ink">Andere Spots</p>
              {selOut.size > 0 && (
                <button
                  type="button"
                  disabled={busy || !id}
                  onClick={() => id && bulkMove([...selOut], id)}
                  className="rounded-lg border border-teal/30 px-3 py-1 text-label font-medium text-teal hover:bg-teal/5 disabled:opacity-50"
                >
                  {selOut.size} in diese Region holen
                </button>
              )}
            </div>
            <Input
              className="mt-2"
              value={spotSearch}
              onChange={(e) => setSpotSearch(e.target.value)}
              placeholder="Suchen …"
            />
            <div className="mt-2 max-h-[360px] space-y-2 overflow-auto">
              {otherSpots
                .filter((s) =>
                  s.name.toLowerCase().includes(spotSearch.trim().toLowerCase())
                )
                .map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center gap-2 rounded-lg border border-line px-3 py-2"
                  >
                    <input
                      type="checkbox"
                      checked={selOut.has(s.id)}
                      onChange={() => setSelOut((prev) => toggle(prev, s.id))}
                    />
                    <div
                      draggable
                      onDragStart={(e) => e.dataTransfer.setData("text/plain", s.id)}
                      className="min-w-0 flex-1 cursor-grab active:cursor-grabbing"
                    >
                      <div className="text-ui text-ink">{s.name}</div>
                      <div className="text-caption text-muted">{regionName(s.region_id)}</div>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </section>

      {/* Danger zone: delete (only when empty). */}
      <section className="mt-10 rounded-2xl border border-red-200 bg-red-50/40 p-4">
        <h2 className="text-body font-semibold text-ink">Region löschen</h2>
        <p className="mt-1 text-label text-muted">
          {spots.length > 0
            ? `Diese Region hat ${spots.length} zugeordnete(n) Spot(s). Verschiebe sie zuerst — dann lässt sich die Region löschen.`
            : "Diese Region hat keine Spots und kann gelöscht werden. Das lässt sich nicht rückgängig machen."}
        </p>
        <button
          type="button"
          disabled={busy || spots.length > 0}
          onClick={() => setDeleteOpen(true)}
          className="mt-3 rounded-lg border border-red-300 px-3 py-1.5 text-label font-medium text-red-600 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Region löschen
        </button>
      </section>

      <ConfirmDialog
        open={deleteOpen}
        title="Region löschen"
        message={`„${region.name}" wird dauerhaft gelöscht. Das lässt sich nicht rückgängig machen.`}
        busy={busy}
        onConfirm={onDelete}
        onCancel={() => setDeleteOpen(false)}
      />

      <ConflictDialog
        open={conflictOpen}
        busy={busy}
        onReload={() => {
          setConflictOpen(false);
          loadRegion().catch((e) =>
            setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.")
          );
        }}
        onOverwrite={() => {
          setConflictOpen(false);
          void doSaveFields(true);
        }}
        onClose={() => setConflictOpen(false)}
      />
    </div>
  );
}
