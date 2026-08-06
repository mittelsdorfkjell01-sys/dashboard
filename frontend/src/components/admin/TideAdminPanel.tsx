import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  applyTideSuggestion,
  autoSelectTideAnchor,
  createTideOverride,
  getTideHistory,
  getTideProfile,
  getTideSuggestion,
  previewTides,
  recalculateTides,
  revokeTideOverride,
  rollbackTideProfile,
  setManualTideAnchor,
  updateTideProfile,
  type TideEvent,
  type TideProfile,
  type TideProfileRevision,
  type TideSuggestion,
} from "../../lib/api";
import { Field, fieldClass } from "../ui";
import { isoToSpotLocalInput, spotLocalInputToIso } from "../../lib/tideTime";

const QUALITY: Record<TideProfile["quality_status"], string> = {
  unavailable: "Nicht verfügbar",
  model_only: "Nur Modell",
  reviewed_anchor: "Anker geprüft",
  manual_calibrated: "Manuell kalibriert",
  gauge_calibrated: "Pegelkalibriert",
};

const STATUS: Record<TideProfile["calculation_status"], string> = {
  not_configured: "Nicht eingerichtet",
  queued: "Eingeplant",
  running: "Berechnung läuft",
  ready: "Bereit",
  failed: "Fehlgeschlagen",
  stale: "Veraltet",
};

function when(value: string, timezone?: string | null) {
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "short", timeStyle: "short", timeZone: timezone || "UTC",
  }).format(new Date(value));
}

export default function TideAdminPanel({ spotId, spotLat, spotLon }: {
  spotId: string; spotLat: number; spotLon: number;
}) {
  const [profile, setProfile] = useState<TideProfile | null>(null);
  const [history, setHistory] = useState<TideProfileRevision[]>([]);
  const [suggestion, setSuggestion] = useState<TideSuggestion | null>(null);
  const [preview, setPreview] = useState<TideEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [publicEnabled, setPublicEnabled] = useState(false);
  const [timezone, setTimezone] = useState("");
  const [globalOffset, setGlobalOffset] = useState(0);
  const [highOffset, setHighOffset] = useState(0);
  const [lowOffset, setLowOffset] = useState(0);
  const [uncertainty, setUncertainty] = useState("");
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [source, setSource] = useState("");
  const [anchorLat, setAnchorLat] = useState("");
  const [anchorLon, setAnchorLon] = useState("");
  const [eventId, setEventId] = useState("");
  const [manualTime, setManualTime] = useState("");
  const [scope, setScope] = useState<"single" | "high_profile" | "low_profile" | "calibration_input">("single");

  const seed = useCallback((data: TideProfile) => {
    setProfile(data);
    setEnabled(data.enabled);
    setPublicEnabled(data.public_enabled);
    setTimezone(data.timezone ?? "");
    setGlobalOffset(data.global_offset_minutes);
    setHighOffset(data.high_offset_minutes);
    setLowOffset(data.low_offset_minutes);
    setUncertainty(data.manual_uncertainty_minutes?.toString() ?? "");
    setNote(data.note ?? "");
    setReason(data.correction_reason ?? "");
    setSource(data.correction_source ?? "");
    const anchor = data.effective_anchor;
    setAnchorLat(anchor?.lat.toString() ?? "");
    setAnchorLon(anchor?.lon.toString() ?? "");
  }, []);

  const reload = useCallback(async () => {
    try {
      const [data, revisions, proposed] = await Promise.all([
        getTideProfile(spotId), getTideHistory(spotId), getTideSuggestion(spotId),
      ]);
      seed(data);
      setHistory(revisions);
      setSuggestion(proposed);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Gezeiten konnten nicht geladen werden.");
    }
  }, [seed, spotId]);

  useEffect(() => { void reload(); }, [reload]);
  useEffect(() => {
    const timer = setTimeout(() => {
      previewTides(spotId, {
        global_offset_minutes: globalOffset,
        high_offset_minutes: highOffset,
        low_offset_minutes: lowOffset,
      }).then((result) => setPreview(result.events)).catch(() => setPreview([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [globalOffset, highOffset, lowOffset, spotId]);

  const run = async (work: () => Promise<unknown>, success: string) => {
    setBusy(true); setError(null); setMessage(null);
    try {
      await work();
      setMessage(success);
      await reload();
    } catch (cause) {
      setError(cause instanceof ApiError || cause instanceof Error ? cause.message : "Aktion fehlgeschlagen.");
    } finally { setBusy(false); }
  };

  const selectedEvent = useMemo(
    () => profile?.events.find((event) => event.id === eventId),
    [eventId, profile],
  );

  if (!profile) {
    return <section className="rounded-lg border border-admin-border bg-admin-surface p-5"><p className="text-label text-admin-fg2">Gezeiten werden geladen.</p>{error && <p className="mt-2 text-label text-red-600">{error}</p>}</section>;
  }

  const unusual = Math.max(Math.abs(globalOffset), Math.abs(highOffset), Math.abs(lowOffset)) > profile.limits.soft_offset_minutes;
  return (
    <section id="f-tide" className="space-y-5 rounded-lg border border-admin-border bg-admin-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-ui font-semibold text-admin-fg">Gezeiten</h2>
          <p className="mt-1 text-caption text-admin-fg2">{profile.model_name} · Version {profile.model_version} · Profil {profile.version}</p>
        </div>
        <span className="rounded border border-admin-border px-2 py-1 text-caption font-medium text-admin-fg2">{STATUS[profile.calculation_status]}</span>
      </div>

      {error && <p role="alert" className="border-l-2 border-red-500 pl-3 text-label text-red-700">{error}</p>}
      {message && <p role="status" className="border-l-2 border-admin-success pl-3 text-label text-admin-success">{message}</p>}
      {profile.calculation_error && <p role="alert" className="border-l-2 border-red-500 pl-3 text-label text-red-700">{profile.calculation_error}</p>}
      {(profile.anchor_warnings ?? []).map((warning) => <p key={warning} className="border-l-2 border-amber-500 pl-3 text-label text-amber-800">{warning}</p>)}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex items-center gap-2 text-label text-admin-fg"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Aktiviert</label>
        <label className="flex items-center gap-2 text-label text-admin-fg"><input type="checkbox" checked={publicEnabled} onChange={(e) => setPublicEnabled(e.target.checked)} /> Öffentlich anzeigen</label>
        <div><p className="text-caption text-admin-fg2">Qualität</p><p className="text-label font-medium text-admin-fg">{QUALITY[profile.quality_status]}</p></div>
        <div><p className="text-caption text-admin-fg2">Letzte Berechnung</p><p className="text-label font-medium text-admin-fg">{profile.last_calculated_at ? when(profile.last_calculated_at, timezone) : "Noch keine"}</p></div>
      </div>

      <div className="border-t border-admin-border pt-4">
        <p className="text-label font-semibold text-admin-fg">Modellanker</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div><p className="text-caption text-admin-fg2">Spot</p><p className="text-label text-admin-fg">{spotLat.toFixed(5)}, {spotLon.toFixed(5)}</p></div>
          <div><p className="text-caption text-admin-fg2">Effektiver Anker</p><p className="text-label text-admin-fg">{profile.effective_anchor ? `${profile.effective_anchor.lat.toFixed(5)}, ${profile.effective_anchor.lon.toFixed(5)}` : "Nicht bestimmt"}</p></div>
          <div><p className="text-caption text-admin-fg2">Abstand</p><p className="text-label text-admin-fg">{profile.anchor_distance_m === null ? "—" : `${Math.round(profile.anchor_distance_m)} m`}</p></div>
          <div><p className="text-caption text-admin-fg2">Prüfung</p><p className="text-label text-admin-fg">{profile.anchor_status === "reviewed" ? "Geprüft" : profile.anchor_status === "invalid" ? "Ungültig" : "Prüfung erforderlich"}</p></div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={busy} onClick={() => void run(() => autoSelectTideAnchor(spotId), "Ankerbestimmung wurde eingeplant.")} className="rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50">Automatisch bestimmen</button>
          <button type="button" disabled={busy || profile.anchor_status !== "auto_selected" || profile.calculation_status !== "ready"} onClick={() => void run(() => updateTideProfile(spotId, { review_anchor: true }), "Modellanker geprüft.")} className="rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50">Anker prüfen</button>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_2fr_auto] sm:items-end">
          <Field label="Anker Breitengrad"><input className={fieldClass} type="number" step="0.00001" value={anchorLat} onChange={(e) => setAnchorLat(e.target.value)} /></Field>
          <Field label="Anker Längengrad"><input className={fieldClass} type="number" step="0.00001" value={anchorLon} onChange={(e) => setAnchorLon(e.target.value)} /></Field>
          <Field label="Begründung"><input className={fieldClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <button type="button" disabled={busy || !reason.trim()} onClick={() => void run(() => setManualTideAnchor(spotId, { lat: Number(anchorLat), lon: Number(anchorLon), reason }), "Manueller Anker gespeichert.")} className="rounded-md bg-admin-accent px-3 py-2 text-label font-medium text-white disabled:opacity-50">Anker setzen</button>
        </div>
      </div>

      <div className="border-t border-admin-border pt-4">
        <p className="text-label font-semibold text-admin-fg">Kalibrierung</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Allgemein (Min.)"><input className={fieldClass} type="number" value={globalOffset} onChange={(e) => setGlobalOffset(Number(e.target.value))} /></Field>
          <Field label="Hochwasser (Min.)"><input className={fieldClass} type="number" value={highOffset} onChange={(e) => setHighOffset(Number(e.target.value))} /></Field>
          <Field label="Niedrigwasser (Min.)"><input className={fieldClass} type="number" value={lowOffset} onChange={(e) => setLowOffset(Number(e.target.value))} /></Field>
          <Field label="Unsicherheit (Min.)"><input className={fieldClass} type="number" min="0" value={uncertainty} onChange={(e) => setUncertainty(e.target.value)} placeholder={profile.estimated_uncertainty_minutes?.toString() ?? "automatisch"} /></Field>
        </div>
        {unusual && <p className="mt-2 text-label text-amber-800">Ungewöhnlich große Korrektur. Prüfe Quelle und Begründung sorgfältig.</p>}
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Field label="Fachliche Notiz"><textarea className={fieldClass} rows={3} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <div className="grid gap-3">
            <Field label={`Begründung${Math.max(Math.abs(globalOffset), Math.abs(highOffset), Math.abs(lowOffset)) >= profile.limits.reason_required_minutes ? " (Pflicht)" : ""}`}><input className={fieldClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <Field label="Quelle"><input className={fieldClass} value={source} onChange={(e) => setSource(e.target.value)} /></Field>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" disabled={busy} onClick={() => void run(() => updateTideProfile(spotId, {
            enabled, public_enabled: publicEnabled, timezone: timezone || null,
            global_offset_minutes: globalOffset, high_offset_minutes: highOffset,
            low_offset_minutes: lowOffset,
            manual_uncertainty_minutes: uncertainty === "" ? null : Number(uncertainty),
            note: note || null, correction_reason: reason || null, correction_source: source || null,
          }), "Tideprofil gespeichert und Neuberechnung eingeplant.")} className="rounded-md bg-admin-accent px-3 py-2 text-label font-medium text-white disabled:opacity-50">Korrekturen speichern</button>
          <button type="button" disabled={busy || !enabled} onClick={() => void run(() => recalculateTides(spotId), "Neuberechnung wurde eingeplant.")} className="rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50">Neu berechnen</button>
          <button type="button" disabled={busy} onClick={() => { setGlobalOffset(0); setHighOffset(0); setLowOffset(0); }} className="rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50">Korrekturen zurücksetzen</button>
        </div>
      </div>

      <div className="border-t border-admin-border pt-4">
        <p className="text-label font-semibold text-admin-fg">Vorschau</p>
        {preview.length === 0 ? <p className="mt-2 text-label text-admin-fg2">Noch keine berechneten Ereignisse vorhanden.</p> : (
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {preview.slice(0, 6).map((event) => <div key={event.id} className="border-l-2 border-admin-border pl-3"><p className="text-caption uppercase text-admin-fg2">{event.event_type === "high" ? "Hochwasser" : "Niedrigwasser"}</p><p className="text-label font-medium text-admin-fg">{when(event.time, timezone)}</p>{event.raw_time && event.raw_time !== event.time && <p className="text-caption text-admin-fg2">Roh: {when(event.raw_time, timezone)}</p>}</div>)}
          </div>
        )}
      </div>

      <div className="border-t border-admin-border pt-4">
        <p className="text-label font-semibold text-admin-fg">Einzelereignis korrigieren</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Ereignis"><select className={fieldClass} value={eventId} onChange={(e) => { setEventId(e.target.value); const event = profile.events.find((item) => item.id === e.target.value); setManualTime(event && timezone ? isoToSpotLocalInput(event.time, timezone) : ""); }}><option value="">Auswählen</option>{profile.events.map((event) => <option key={event.id} value={event.id}>{event.event_type === "high" ? "Hoch" : "Niedrig"} · {when(event.time, timezone)}</option>)}</select></Field>
          <Field label={`Korrigierter Zeitpunkt${timezone ? ` (${timezone})` : ""}`}><input className={fieldClass} type="datetime-local" value={manualTime} onChange={(e) => setManualTime(e.target.value)} /></Field>
          <Field label="Wirkung"><select className={fieldClass} value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}><option value="single">Nur dieses Ereignis</option><option value="high_profile" disabled={selectedEvent?.event_type !== "high"}>Dauerhaft für Hochwasser</option><option value="low_profile" disabled={selectedEvent?.event_type !== "low"}>Dauerhaft für Niedrigwasser</option><option value="calibration_input">Für Profilvorschlag verwenden</option></select></Field>
          <Field label="Begründung"><input className={fieldClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        </div>
        <button type="button" disabled={busy || !eventId || !manualTime || !timezone || !reason.trim()} onClick={() => void run(() => createTideOverride(spotId, { event_id: eventId, manual_time: spotLocalInputToIso(manualTime, timezone), scope, reason, source: source || undefined }), "Ereigniskorrektur gespeichert.")} className="mt-3 rounded-md bg-admin-accent px-3 py-2 text-label font-medium text-white disabled:opacity-50">Korrektur speichern</button>
        {profile.overrides.filter((item) => item.active).length > 0 && <div className="mt-4 divide-y divide-admin-border border-y border-admin-border">{profile.overrides.filter((item) => item.active).map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-2"><div><p className="text-label text-admin-fg">{item.event_type === "high" ? "Hochwasser" : "Niedrigwasser"}: {item.difference_minutes > 0 ? "+" : ""}{item.difference_minutes} Min.</p><p className="text-caption text-admin-fg2">{item.reason} · {item.actor ?? "Unbekannt"}</p></div><button type="button" disabled={busy} onClick={() => void run(() => revokeTideOverride(spotId, item.id), "Überschreibung zurückgenommen.")} className="text-label font-medium text-red-700 hover:underline">Zurücknehmen</button></div>)}</div>}
      </div>

      {suggestion && suggestion.total > 0 && <div className="border-t border-admin-border pt-4"><p className="text-label font-semibold text-admin-fg">Profilvorschlag aus {suggestion.total} Angaben</p><p className="mt-2 text-label text-admin-fg2">Hochwasser: {suggestion.high ? `${suggestion.high.offset_minutes} Min. (Streuung ${suggestion.high.spread_minutes} Min.)` : "keine Daten"} · Niedrigwasser: {suggestion.low ? `${suggestion.low.offset_minutes} Min. (Streuung ${suggestion.low.spread_minutes} Min.)` : "keine Daten"}</p><button type="button" disabled={busy || !reason.trim()} onClick={() => void run(() => applyTideSuggestion(spotId, { apply_high: Boolean(suggestion.high), apply_low: Boolean(suggestion.low), reason }), "Profilvorschlag übernommen.")} className="mt-3 rounded-md border border-admin-border px-3 py-2 text-label font-medium text-admin-fg hover:bg-admin-hover disabled:opacity-50">Vorschlag bestätigen</button></div>}

      {history.length > 0 && <details className="border-t border-admin-border pt-4"><summary className="cursor-pointer text-label font-semibold text-admin-fg">Änderungshistorie</summary><div className="mt-3 divide-y divide-admin-border">{history.map((item) => <div key={item.version} className="flex flex-wrap items-center justify-between gap-3 py-2"><div><p className="text-label text-admin-fg">Version {item.version}: {item.reason}</p><p className="text-caption text-admin-fg2">{item.actor ?? "System"} · {when(item.created_at, timezone)}</p></div>{item.version !== profile.version && <button type="button" disabled={busy || !reason.trim()} onClick={() => void run(() => rollbackTideProfile(spotId, item.version, reason), `Version ${item.version} als neues Profil wiederhergestellt.`)} className="text-label font-medium text-admin-accent hover:underline">Wiederherstellen</button>}</div>)}</div></details>}
    </section>
  );
}
