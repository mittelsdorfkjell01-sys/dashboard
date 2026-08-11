import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Spot } from "../../lib/types";
import { getSpotClimatology, type ClimatologyResponse } from "../../lib/api";
import { sportLabel } from "../../lib/labels";

const MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const THRESHOLDS = [8, 10, 12, 14, 16, 18, 20, 22, 25, 30];
const WIND_SPORTS = ["kitesurf", "windsurf", "wing", "wavekite"];
const pct = (v: number | null) => v == null ? "—" : `${Math.round(v * 100)} %`;
const num = (v: number | null, unit = "") => v == null ? "—" : `${v.toFixed(1)}${unit}`;

function safeInt(raw: string | null, fallback: number, min: number, max: number) {
  const n = Number(raw);
  return Number.isInteger(n) && n >= min && n <= max ? n : fallback;
}

export default function Climatology({ spot }: { spot: Spot }) {
  const [search, setSearch] = useSearchParams();
  const nowMonth = new Date().getMonth() + 1;
  const initialSport = WIND_SPORTS.includes(search.get("climate_sport") ?? "")
    ? search.get("climate_sport")!
    : (spot.sports?.find((s) => WIND_SPORTS.includes(s)) ?? "kitesurf");
  const [month, setMonth] = useState(() => safeInt(search.get("climate_month"), nowMonth, 1, 12));
  const [threshold, setThreshold] = useState(() => {
    const value = safeInt(search.get("climate_kn"), 14, 6, 35);
    return THRESHOLDS.includes(value) ? value : 14;
  });
  const [view, setView] = useState<"wind" | "result">(() => search.get("climate_view") === "result" ? "result" : "wind");
  const [sport, setSport] = useState(initialSport);
  const [level, setLevel] = useState(() => ["beginner", "advanced", "expert"].includes(search.get("climate_level") ?? "") ? search.get("climate_level")! : "advanced");
  const [material, setMaterial] = useState(() => ["standard", "lightwind", "highwind"].includes(search.get("climate_material") ?? "") ? search.get("climate_material")! : "standard");
  const [data, setData] = useState<ClimatologyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const next = new URLSearchParams(search);
    next.set("climate_view", view); next.set("climate_month", String(month)); next.set("climate_kn", String(threshold));
    next.set("climate_sport", sport); next.set("climate_level", level); next.set("climate_material", material);
    setSearch(next, { replace: true });
    // URL changes are intentionally not a dependency: local state is the source
    // of truth after the initial deep-link restoration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, month, threshold, sport, level, material, setSearch]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true); setError(null);
      getSpotClimatology(spot.id, { month, threshold_kt: threshold, view, sport, level, material }, controller.signal)
        .then(setData)
        .catch((e) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Klimatologie konnte nicht geladen werden."); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [spot.id, month, threshold, view, sport, level, material]);

  const max = useMemo(() => Math.max(1, ...(data?.months.map((m) => m.hours_per_week ?? 0) ?? [1])), [data]);

  return (
    <div className="p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="inline-flex rounded-full bg-ink/5 p-1" aria-label="Klimatologie-Ansicht">
          {(["wind", "result"] as const).map((v) => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)} className={`min-h-10 rounded-full px-4 text-label font-medium ${view === v ? "bg-white text-teal shadow-sm" : "text-muted"}`}>{v === "wind" ? "Wind" : "Ergebnis"}</button>)}
        </div>
        <label className="text-label text-muted">Windschwelle
          <select aria-label="Windschwelle in Knoten" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="ml-2 min-h-10 rounded-lg border border-line bg-white px-3 text-ink">
            {THRESHOLDS.map((v) => <option key={v} value={v}>{v} kn</option>)}
          </select>
        </label>
      </div>

      {view === "result" && <div className="mt-3 flex flex-wrap gap-2">
        <select aria-label="Sportart" value={sport} onChange={(e) => setSport(e.target.value)} className="min-h-10 rounded-lg border border-line bg-white px-3">{WIND_SPORTS.map((s) => <option key={s} value={s}>{sportLabel(s)}</option>)}</select>
        <select aria-label="Können" value={level} onChange={(e) => setLevel(e.target.value)} className="min-h-10 rounded-lg border border-line bg-white px-3"><option value="beginner">Einsteiger</option><option value="advanced">Fortgeschritten</option><option value="expert">Experte</option></select>
        <select aria-label="Materialklasse" value={material} onChange={(e) => setMaterial(e.target.value)} className="min-h-10 rounded-lg border border-line bg-white px-3"><option value="standard">Standard</option><option value="lightwind">Leichtwind</option><option value="highwind">Starkwind</option></select>
      </div>}

      {view === "wind" && <p className="mt-3 text-caption leading-relaxed text-muted">Fahrbare Windstunden sind Tageslichtstunden mit mindestens der gewählten Windstärke. Spotrichtung, Sportart und Material werden in dieser Ansicht nicht berücksichtigt.</p>}

      {error && <div role="alert" className="mt-4 rounded-lg bg-orange/10 p-3 text-body text-ink">{error}</div>}
      {loading && !data && <div className="mt-5 h-52 animate-pulse rounded-lg bg-band" aria-label="Klimatologie wird geladen" />}
      {data && <>
        <div className={`mt-5 overflow-x-auto transition-opacity ${loading ? "opacity-50" : "opacity-100"}`} aria-busy={loading}>
          <div className="grid min-w-[720px] grid-cols-12 gap-2" role="list" aria-label="Monatliche Klimatologie">
            {data.months.map((m) => <button key={m.month} type="button" role="listitem" aria-pressed={month === m.month} onClick={() => setMonth(m.month)} className={`flex h-52 flex-col items-center justify-end rounded-lg border px-1 pt-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal ${month === m.month ? "border-orange bg-orange/10" : "border-transparent hover:bg-band"}`} title={`${MONTHS[m.month - 1]}: ${m.hours_per_week == null ? "keine belastbaren Daten" : `${m.hours_per_week.toFixed(1)} Stunden/Woche`} · ${threshold} kn · ${view === "wind" ? "Wind" : "Ergebnis"}`}>
              <span className="mb-1 text-[11px] font-medium text-ink">{m.hours_per_week == null ? "—" : m.hours_per_week.toFixed(1)}</span>
              <span className={`w-full max-w-7 rounded-t ${m.reliable ? "bg-teal" : "bg-muted/30"}`} style={{ height: `${m.hours_per_week == null ? 4 : Math.max(6, m.hours_per_week / max * 150)}px` }} />
              <span className="mt-2 text-caption font-medium text-muted">{MONTHS[m.month - 1]}</span>
            </button>)}
          </div>
        </div>

        <section className="mt-6 border-t border-line pt-5" aria-live="polite">
          <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="text-title font-semibold text-ink">{MONTHS[month - 1]} · Reiseberechnung</h3><span className="text-caption text-muted">{data.details.years} Jahre · {data.details.windows} rollierende 7-Tage-Fenster</span></div>
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[["Geeignete Stunden/Woche", num(data.details.hours_per_week, " h")], ["P25–P75", `${num(data.details.hours_p25, " h")} – ${num(data.details.hours_p75, " h")}`], ["Mediane gute Tage", num(data.details.median_good_days)], ["Mediane Sessions", num(data.details.median_sessions)], ["≥ 1 Session", pct(data.details.chance_one_session)], ["≥ 3 gute Tage", pct(data.details.chance_three_good_days)], ["≥ 5 gute Tage", pct(data.details.chance_five_good_days)], ["Konfidenz", data.confidence.level]].map(([label, value]) => <div key={label} className="rounded-lg bg-band p-3"><p className="text-caption text-muted">{label}</p><p className="mt-1 text-title font-semibold text-ink">{value}</p></div>)}
          </div>

          {data.details.within_month.length > 0 && <div className="mt-5"><p className="text-label font-semibold text-ink">Verlauf nach Starttag der Urlaubswoche</p><div className="mt-2 flex h-24 items-end gap-1 overflow-x-auto">{data.details.within_month.map((p) => <div key={p.start_day} className="flex min-w-5 flex-1 flex-col items-center justify-end" title={`Start ${p.start_day}.: ${p.hours} h`}><span className="w-full bg-orange/60" style={{ height: `${Math.max(3, p.hours / Math.max(1, ...data.details.within_month.map((x) => x.hours)) * 70)}px` }} /><span className="mt-1 text-[9px] text-muted">{p.start_day}</span></div>)}</div></div>}

          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            <div><p className="text-label font-semibold text-ink">Windstärkenverteilung</p><div className="mt-2 space-y-1">{data.details.speed_distribution.map((b) => <div key={b.from} className="flex justify-between text-caption text-muted"><span>{b.from}–{b.to ?? "∞"} kn</span><span>{b.hours} h</span></div>)}</div></div>
            <div><p className="text-label font-semibold text-ink">Geeignete Stunden nach Tageszeit</p><div className="mt-2 space-y-1">{Object.entries(data.details.time_of_day).map(([key, value]) => <div key={key} className="flex justify-between text-caption text-muted"><span>{{ morning: "Morgen", midday: "Mittag", afternoon: "Nachmittag", evening: "Abend" }[key] ?? key}</span><span>{value} h</span></div>)}</div></div>
            <div><p className="text-label font-semibold text-ink">Windrichtung · 16 Sektoren</p><div className="mt-2 grid grid-cols-8 gap-1" aria-label="Windrichtungsverteilung">{data.details.direction_distribution.map((value, i) => <div key={i} className="rounded bg-teal/10 p-1 text-center text-[10px] text-muted" title={`${i * 22.5}°: ${value} h`}><span className="block font-medium text-ink">{Math.round(i * 22.5)}°</span>{value}</div>)}</div></div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div><p className="text-label font-semibold text-ink">Datenqualität</p><p className="mt-1 text-body text-ink-soft">Abdeckung: {Math.round(data.details.coverage * 100)} % · Konfidenz: {data.confidence.level}</p><ul className="mt-2 list-disc pl-5 text-caption leading-relaxed text-muted">{data.confidence.limitations.map((x) => <li key={x}>{x}</li>)}</ul></div>
            {view === "result" && <div><p className="text-label font-semibold text-ink">Angewendete Herleitung</p><ol className="mt-2 list-decimal pl-5 text-caption leading-relaxed text-muted"><li>Tageslicht und Wind ab {threshold} kn</li><li>Windband für {sportLabel(sport)} / {material}</li><li>gepflegte Spot-Windrichtung und harte Ausschlüsse</li>{sport === "wavekite" && <li>zeitgleiche Wellenhöhe und Periode</li>}<li>Session: mindestens zwei aufeinanderfolgende Stunden</li></ol></div>}
          </div>
        </section>
      </>}
    </div>
  );
}
