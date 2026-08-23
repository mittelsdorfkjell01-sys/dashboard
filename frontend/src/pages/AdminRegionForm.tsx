// Edit a region like a spot: description, hero image (manual URL or upload),
// read-only regional wind availability, model default, and
// which spots belong to it (reassign in/out — fixes wrong auto-assignment).

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import {
  ApiError,
  assignSpotRegion,
  bulkAssignSpotRegion,
  bulkUnassignSpotRegion,
  deleteRegion,
  getAdminRegion,
  getAdminSpots,
  getAdminRegionsFlat,
  publishRegion,
  unpublishRegion,
  resolveMediaUrl,
  setRegionImageFocal,
  setRegionImageFocalMobile,
  setRegionImageManual,
  updateRegion,
  uploadRegionImage,
  type Region,
  type SpotSummary,
} from "../lib/api";
import { validateHeroFile } from "../components/ImageUpload";
import ImageFocalEditor from "../components/ImageFocalEditor";
import DuplicateWarningDialog from "../components/admin/DuplicateWarningDialog";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import { Input, Textarea } from "../components/ui";
import { Badge, Button } from "../components/admin/ui";
import AdminBackButton, {
  useAdminBackNavigation,
} from "../components/admin/AdminBackButton";
import UnsavedChangesDialog from "../components/admin/UnsavedChangesDialog";
import MediaPicker from "../components/admin/MediaPicker";
import GalleryManager from "../components/admin/GalleryManager";
import type { MediaRole } from "../lib/mediaPicker";
import {
  stableFormValue,
  useUnsavedChangesGuard,
} from "../lib/useUnsavedChangesGuard";
import {
  parseDuplicateConflict,
  type DuplicateConflict,
} from "../lib/duplicateConflicts";

const label = "text-label font-medium text-admin-fg";

export default function AdminRegionForm() {
  const { id } = useParams();
  const back = useAdminBackNavigation({
    fallbackTo: "/admin/regions",
    fallbackLabel: "Regionen",
  });
  const { blocker, markDirty, markClean, setDirty } = useUnsavedChangesGuard();

  const [region, setRegion] = useState<Region | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [allSpots, setAllSpots] = useState<SpotSummary[]>([]);

  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [description, setDescription] = useState("");
  const [imgUrl, setImgUrl] = useState("");
  const [imgCredit, setImgCredit] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState<MediaRole | null>(null);
  const [busy, setBusy] = useState(false);
  const [duplicateWarning, setDuplicateWarning] = useState<{
    conflict: DuplicateConflict;
    retry: () => void;
  } | null>(null);
  const [spotSearch, setSpotSearch] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [dragOverRight, setDragOverRight] = useState(false);
  // Bulk transfer: checkbox selections in each column + the target region for
  // moving spots *out* of this region.
  const [selIn, setSelIn] = useState<Set<string>>(new Set());
  const [selOut, setSelOut] = useState<Set<string>>(new Set());
  const [moveOutTarget, setMoveOutTarget] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [fieldsBaseline, setFieldsBaseline] = useState<string | null>(null);
  const [imageBaseline, setImageBaseline] = useState(stableFormValue({ url: "", credit: "" }));

  const fieldsValue = stableFormValue({ name, country, description });
  const imageValue = stableFormValue({ url: imgUrl, credit: imgCredit });

  useEffect(() => {
    setDirty("fields", fieldsBaseline !== null && fieldsValue !== fieldsBaseline);
  }, [fieldsBaseline, fieldsValue, setDirty]);
  useEffect(() => {
    setDirty("image", imageValue !== imageBaseline);
  }, [imageBaseline, imageValue, setDirty]);

  const flash = (m: string) => {
    setNotice(m);
    setTimeout(() => setNotice(null), 2500);
  };

  const loadRegion = async () => {
    if (!id) return;
    const r = await getAdminRegion(id);
    setRegion(r);
    setName(r.name);
    setCountry(r.country ?? "");
    setDescription(r.description ?? "");
    setFieldsBaseline(
      stableFormValue({ name: r.name, country: r.country ?? "", description: r.description ?? "" })
    );
    markClean();
  };

  const loadSpots = async () => {
    if (!id) return;
    // One fetch; `spots` (this region) and `otherSpots` are both derived below.
    const all = await getAdminSpots({ limit: 500 });
    setAllSpots(all.items);
  };

  useEffect(() => {
    getAdminRegionsFlat().then(setRegions).catch(() => {});
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

  const doSaveFields = async (allowDuplicate = false) => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      const patch: Parameters<typeof updateRegion>[1] = { expected_values: {} };
      const expected = patch.expected_values!;
      const add = (field: "name" | "country" | "description", value: unknown, oldValue: unknown) => {
        if (stableFormValue(value) === stableFormValue(oldValue)) return;
        (patch as Record<string, unknown>)[field] = value;
        expected[field] = oldValue;
      };
      add("name", name.trim(), region?.name);
      add("country", country.trim() || null, region?.country ?? null);
      add("description", description.trim() || null, region?.description ?? null);
      patch.allow_duplicate = allowDuplicate;
      const updated = Object.keys(expected).length
        ? await updateRegion(id, patch)
        : region!;
      setRegion(updated);
      setName(updated.name);
      setCountry(updated.country ?? "");
      setDescription(updated.description ?? "");
      setFieldsBaseline(
        stableFormValue({
          name: updated.name,
          country: updated.country ?? "",
          description: updated.description ?? "",
        })
      );
      markClean("fields");
      flash("Region gespeichert.");
    } catch (err) {
      const duplicate = parseDuplicateConflict(err);
      if (duplicate) {
        setDuplicateWarning({
          conflict: duplicate,
          retry: () => void doSaveFields(true),
        });
        return;
      }
      if (err instanceof ApiError && err.status === 409) setError(err.message);
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const saveFields = (e: FormEvent) => {
    e.preventDefault();
    void doSaveFields();
  };

  const saveImageUrl = async () => {
    if (!id || !imgUrl.trim()) return;
    // Attribution is mandatory for every image source and enforced server-side
    // since Sprint 1 — catch it here so the operator sees why, not a 422.
    if (!imgCredit.trim()) {
      setError("Für das Titelbild bitte einen Credit angeben.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await setRegionImageManual(id, {
        url: imgUrl.trim(),
        credit: imgCredit.trim(),
      });
      setRegion(r);
      setImgUrl("");
      setImgCredit("");
      setImageBaseline(stableFormValue({ url: "", credit: "" }));
      markClean("image");
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
      setImgCredit("");
      setImageBaseline(stableFormValue({ url: "", credit: "" }));
      markClean("image");
      flash("Titelbild hochgeladen.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const reassign = async (spotId: string, regionId: string, allowDuplicate = false) => {
    setBusy(true);
    setError(null);
    try {
      await assignSpotRegion(spotId, regionId, allowDuplicate);
      await loadSpots();
      flash("Spot verschoben.");
    } catch (err) {
      const duplicate = parseDuplicateConflict(err);
      if (duplicate) {
        setDuplicateWarning({
          conflict: duplicate,
          retry: () => void reassign(spotId, regionId, true),
        });
        return;
      }
      setError(err instanceof ApiError ? err.message : "Verschieben fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const bulkMove = async (ids: string[], regionId: string, allowDuplicate = false) => {
    if (ids.length === 0 || !regionId) return;
    setBusy(true);
    setError(null);
    try {
      const { moved } = await bulkAssignSpotRegion(ids, regionId, allowDuplicate);
      setSelIn(new Set());
      setSelOut(new Set());
      await loadSpots();
      flash(`${moved} Spot(s) verschoben.`);
    } catch (err) {
      const duplicate = parseDuplicateConflict(err);
      if (duplicate) {
        setDuplicateWarning({
          conflict: duplicate,
          retry: () => void bulkMove(ids, regionId, true),
        });
        return;
      }
      setError(err instanceof ApiError ? err.message : "Verschieben fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const unassign = async (spotId: string, allowDuplicate = false) => {
    setBusy(true);
    setError(null);
    try {
      await bulkUnassignSpotRegion([spotId], allowDuplicate);
      await loadSpots();
      flash("Spot ohne Region gesetzt.");
    } catch (err) {
      const duplicate = parseDuplicateConflict(err);
      if (duplicate) {
        setDuplicateWarning({
          conflict: duplicate,
          retry: () => void unassign(spotId, true),
        });
        return;
      }
      setError(err instanceof ApiError ? err.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (fn: (id: string) => Promise<Region>, msg: string) => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      setRegion(await fn(id));
      flash(msg);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = (set: Set<string>, sid: string) => {
    const next = new Set(set);
    if (next.has(sid)) next.delete(sid);
    else next.add(sid);
    return next;
  };

  const onDelete = async () => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await deleteRegion(id);
      markClean();
      back.goBack();
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
    <div className="w-full">
      <AdminBackButton onClick={back.goBack} label={back.label} />
      <h1 className="sr-only">Region bearbeiten — {region.name}</h1>

      {notice && (
        <div className="mt-4 rounded-md border border-admin-success-border bg-admin-success-bg px-3 py-2 text-label font-medium text-admin-success">
          {notice}
        </div>
      )}
      {error && (
        <div role="alert" className="mt-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger">
          {error}
        </div>
      )}

      <div className="mt-6 grid gap-6 sm:gap-8 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-5 sm:space-y-8">
      {/* Editorial */}
      <form onSubmit={saveFields} className="space-y-4 rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className={label}>Name</span>
            <Input
              className="mt-1.5"
              value={name}
              onChange={(e) => {
                markDirty("fields");
                setName(e.target.value);
              }}
            />
          </label>
          <label className="block">
            <span className={label}>Land</span>
            <Input
              className="mt-1.5"
              value={country}
              onChange={(e) => {
                markDirty("fields");
                setCountry(e.target.value);
              }}
              placeholder="z. B. DE"
            />
          </label>
        </div>
        <label className="block">
          <span className={label}>Beschreibung</span>
          <Textarea
            className="mt-1.5 min-h-[120px] resize-y"
            value={description}
            onChange={(e) => {
              markDirty("fields");
              setDescription(e.target.value);
            }}
            placeholder="Beschreibung der Region…"
          />
        </label>
        <div>
          <span className={label}>Windverfügbarkeit</span>
          <p className="mt-1.5 text-label font-medium text-admin-fg2">Unbekannt</p>
          <p className="mt-1 text-caption text-admin-muted">
            Regionale Windverfügbarkeit wird derzeit nicht manuell gepflegt.
          </p>
        </div>
        {error && (
          <div role="alert" className="rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label font-medium text-admin-danger">
            {error}
          </div>
        )}
        <Button type="submit" variant="primary" disabled={busy}>
          Speichern
        </Button>
      </form>

      {/* Hero image */}
      <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-ui font-semibold text-admin-fg">Titelbild</h2>
          <Button variant="primary" onClick={() => setPickerOpen("hero")}>
            Bild suchen
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap items-start gap-4">
          {region.image?.url ? (
            <img
              src={resolveMediaUrl(region.image.url)}
              alt=""
              className="h-24 w-40 rounded-lg object-cover"
            />
          ) : (
            <div className="grid h-24 w-40 place-items-center rounded-lg border border-admin-border bg-admin-bg text-caption text-admin-muted">
              Kein Bild
            </div>
          )}
          <div className="min-w-[240px] flex-1 space-y-2">
            <Input
              value={imgCredit}
              onChange={(e) => {
                markDirty("image");
                setImgCredit(e.target.value);
              }}
              placeholder="Credit / Urheber (für Upload Pflicht)"
            />
            <div className="flex gap-2">
              <Input
                value={imgUrl}
                onChange={(e) => {
                  markDirty("image");
                  setImgUrl(e.target.value);
                }}
                placeholder="Bild-URL setzen"
              />
              <Button
                variant="secondary"
                className="shrink-0"
                disabled={busy || !imgUrl.trim() || !imgCredit.trim()}
                onClick={saveImageUrl}
              >
                Setzen
              </Button>
            </div>
    <div className="pb-20 xl:pb-0">
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

        {/* Focal-point / crop editor — desktop 21:9, optional mobile 16:9. */}
        {region.image?.url && (
          <div className="mt-4">
            <div className="max-w-[560px]">
              <p className={label}>Ausschnitt Desktop (21:9)</p>
              <div className="mt-1.5">
                <ImageFocalEditor
                  url={region.image.url}
                  focal={region.image.focal}
                  aspect="21 / 9"
                  onSave={async (x, y) => {
                    if (!id) return;
                    const r = await setRegionImageFocal(id, x, y);
                    setRegion(r);
                  }}
                />
              </div>
            </div>
            <div className="mt-5 max-w-[320px]">
              <p className={label}>Ausschnitt Mobile (16:9)</p>
              <p className="mt-0.5 text-caption text-muted">
                Optional. Wenn leer, gilt der Desktop-Ausschnitt auch auf dem Handy.
              </p>
              <div className="mt-1.5">
                <ImageFocalEditor
                  url={region.image.url}
                  focal={region.image.focal_mobile ?? region.image.focal}
                  aspect="16 / 9"
                  onSave={async (x, y) => {
                    if (!id) return;
                    const r = await setRegionImageFocalMobile(id, { x, y });
                    setRegion(r);
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Gallery */}
      <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-ui font-semibold text-admin-fg">Galerie</h2>
          <Button variant="secondary" onClick={() => setPickerOpen("gallery")}>
            Bild hinzufügen
          </Button>
        </div>
        <div className="mt-3">
          {id && (
            <GalleryManager
              entityType="region"
              entityId={id}
              onHeroChanged={() => void loadRegion()}
            />
          )}
        </div>
      </section>

      {id && pickerOpen && (
        <MediaPicker
          entityType="region"
          entityId={id}
          open
          initialRole={pickerOpen}
          onClose={() => setPickerOpen(null)}
          onAdopted={() => {
            void loadRegion();
            flash("Bild übernommen.");
          }}
        />
      )}

      {/* Spots — drag from the right pool into this region */}
      <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
        <h2 className="text-ui font-semibold text-admin-fg">Spots zuordnen</h2>
        <p className="mt-1 text-label text-muted">
          Drag &amp; Drop in beide Richtungen: nach links = dieser Region
          zuordnen, nach rechts = Region entfernen (Spot wird region-los und
          erscheint oben in der Übersicht). Oder mehrere ankreuzen und gebündelt
          verschieben.
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
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData("text/plain", s.id)}
                    className="flex cursor-grab items-center gap-2 rounded-lg bg-band px-3 py-2 text-ui text-ink active:cursor-grabbing"
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

          {/* Right: pool of other spots — also a drop target: dropping a spot
              from this region here removes its region (region-less). */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOverRight(true);
            }}
            onDragLeave={() => setDragOverRight(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOverRight(false);
              const sid = e.dataTransfer.getData("text/plain");
              // Only spots currently in THIS region get unassigned here.
              if (sid && spots.some((s) => s.id === sid)) void unassign(sid);
            }}
            className={`rounded-2xl border p-3 transition-colors ${
              dragOverRight ? "border-red-400 bg-red-50/50" : "border-line bg-white"
            }`}
          >
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
                      <div className="text-caption text-muted">
                        {s.region_id ? regionName(s.region_id) : "ohne Region"}
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </section>

      {/* Danger zone: delete (only when empty). */}
      <section className="rounded-lg border border-admin-danger-border bg-admin-danger-bg p-4 sm:p-6">
        <h2 className="text-ui font-semibold text-admin-danger">Region löschen</h2>
        <p className="mt-1 text-label text-admin-fg2">
          {spots.length > 0
            ? `Diese Region hat ${spots.length} zugeordnete(n) Spot(s). Verschiebe sie zuerst — dann lässt sich die Region löschen.`
            : "Diese Region hat keine Spots und kann gelöscht werden. Das lässt sich nicht rückgängig machen."}
        </p>
        <Button
          variant="destructive"
          className="mt-4"
          disabled={busy || spots.length > 0}
          onClick={() => setDeleteOpen(true)}
        >
          Region löschen
        </Button>
      </section>
        </div>

        {/* Right: sticky action panel (status / go-live / preview / save).
            top clears the sticky app header so the rail stays visible while the
            long form scrolls. */}
        <aside className="xl:sticky xl:top-[var(--admin-header-h,64px)] xl:h-fit xl:self-start">
          <div className="rounded-lg border border-admin-border bg-admin-surface p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-ui font-semibold text-admin-fg">Status</h2>
              <Badge tone={region.status === "published" ? "success" : "warning"}>
                {region.status === "published" ? "Live" : "Entwurf"}
              </Badge>
            </div>
            <div className="mt-4 flex flex-col gap-2">
              {region.status === "published" ? (
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => setStatus(unpublishRegion, "Region offline genommen.")}
                >
                  Offline nehmen
                </Button>
              ) : (
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() => setStatus(publishRegion, "Region ist jetzt live.")}
                >
                  Go-Live
                </Button>
              )}
              <a
                href={`/region/${region.slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md border border-admin-border bg-admin-surface px-3 py-2 text-center text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
              >
                Öffentliche Vorschau ↗
              </a>
              <div className="my-1 h-px bg-admin-border" />
              <Button variant="primary" block disabled={busy} onClick={() => void doSaveFields()}>
                Änderungen speichern
              </Button>
            </div>
          </div>
        </aside>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        title="Region löschen"
        message={`„${region.name}" wird dauerhaft gelöscht. Das lässt sich nicht rückgängig machen.`}
        busy={busy}
        onConfirm={onDelete}
        onCancel={() => setDeleteOpen(false)}
      />

      <DuplicateWarningDialog
        conflict={duplicateWarning?.conflict ?? null}
        busy={busy}
        onClose={() => setDuplicateWarning(null)}
        onOverride={() => {
          const retry = duplicateWarning?.retry;
          setDuplicateWarning(null);
          retry?.();
        }}
      />
      <UnsavedChangesDialog blocker={blocker} />
      <div className="fixed inset-x-0 bottom-0 z-30 flex items-center gap-2 border-t border-admin-border bg-admin-surface px-4 py-3 xl:hidden sm:bg-admin-surface/95 sm:backdrop-blur">
        <AdminBackButton
          onClick={back.goBack}
          label={back.label}
          text="Abbrechen"
          showIcon={false}
          className="min-h-11 flex-1 justify-center"
        />
        <Button
          variant="primary"
          className="min-h-11 flex-1"
          disabled={busy}
          onClick={() => void doSaveFields(false)}
        >
          {busy ? "Speichern …" : "Speichern"}
        </Button>
      </div>
    </div>
  );
}
