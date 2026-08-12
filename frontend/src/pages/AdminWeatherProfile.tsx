import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getAdminForecastJob, getAdminWeatherDiagnostics, getAdminWeatherProfile, putAdminWeatherProfile, recalculateAdminForecast, type ForecastJob, type WeatherProfileInput, type WeatherReferencePoint, type WeatherSector } from "../lib/api";
import { useUnsavedChangesGuard } from "../lib/useUnsavedChangesGuard";
import UnsavedChangesDialog from "../components/admin/UnsavedChangesDialog";

const empty: WeatherProfileInput = { timezone: null, elevation_m: null, coastal_normal_deg: null, exposure: null, roughness_length_m: null, land_reference: null, water_reference: null, quality_tier: "coordinates", physics_version: "wind-v1", active: true, reviewed: false, sectors: [] };
const inputCls = "mt-1 h-10 w-full rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg";
const sectionCls = "mt-5 rounded-md border border-admin-border bg-admin-surface p-5";
const n = (value: string) => value === "" ? null : Number(value);
export const weatherSectorsOverlap = (a: WeatherSector, b: WeatherSector) => {
  const split = (s: WeatherSector) => s.start_deg <= s.end_deg ? [[s.start_deg, s.end_deg]] : [[s.start_deg, 360], [0, s.end_deg]];
  return split(a).some(([x,y]) => split(b).some(([u,v]) => Math.max(x,u) <= Math.min(y,v)));
};

function RefFields({ label, value, onChange }: { label: string; value: WeatherReferencePoint | null; onChange: (v: WeatherReferencePoint | null) => void }) {
  return <fieldset className="rounded-md border border-admin-border p-3"><legend className="px-1 font-medium">{label} (optional)</legend>
    <label className="text-label">Breite<input aria-label={`${label} Breitengrad`} type="number" min={-90} max={90} step="any" className={inputCls} value={value?.latitude ?? ""} onChange={(e) => onChange({ latitude: Number(e.target.value), longitude: value?.longitude ?? 0, source: value?.source, reason: value?.reason })}/></label>
    <label className="mt-2 block text-label">Länge<input aria-label={`${label} Längengrad`} type="number" min={-180} max={180} step="any" className={inputCls} value={value?.longitude ?? ""} onChange={(e) => onChange({ latitude: value?.latitude ?? 0, longitude: Number(e.target.value), source: value?.source, reason: value?.reason })}/></label>
    <label className="mt-2 block text-label">Quelle<input className={inputCls} value={value?.source ?? ""} onChange={(e) => onChange({ latitude: value?.latitude ?? 0, longitude: value?.longitude ?? 0, source: e.target.value, reason: value?.reason })}/></label>
    <label className="mt-2 block text-label">Begründung<input className={inputCls} value={value?.reason ?? ""} onChange={(e) => onChange({ latitude: value?.latitude ?? 0, longitude: value?.longitude ?? 0, source: value?.source, reason: e.target.value })}/></label>
    {value && <button type="button" className="mt-2 text-label text-admin-danger underline" onClick={() => onChange(null)}>Referenz entfernen</button>}
  </fieldset>;
}

export default function AdminWeatherProfile() {
  const { spotId = "" } = useParams();
  const [form, setForm] = useState<WeatherProfileInput>(empty);
  const [baseline, setBaseline] = useState(JSON.stringify(empty));
  const [diag, setDiag] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null); const [errors, setErrors] = useState<Record<string,string>>({});
  const [forecastJob, setForecastJob] = useState<ForecastJob | null>(null);
  const { blocker, setDirty, markClean } = useUnsavedChangesGuard();
  const dirty = JSON.stringify(form) !== baseline;
  useEffect(() => setDirty("weather", dirty), [dirty, setDirty]);
  const load = useCallback(() => { setLoading(true); getAdminWeatherProfile(spotId).then((p) => {
    const next: WeatherProfileInput = { ...p, reviewed: !!p.reviewed_at, expected_updated_at: p.updated_at };
    setForm(next); setBaseline(JSON.stringify(next)); markClean("weather");
  }).catch((e) => { if (e instanceof ApiError && e.status === 404) { setForm(empty); setBaseline(JSON.stringify(empty)); } else setMessage(e instanceof ApiError ? e.message : "Profil konnte nicht geladen werden."); }).finally(() => setLoading(false)); }, [spotId, markClean]);
  useEffect(() => load(), [load]);
  const sectorOverlap = useMemo(() => form.sectors.some((a,i) => a.enabled && form.sectors.slice(i+1).some((b) => b.enabled && weatherSectorsOverlap(a,b))), [form.sectors]);
  const save = async () => { setSaving(true); setMessage(null); setErrors({}); try { const saved = await putAdminWeatherProfile(spotId, form); const next = { ...saved, reviewed: !!saved.reviewed_at, expected_updated_at: saved.updated_at }; setForm(next); setBaseline(JSON.stringify(next)); markClean("weather"); setMessage("Wetterprofil gespeichert."); } catch (e) { if (e instanceof ApiError) { const d = (e.detail as {detail?: unknown})?.detail; if (d && typeof d === "object") setErrors(d as Record<string,string>); else setMessage(e.message); } else setMessage("Speichern fehlgeschlagen."); } finally { setSaving(false); } };
  const runDiagnostics = () => { setDiag(null); setMessage(null); getAdminWeatherDiagnostics(spotId).then(setDiag).catch((e) => setMessage(e instanceof ApiError ? e.message : "Diagnostik fehlgeschlagen.")); };
  const recalculate = async (rebuildProfile: boolean) => { setMessage(null); try { setForecastJob(await recalculateAdminForecast(spotId, rebuildProfile)); } catch (e) { setMessage(e instanceof ApiError ? e.message : "Neuberechnung konnte nicht gestartet werden."); } };
  useEffect(() => { if (!forecastJob || !["queued","processing"].includes(forecastJob.status)) return; const timer=window.setInterval(() => getAdminForecastJob(forecastJob.id).then(setForecastJob).catch(() => undefined), 1200); return () => window.clearInterval(timer); }, [forecastJob]);
  const updateSector = (i: number, patch: Partial<WeatherSector>) => setForm((f) => ({ ...f, sectors: f.sectors.map((s,j) => j === i ? { ...s, ...patch } : s) }));
  if (loading) return <p>Wetterprofil wird geladen …</p>;
  return <div className="max-w-5xl"><UnsavedChangesDialog blocker={blocker}/><Link to="/admin/weather" className="text-admin-primary underline">← Wetterprofile</Link><h1 className="mt-3 text-2xl font-semibold">Wetterprofil</h1>
    {message && <p role="status" className="mt-3 rounded-md border border-admin-border p-3">{message}</p>}
    <section className={sectionCls}><h2 className="text-lg font-semibold">A. Profilstatus</h2><div className="mt-3 grid gap-3 sm:grid-cols-3">
      <label>Qualitätsstufe<select className={inputCls} value={form.quality_tier} onChange={(e) => setForm({...form, quality_tier: e.target.value as WeatherProfileInput["quality_tier"]})}><option value="coordinates">Coordinates</option><option value="coastal">Basis/Küste</option><option value="extended">Extended</option>{form.quality_tier === "advanced" && <option value="advanced" disabled>Advanced (deaktiviert)</option>}</select></label>
      <label className="flex items-center gap-2 pt-7"><input type="checkbox" checked={form.active} onChange={(e) => setForm({...form, active:e.target.checked})}/> Aktiv</label>
      <label className="flex items-center gap-2 pt-7"><input type="checkbox" checked={form.reviewed} onChange={(e) => setForm({...form, reviewed:e.target.checked})}/> Fachlich geprüft</label>
    </div>{errors.quality_tier && <p role="alert" className="text-admin-danger">{errors.quality_tier}</p>}</section>
    <section className={sectionCls}><h2 className="text-lg font-semibold">B. Basisdaten</h2><div className="mt-3 grid gap-4 sm:grid-cols-3">
      <label>IANA-Zeitzone<input className={inputCls} placeholder="Europe/Berlin" value={form.timezone ?? ""} onChange={(e) => setForm({...form, timezone:e.target.value || null})}/>{errors.timezone && <span className="text-admin-danger">{errors.timezone}</span>}</label>
      <label>Höhe (m)<input type="number" step="any" className={inputCls} value={form.elevation_m ?? ""} onChange={(e) => setForm({...form,elevation_m:n(e.target.value)})}/></label>
      <label>Küstennormale (°)<input type="number" min={0} max={359.999} step="0.1" className={inputCls} value={form.coastal_normal_deg ?? ""} onChange={(e) => setForm({...form,coastal_normal_deg:n(e.target.value)})}/><span className="block text-caption text-admin-muted">Nord = 0°, im Uhrzeigersinn; vom Land zum Wasser. Niemals aus facing.</span></label>
    </div><label className="mt-4 block">Zugängliche Kompasssteuerung<input aria-label="Küstennormale per Kompass einstellen" type="range" min={0} max={359} value={form.coastal_normal_deg ?? 0} onChange={(e) => setForm({...form,coastal_normal_deg:Number(e.target.value)})} className="w-full"/></label></section>
    <section className={sectionCls}><h2 className="text-lg font-semibold">C. Referenzpunkte und Exposition</h2><div className="mt-3 grid gap-4 sm:grid-cols-2"><RefFields label="Wasserreferenz" value={form.water_reference} onChange={(v) => setForm({...form,water_reference:v})}/><RefFields label="Landreferenz" value={form.land_reference} onChange={(v) => setForm({...form,land_reference:v})}/></div><div className="mt-3 grid gap-4 sm:grid-cols-2"><label>Rauigkeitslänge (m, optional)<input type="number" min="0.0001" step="any" className={inputCls} value={form.roughness_length_m ?? ""} onChange={(e) => setForm({...form,roughness_length_m:n(e.target.value)})}/></label><label>Exposition<select className={inputCls} value={form.exposure ?? ""} onChange={(e) => setForm({...form,exposure:(e.target.value || null) as WeatherProfileInput["exposure"]})}><option value="">Nicht gesetzt</option><option value="sheltered">Geschützt</option><option value="neutral">Neutral</option><option value="exposed">Exponiert</option></select></label></div></section>
    <section className={sectionCls}><div className="flex justify-between"><h2 className="text-lg font-semibold">D. Windsektoren</h2><button type="button" className="text-admin-primary underline" onClick={() => setForm({...form,sectors:[...form.sectors,{start_deg:0,end_deg:45,speed_factor:1,direction_offset_deg:0,version:1,enabled:true,note:""}]})}>+ Sektor</button></div><p className="text-caption text-admin-muted">Wrap-around ist erlaubt. Advanced: Faktor 0,60–1,35, Richtung ±15°. Lücken bedeuten keine manuelle Regel.</p>{sectorOverlap && <p role="alert" className="text-admin-danger">Aktive Sektoren überschneiden sich.</p>}{errors.sectors && <p role="alert" className="text-admin-danger">{errors.sectors}</p>}
      {form.sectors.map((s,i) => <fieldset key={i} className="mt-3 grid gap-2 rounded-md border border-admin-border p-3 sm:grid-cols-6"><legend>Sektor {i+1}</legend>{(["start_deg","end_deg","speed_factor","direction_offset_deg"] as const).map((key) => <label key={key} className="text-caption">{key}<input type="number" step="any" className={inputCls} value={s[key]} onChange={(e) => updateSector(i,{[key]:Number(e.target.value)})}/></label>)}<label className="flex items-center gap-2"><input type="checkbox" checked={s.enabled} onChange={(e) => updateSector(i,{enabled:e.target.checked})}/> aktiv</label><button type="button" className="text-admin-danger underline" onClick={() => setForm({...form,sectors:form.sectors.filter((_,j)=>j!==i)})}>Löschen</button><label className="sm:col-span-6">Begründung/Quelle<input className={inputCls} value={s.note ?? ""} onChange={(e) => updateSector(i,{note:e.target.value})}/></label></fieldset>)}
    </section>
    <div className="mt-5 flex gap-3"><button type="button" disabled={saving || sectorOverlap} onClick={save} className="rounded-md bg-admin-primary px-4 py-2 font-medium text-admin-primary-fg disabled:opacity-50">{saving ? "Speichert …" : "Profil speichern"}</button><button type="button" onClick={load} className="rounded-md border border-admin-border px-4 py-2">Neu laden</button></div>
    <section className={sectionCls}><h2 className="text-lg font-semibold">E. Forecast-Publisher</h2><div className="mt-3 flex flex-wrap gap-3"><button type="button" disabled={!!forecastJob && ["queued","processing"].includes(forecastJob.status)} onClick={() => recalculate(false)} className="rounded-md bg-admin-primary px-3 py-2 font-medium text-admin-primary-fg disabled:opacity-50">Forecast neu berechnen</button><button type="button" disabled={!!forecastJob && ["queued","processing"].includes(forecastJob.status)} onClick={() => recalculate(true)} className="rounded-md border border-admin-border px-3 py-2 disabled:opacity-50">Basis-Geoprofil aus Cache + Forecast neu berechnen</button><button type="button" onClick={runDiagnostics} className="rounded-md border border-admin-border px-3 py-2">Diagnostik laden</button></div><p className="mt-2 text-caption text-admin-muted">Rastermerkmale sind nur Diagnose/Shadow und verändern den öffentlichen Forecast noch nicht.</p>{forecastJob && <div role="status" className="mt-3 rounded-md border border-admin-border p-3 text-ui"><p>Status: {forecastJob.status} · {forecastJob.progress}%</p>{forecastJob.error && <p className="text-admin-danger">{forecastJob.error}</p>}</div>}{diag && <div className="mt-3 space-y-2 text-ui"><p>Forecasttage: {Array.isArray(diag.days) ? diag.days.length : 0}</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-admin-bg p-3 text-caption">{JSON.stringify(diag.publisher ?? {}, null, 2)}</pre></div>}</section>
  </div>;
}
