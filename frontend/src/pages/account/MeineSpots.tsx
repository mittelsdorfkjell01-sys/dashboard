import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  addSubmission, findSimilarSpots, getSubmissionsState, loadMoreSubmissions, refreshSubmissions,
  SUBMISSIONS_EVENT, withdrawSubmission, AccountError,
  type CollectionState, type MySubmission, type SubmissionStatus,
} from "../../lib/account";
import { useRegions } from "../../lib/hooks";
import { SPORTS, sportLabel } from "../../lib/labels";
import { spotPath } from "../../lib/spotRoutes";
import { Button, Field, Input, Select } from "../../components/ui";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { PlusCircleIcon } from "../../lib/icons";
import { AccountPage } from "./AccountLayout";

const SubmissionMapPicker = lazy(() => import("../../components/SubmissionMapPicker"));
const STATUS: Record<SubmissionStatus, { label: string; cls: string }> = {
  pending: { label: "In Prüfung", cls: "bg-amber-100 text-amber-800" },
  merged: { label: "Als Entwurf übernommen", cls: "bg-success-bg text-success" },
  rejected: { label: "Abgelehnt", cls: "bg-danger-bg text-danger" },
  withdrawn: { label: "Zurückgezogen", cls: "bg-band text-muted" },
};

export default function MeineSpots() {
  const [state, setState] = useState<CollectionState<MySubmission>>(getSubmissionsState);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [sports, setSports] = useState<string[]>([]);
  const [similar, setSimilar] = useState<{ id: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [withdrawId, setWithdrawId] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const regions = useRegions(open);

  useEffect(() => {
    const refresh = () => setState(getSubmissionsState());
    window.addEventListener(SUBMISSIONS_EVENT, refresh);
    void refreshSubmissions();
    return () => window.removeEventListener(SUBMISSIONS_EVENT, refresh);
  }, []);

  useEffect(() => {
    if (!open || name.trim().length < 3) { setSimilar([]); return; }
    let active = true;
    const timer = window.setTimeout(() => {
      void findSimilarSpots(name.trim()).then((items) => { if (active) setSimilar(items); }).catch(() => { if (active) setSimilar([]); });
    }, 300);
    return () => { active = false; window.clearTimeout(timer); };
  }, [name, open]);

  const region = regions.data?.find((item) => item.id === regionId);
  const center: [number, number] = region?.center
    ? [region.center.lat, region.center.lon] : [54.4, 10.2];
  const latNumber = Number(lat);
  const lonNumber = Number(lon);
  const validPosition = lat.trim() !== "" && lon.trim() !== "" &&
    Number.isFinite(latNumber) && Number.isFinite(lonNumber) &&
    latNumber >= -90 && latNumber <= 90 && lonNumber >= -180 && lonNumber <= 180;
  const dirty = Boolean(name || regionId || lat || lon || sports.length);

  const resetForm = () => { setName(""); setRegionId(""); setLat(""); setLon(""); setSports([]); setError(null); setSimilar([]); };
  const closeForm = () => {
    if (busy) return;
    if (dirty) { setConfirmDiscard(true); return; }
    setOpen(false);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !regionId || !validPosition) return;
    setBusy(true); setError(null);
    try {
      await addSubmission({ name: name.trim(), regionId, lat: latNumber, lon: lonNumber, sports });
      resetForm(); setOpen(false);
    } catch (err) {
      setError(err instanceof AccountError ? err.message : "Einreichen fehlgeschlagen. Bitte versuche es erneut.");
    } finally { setBusy(false); }
  };

  const withdraw = async () => {
    if (!withdrawId) return;
    setActionError(null);
    try { await withdrawSubmission(withdrawId); setWithdrawId(null); }
    catch (err) { setActionError(err instanceof AccountError ? err.message : "Zurückziehen fehlgeschlagen."); setWithdrawId(null); }
  };

  return (
    <AccountPage title="Spots hinzufügen">
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-[60ch] text-ui text-muted">Hier siehst du deine Vorschläge und was daraus geworden ist. Erst nach der redaktionellen Veröffentlichung ist ein Spot öffentlich sichtbar.</p>
        <Button onClick={() => setOpen(true)}><PlusCircleIcon className="text-sz-18" /> Spot vorschlagen</Button>
      </div>

      <Modal open={open} onClose={closeForm} labelledBy="suggest-spot-title" cardClassName="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-[14px] bg-surface p-5 sm:p-6">
        <form onSubmit={submit} className="space-y-4">
          <h2 id="suggest-spot-title" className="text-sz-20 font-semibold text-ink">Spot vorschlagen</h2>
          <p className="text-ui text-muted">Nenne den Spot und markiere seine Lage. Wir prüfen und vervollständigen die Angaben vor einer Veröffentlichung.</p>
          <Field label="Name des Spots" required><Input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} placeholder="z. B. Wulfener Hals" required /></Field>
          {similar.length > 0 && <div className="rounded-lg bg-band p-3 text-label"><p className="font-semibold text-ink">Vielleicht schon vorhanden:</p><ul className="mt-1 space-y-1">{similar.map((item) => <li key={item.id}><Link className="text-ink underline" to={spotPath(item)}>{item.name}</Link></li>)}</ul></div>}
          <Field label="Region" required>
            <Select value={regionId} onChange={(e) => setRegionId(e.target.value)} required>
              <option value="">Region wählen</option>
              {(regions.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}{item.country ? `, ${item.country}` : ""}</option>)}
            </Select>
          </Field>
          {regions.error && <p role="alert" className="text-label text-danger">Regionen konnten nicht geladen werden. <button type="button" className="underline" onClick={regions.reload}>Erneut versuchen</button></p>}
          <div>
            <p className="mb-2 text-label font-medium text-ink">Position auf der Karte auswählen</p>
            <Suspense fallback={<div role="status" className="grid h-56 place-items-center bg-band text-ui text-muted">Karte lädt …</div>}>
              <SubmissionMapPicker center={center} position={validPosition ? [latNumber, lonNumber] : null} onPick={(a, b) => { setLat(String(a)); setLon(String(b)); }} />
            </Suspense>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Field label="Breitengrad" required><Input type="number" inputMode="decimal" step="any" min={-90} max={90} value={lat} onChange={(e) => setLat(e.target.value)} required /></Field>
              <Field label="Längengrad" required><Input type="number" inputMode="decimal" step="any" min={-180} max={180} value={lon} onChange={(e) => setLon(e.target.value)} required /></Field>
            </div>
          </div>
          <fieldset>
            <legend className="text-label font-medium text-ink">Sportarten (optional)</legend>
            <div className="mt-2 flex flex-wrap gap-2">{SPORTS.map((sport) => <label key={sport} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line px-3 text-label text-ink"><input type="checkbox" checked={sports.includes(sport)} onChange={() => setSports((current) => current.includes(sport) ? current.filter((item) => item !== sport) : [...current, sport])} />{sportLabel(sport)}</label>)}</div>
          </fieldset>
          {error && <p role="alert" className="text-label font-medium text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={closeForm} disabled={busy}>Abbrechen</Button>
            <Button type="submit" disabled={busy || !name.trim() || !regionId || !validPosition}>{busy ? "Sende …" : "Vorschlag einreichen"}</Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={confirmDiscard} title="Eingaben verwerfen?" message="Dein noch nicht eingereichter Vorschlag geht verloren." confirmText="Verwerfen" onCancel={() => setConfirmDiscard(false)} onConfirm={() => { resetForm(); setConfirmDiscard(false); setOpen(false); }} />

      {state.status === "loading" && state.items.length === 0 && <p role="status" className="py-8 text-center text-ui text-muted">Vorschläge werden geladen …</p>}
      {state.status === "error" && <div role="alert" className="rounded-lg border border-line p-5 text-ui"><p>{state.error}</p><button type="button" onClick={() => void refreshSubmissions()} className="mt-3 min-h-11 font-semibold underline">Erneut versuchen</button></div>}
      {actionError && <p role="alert" className="text-ui text-danger">{actionError}</p>}
      {state.status === "ready" && state.items.length === 0 && <p className="rounded-[14px] border border-dashed border-line px-6 py-10 text-center text-ui text-muted">Du hast noch keine Spots vorgeschlagen.</p>}
      {state.items.length > 0 && <ul className="space-y-3">{state.items.map((sub) => {
        const status = STATUS[sub.status] ?? { label: "Status unbekannt", cls: "bg-band text-muted" };
        return <li key={sub.id} className="rounded-[14px] border border-line bg-surface p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h2 className="text-body font-semibold text-ink">{sub.name}</h2><p className="mt-1 text-caption text-muted">Eingereicht am {new Date(sub.createdAt).toLocaleDateString("de-DE")}</p></div><span className={`rounded-full px-3 py-1 text-caption font-semibold ${status.cls}`}>{status.label}</span></div>
          {sub.status === "merged" && !sub.publishedSpotId && <p className="mt-3 text-label text-muted">Der Spot ist als Entwurf übernommen. Die Veröffentlichung steht noch aus.</p>}
          {sub.status === "rejected" && <p className="mt-3 text-label text-muted">{sub.reviewNote ? `Rückmeldung: ${sub.reviewNote}` : "Der Vorschlag wurde nach Prüfung nicht übernommen."}</p>}
          {sub.publishedSpotId && <Link to={spotPath({ id: sub.publishedSpotId, name: sub.name })} className="mt-3 inline-flex min-h-11 items-center text-label font-semibold text-ink underline">Veröffentlichten Spot ansehen</Link>}
          {sub.status === "pending" && <button type="button" onClick={() => setWithdrawId(sub.id)} className="mt-3 min-h-11 text-label font-semibold text-ink underline">Vorschlag zurückziehen</button>}
        </li>;
      })}</ul>}
      {state.hasMore && <button type="button" disabled={state.status === "loading"} onClick={() => void loadMoreSubmissions()} className="min-h-11 rounded-lg border border-line px-4 text-ui font-semibold text-ink">{state.status === "loading" ? "Lädt …" : "Weitere Vorschläge laden"}</button>}
      <ConfirmDialog open={withdrawId !== null} title="Vorschlag zurückziehen?" message="Der Vorschlag wird nicht mehr geprüft." confirmText="Zurückziehen" onCancel={() => setWithdrawId(null)} onConfirm={() => void withdraw()} />
    </div>
    </AccountPage>
  );
}
