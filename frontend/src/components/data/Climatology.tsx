import { useEffect, useRef, useState } from "react";
import type { WindWindowKey } from "../../lib/api";
import { useWindClimatology } from "../../lib/hooks";
import type { Spot } from "../../lib/types";

const MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const WINDOWS: [WindWindowKey, string][] = [["10_15", "10–15 kt"], ["15_20", "15–20 kt"], ["20_30", "20–30 kt"], ["30_plus", "30+ kt"]];

export default function Climatology({ spot }: { spot: Spot }) {
  const { data, loading, error, reload } = useWindClimatology(spot.id);
  const [windowKey, setWindowKey] = useState<WindWindowKey>(() => (sessionStorage.getItem("wind-window") as WindWindowKey) || "15_20");
  const [unit, setUnit] = useState<"percent" | "hours">(() => sessionStorage.getItem("wind-unit") === "hours" ? "hours" : "percent");
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => { sessionStorage.setItem("wind-window", windowKey); }, [windowKey]);
  useEffect(() => { sessionStorage.setItem("wind-unit", unit); }, [unit]);
  useEffect(() => { scroller.current?.children[new Date().getMonth()]?.scrollIntoView({ inline: "start", block: "nearest" }); }, [data?.status]);
  if (loading) return <ClimatologyEmptyState state="loading" />;
  if (error || !data || data.status === "failed") return <ClimatologyEmptyState state="error" onRetry={reload} />;
  if (data.status !== "ready" || !data.sections) return <ClimatologyEmptyState state={data.status === "processing" || data.status === "pending" ? "pending" : "unavailable"} />;
  const sections = data.sections;
  const selectedLabel = WINDOWS.find(([key]) => key === windowKey)![1];
  return <div className="p-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><h3 className="font-display text-lg text-ink">Windfenster im Jahresverlauf</h3><p className="text-sm text-muted">Wie häufig liegt der Wind tagsüber im gewählten Bereich?</p></div>
      <div className="flex flex-wrap gap-2">
        <div className="flex rounded-full border border-line p-1" aria-label="Windfenster">{WINDOWS.map(([key, label]) => <button key={key} onClick={() => setWindowKey(key)} aria-pressed={windowKey === key} className={`rounded-full px-3 py-1 text-xs ${windowKey === key ? "bg-ink text-white" : "text-muted"}`}>{label}</button>)}</div>
        <div className="flex rounded-full border border-line p-1" aria-label="Einheit">{([["percent", "Prozent"], ["hours", "Stunden/Tag"]] as const).map(([key, label]) => <button key={key} onClick={() => setUnit(key)} aria-pressed={unit === key} className={`rounded-full px-3 py-1 text-xs ${unit === key ? "bg-ink text-white" : "text-muted"}`}>{label}</button>)}</div>
      </div>
    </div>
    {data.refresh_status && <p className="mt-3 text-xs text-muted">Eine aktualisierte Berechnung läuft; angezeigt bleibt die letzte vollständige Version.</p>}
    <div ref={scroller} className="mt-5 flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3">
      {MONTHS.map((month, monthIndex) => <div key={month} className="w-36 shrink-0 snap-start"><div className="flex h-44 items-end gap-1 border-b border-line px-1">{sections.slice(monthIndex * 4, monthIndex * 4 + 4).map((section) => {
        const metric = section.windows[windowKey]; const value = unit === "percent" ? metric.percent : metric.hours_per_day; const height = Math.max(value > 0 ? 3 : 0, value / (unit === "percent" ? 100 : 24) * 100);
        const end = section.day_end === "month_end" ? "Monatsende" : section.day_end;
        return <button key={section.section} className="group relative flex h-full flex-1 items-end focus:outline-none focus:ring-2 focus:ring-orange" title={`${section.day_start}.–${end} ${month}: ${metric.percent}% · ${metric.hours_per_day} h/Tag (${data.period!.start_year}–${data.period!.end_year})`} aria-label={`${section.day_start}. bis ${end} ${month}, ${selectedLabel}: ${metric.percent} Prozent, ${metric.hours_per_day} Stunden pro Tag`}><span className="w-full rounded-t bg-cyan-600 transition-opacity group-hover:opacity-75" style={{ height: `${height}%` }}><span className="sr-only">{value}</span></span></button>;
      })}</div><p className="pt-2 text-center text-xs font-medium uppercase tracking-wider text-muted">{month}</p></div>)}
    </div>
    <p className="mt-3 text-xs leading-relaxed text-muted">Windrichtung und lokale Bedingungen sind nicht berücksichtigt. Die Stunden müssen nicht zusammenhängend auftreten.</p>
    <p className="mt-2 text-xs text-muted">ERA5 · 10-Meter-Wind · {data.period?.start_year}–{data.period?.end_year} · Tageslichtstunden · ca. {data.grid?.resolution_degrees}° Raster · {data.updated_at ? new Date(data.updated_at).toLocaleDateString("de-DE") : ""} · Open-Meteo / ERA5</p>
  </div>;
}

function ClimatologyEmptyState({ state, onRetry }: {
  state: "loading" | "pending" | "unavailable" | "error";
  onRetry?: () => void;
}) {
  const copy = {
    loading: "Windmonate werden geladen …",
    pending: "Die historischen Winddaten werden gerade berechnet.",
    unavailable: "Für diesen Spot liegen noch keine historischen Winddaten vor.",
    error: "Die Windmonate konnten nicht geladen werden.",
  }[state];

  return (
    <div className="p-4" aria-live="polite">
      <h3 className="font-display text-lg text-ink">Windfenster im Jahresverlauf</h3>
      <p className="mt-1 text-sm text-muted">Wie häufig liegt der Wind tagsüber im gewählten Bereich?</p>
      <div className="mt-5 flex gap-3 overflow-hidden pb-3" aria-hidden="true">
        {MONTHS.map((month) => (
          <div key={month} className="w-24 shrink-0 sm:w-28">
            <div className="flex h-24 items-end gap-1 border-b border-line px-1">
              {[22, 36, 18, 29].map((height, index) => (
                <span
                  key={index}
                  className={`w-full rounded-t bg-line-soft ${state === "loading" ? "animate-pulse" : ""}`}
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
            <p className="pt-2 text-center text-xs font-medium uppercase tracking-wider text-muted">{month}</p>
          </div>
        ))}
      </div>
      <div role={state === "error" ? "alert" : "status"} className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <p className="text-sm text-muted">{copy}</p>
        {state === "error" && onRetry && (
          <button type="button" onClick={onRetry} className="text-sm font-medium text-teal underline decoration-teal/40 underline-offset-4 hover:text-teal-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/30">
            Erneut laden
          </button>
        )}
      </div>
    </div>
  );
}
