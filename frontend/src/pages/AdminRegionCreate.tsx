import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import SpotMapEditor, { type MapView } from "../components/SpotMapEditor";
import AdminBackButton, { useAdminBackNavigation } from "../components/admin/AdminBackButton";
import DuplicateWarningDialog from "../components/admin/DuplicateWarningDialog";
import UnsavedChangesDialog from "../components/admin/UnsavedChangesDialog";
import { Button } from "../components/admin/ui";
import { Input, Textarea } from "../components/ui";
import {
  ApiError,
  createRegion,
  setRegionImageManual,
  updateRegion,
} from "../lib/api";
import { parseDuplicateConflict, type DuplicateConflict } from "../lib/duplicateConflicts";
import { useUnsavedChangesGuard } from "../lib/useUnsavedChangesGuard";

const MODELS = [
  { value: "", label: "Automatisch" },
  { value: "icon_d2", label: "ICON-D2" },
  { value: "icon_eu", label: "ICON-EU" },
  { value: "gfs", label: "GFS" },
];
const fieldClass = "mt-1.5 w-full";

const numberValue = (value: string) => Number(value.replace(",", "."));

export default function AdminRegionCreate() {
  const navigate = useNavigate();
  const back = useAdminBackNavigation({ fallbackTo: "/admin/regions", fallbackLabel: "Regionen" });
  const { blocker, markDirty, markClean } = useUnsavedChangesGuard();
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [description, setDescription] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [model, setModel] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [imageCredit, setImageCredit] = useState("");
  const [mapView, setMapView] = useState<MapView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<DuplicateConflict | null>(null);

  const change = <T,>(setter: (value: T) => void, value: T) => {
    markDirty("region-create");
    setter(value);
  };

  const save = async (allowDuplicate = false) => {
    const hasLat = lat.trim() !== "";
    const hasLon = lon.trim() !== "";
    if (!name.trim()) return setError("Bitte einen Namen eingeben.");
    if (hasLat !== hasLon) return setError("Breiten- und Längengrad bitte gemeinsam angeben.");
    const latitude = hasLat ? numberValue(lat) : undefined;
    const longitude = hasLon ? numberValue(lon) : undefined;
    if ((latitude != null && (!Number.isFinite(latitude) || latitude < -90 || latitude > 90)) ||
        (longitude != null && (!Number.isFinite(longitude) || longitude < -180 || longitude > 180))) {
      return setError("Bitte gültige Koordinaten eingeben.");
    }
    if (imageUrl.trim() && !imageCredit.trim()) return setError("Für das Titelbild bitte einen Credit angeben.");

    setBusy(true);
    setError(null);
    try {
      const created = await createRegion({
        name: name.trim(),
        country: country.trim().toUpperCase() || undefined,
        lat: latitude,
        lon: longitude,
        defaults: model ? { model_pref: model } : undefined,
        allow_duplicate: allowDuplicate,
      });
      if (description.trim()) {
        await updateRegion(created.id, {
          description: description.trim() || null,
        });
      }
      if (imageUrl.trim()) {
        await setRegionImageManual(created.id, {
          url: imageUrl.trim(),
          credit: imageCredit.trim(),
        });
      }
      markClean();
      navigate(`/admin/region/${created.id}/edit`, { replace: true });
    } catch (err) {
      const conflict = parseDuplicateConflict(err);
      if (conflict) setDuplicate(conflict);
      else setError(err instanceof ApiError ? err.message : "Region konnte nicht angelegt werden.");
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void save();
  };

  return (
    <div className="w-full pb-20 xl:pb-0">
      <AdminBackButton onClick={back.goBack} label={back.label} />
      <h1 className="mt-5 text-sz-24 font-semibold text-admin-fg">Region anlegen</h1>
      <p className="mt-1 text-label text-admin-muted">Stammdaten, Mittelpunkt und Titelbild in einem Schritt erfassen.</p>

      <form id="admin-region-create" onSubmit={submit} className="mt-6 grid gap-5 sm:gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-6">
          <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
            <h2 className="text-ui font-semibold text-admin-fg">Stammdaten</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-label font-medium text-admin-fg">Name
                <Input className={fieldClass} value={name} onChange={(e) => change(setName, e.target.value)} placeholder="z. B. Nordsee" autoFocus />
              </label>
              <label className="text-label font-medium text-admin-fg">Landcode
                <Input className={fieldClass} value={country} maxLength={2} onChange={(e) => change(setCountry, e.target.value.toUpperCase())} placeholder="z. B. DE" />
              </label>
            </div>
            <label className="mt-4 block text-label font-medium text-admin-fg">Beschreibung
              <Textarea className={`${fieldClass} min-h-[120px] resize-y`} value={description} onChange={(e) => change(setDescription, e.target.value)} placeholder="Charakter, Saison und Besonderheiten der Region …" />
            </label>
            <label className="mt-4 block text-label font-medium text-admin-fg">Standard-Wettermodell
              <select className={`${fieldClass} rounded-md border border-admin-border bg-admin-surface px-3 py-2 text-ui text-admin-fg`} value={model} onChange={(e) => change(setModel, e.target.value)}>
                {MODELS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </section>

          <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
            <h2 className="text-ui font-semibold text-admin-fg">Mittelpunkt und Karte</h2>
            <p className="mt-1 text-caption text-admin-muted">Koordinaten eingeben oder den Pin direkt auf der Karte setzen und verschieben.</p>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <label className="text-label font-medium text-admin-fg">Breitengrad (lat)
                <Input className={fieldClass} inputMode="decimal" value={lat} onChange={(e) => change(setLat, e.target.value)} placeholder="54.47" />
              </label>
              <label className="text-label font-medium text-admin-fg">Längengrad (lon)
                <Input className={fieldClass} inputMode="decimal" value={lon} onChange={(e) => change(setLon, e.target.value)} placeholder="11.14" />
              </label>
            </div>
            <div className="mt-4">
              <SpotMapEditor
                lat={lat.trim() && Number.isFinite(numberValue(lat)) ? numberValue(lat) : null}
                lon={lon.trim() && Number.isFinite(numberValue(lon)) ? numberValue(lon) : null}
                mapView={mapView}
                onPositionChange={(nextLat, nextLon) => {
                  markDirty("region-create");
                  setLat(String(nextLat));
                  setLon(String(nextLon));
                }}
                onViewChange={(view) => setMapView(view)}
              />
            </div>
          </section>

          <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
            <h2 className="text-ui font-semibold text-admin-fg">Windverfügbarkeit</h2>
            <p className="mt-2 text-label font-medium text-admin-fg2">Unbekannt</p>
            <p className="mt-1 text-caption text-admin-muted">Regionale Windverfügbarkeit wird derzeit nicht manuell gepflegt.</p>
          </section>

          <section className="rounded-lg border border-admin-border bg-admin-surface p-4 sm:p-6">
            <h2 className="text-ui font-semibold text-admin-fg">Titelbild</h2>
            <p className="mt-1 text-caption text-admin-muted">Optional per URL; weitere Bildquellen und Uploads stehen nach dem Anlegen im Editor bereit.</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-label font-medium text-admin-fg">Bild-URL
                <Input className={fieldClass} value={imageUrl} onChange={(e) => change(setImageUrl, e.target.value)} placeholder="https://…" />
              </label>
              <label className="text-label font-medium text-admin-fg">Credit / Urheber
                <Input className={fieldClass} value={imageCredit} onChange={(e) => change(setImageCredit, e.target.value)} placeholder="Fotograf:in / Quelle" />
              </label>
            </div>
          </section>
        </div>

        <aside className="xl:sticky xl:top-[var(--admin-header-h,64px)] xl:h-fit">
          <div className="rounded-lg border border-admin-border bg-admin-surface p-4">
            <p className="font-semibold text-admin-fg">{name.trim() || "Neue Region"}</p>
            <p className="mt-1 text-caption text-admin-muted">Wird zunächst als Entwurf angelegt.</p>
            {error && <p role="alert" className="mt-4 text-label font-medium text-admin-danger">{error}</p>}
            <Button type="submit" variant="primary" block disabled={busy || !name.trim()} className="mt-4 min-h-11">{busy ? "Region wird angelegt …" : "Region anlegen"}</Button>
            <AdminBackButton onClick={back.goBack} label={back.label} text="Abbrechen" showIcon={false} className="mt-3 justify-center" />
          </div>
        </aside>
      </form>

      <div className="fixed inset-x-0 bottom-0 z-30 flex gap-2 border-t border-admin-border bg-admin-surface px-4 py-3 xl:hidden sm:bg-admin-surface/95 sm:backdrop-blur">
        <AdminBackButton onClick={back.goBack} label={back.label} text="Abbrechen" showIcon={false} className="min-h-11 flex-1 justify-center" />
        <Button type="submit" form="admin-region-create" variant="primary" disabled={busy || !name.trim()} className="min-h-11 flex-1">{busy ? "Speichern …" : "Region anlegen"}</Button>
      </div>

      <DuplicateWarningDialog conflict={duplicate} busy={busy} onClose={() => setDuplicate(null)} onOverride={() => { setDuplicate(null); void save(true); }} />
      <UnsavedChangesDialog blocker={blocker} />
    </div>
  );
}
