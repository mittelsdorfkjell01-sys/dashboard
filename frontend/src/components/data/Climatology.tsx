import { useMemo, useState } from "react";
import type { WindClimatologySection, WindWindowKey } from "../../lib/api";
import { useWindClimatology } from "../../lib/hooks";
import { InfoIcon } from "../../lib/icons";
import type { Spot } from "../../lib/types";

const MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const WINDOWS: [WindWindowKey, string][] = [["10_15", "10–15 kt"], ["15_20", "15–20 kt"], ["20_30", "20–30 kt"], ["30_plus", "30+ kt"]];
const CHART_HEIGHT_PX = 176; // h-44

export function metricValue(section: WindClimatologySection, windowKey: WindWindowKey, unit: "percent" | "hours"): number | null {
  const metric = section.windows[windowKey];
  const value = unit === "percent" ? metric?.percent : metric?.hours_per_day;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function storedWindow(): WindWindowKey {
  const value = sessionStorage.getItem("wind-window");
  return WINDOWS.some(([key]) => key === value) ? value as WindWindowKey : "15_20";
}

/** Rounds a scale ceiling up to a "nice" step (5/10/25/50/100 family) so axis
 *  ticks read as round numbers instead of an arbitrary decimal. */
function niceCeiling(value: number, unit: "percent" | "hours"): number {
  if (value <= 0) return unit === "percent" ? 10 : 2;
  const steps = unit === "percent" ? [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100] : [1, 2, 3, 4, 6, 8, 12, 16, 20, 24];
  return steps.find((step) => step >= value) ?? (unit === "percent" ? 100 : 24);
}

export default function Climatology({ spot }: { spot: Spot }) {
  const { data, loading, error, reload } = useWindClimatology(spot.id);
  const [windowKey, setWindowKey] = useState<WindWindowKey>(storedWindow);
  const [unit, setUnit] = useState<"percent" | "hours">(() => sessionStorage.getItem("wind-unit") === "hours" ? "hours" : "percent");
  const [infoOpen, setInfoOpen] = useState(false);
  const sections = data?.sections;

  const scaleMax = useMemo(() => {
    if (!sections) return unit === "percent" ? 100 : 24;
    const peak = Math.max(0, ...sections.map((s) => metricValue(s, windowKey, unit) ?? 0));
    // ~15% headroom above the tallest bar, rounded to a round tick value —
    // the scale tracks the data instead of a fixed 100%/24h ceiling that
    // leaves most of the chart empty for typical wind-window values.
    return niceCeiling(peak * 1.15, unit);
  }, [sections, windowKey, unit]);

  if (loading) return <ClimatologyEmptyState state="loading" />;
  if (error || !data || data.status === "failed") return <ClimatologyEmptyState state="error" onRetry={reload} />;
  if (data.status !== "ready" || !sections) return <ClimatologyEmptyState state={data.status === "processing" || data.status === "pending" ? "pending" : "unavailable"} />;

  const selectedLabel = WINDOWS.find(([key]) => key === windowKey)![1];
  const axisTicks = [4, 3, 2, 1, 0].map((n) => Math.round((scaleMax * n) / 4));
  const selectedValues = sections.map((section) => metricValue(section, windowKey, unit));
  const hasPositiveValue = selectedValues.some((value) => value != null && value > 0);

  return <div className="p-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="font-display text-lg text-ink">Windmonate</h3>
      <div className="flex min-w-0 flex-wrap gap-2">
        <div className="no-scrollbar flex min-w-0 max-w-full overflow-x-auto rounded-full border border-line p-1" aria-label="Windfenster">{WINDOWS.map(([key, label]) => <button key={key} type="button" onClick={() => { setWindowKey(key); sessionStorage.setItem("wind-window", key); }} aria-pressed={windowKey === key} className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors ${windowKey === key ? "bg-teal text-white" : "text-muted hover:text-ink"}`}>{label}</button>)}</div>
        <div className="no-scrollbar flex min-w-0 max-w-full overflow-x-auto rounded-full border border-line p-1" aria-label="Einheit">{([["percent", "Prozent"], ["hours", "Stunden/Tag"]] as const).map(([key, label]) => <button key={key} type="button" onClick={() => { setUnit(key); sessionStorage.setItem("wind-unit", key); }} aria-pressed={unit === key} className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors ${unit === key ? "bg-teal text-white" : "text-muted hover:text-ink"}`}>{label}</button>)}</div>
      </div>
    </div>
    {data.refresh_status && <p className="mt-3 text-xs text-muted">Eine aktualisierte Berechnung läuft; angezeigt bleibt die letzte vollständige Version.</p>}

    <div className="mt-5 flex gap-2">
      <div className="flex shrink-0 flex-col justify-between text-right text-data-caption text-muted" style={{ height: `${CHART_HEIGHT_PX}px` }} aria-hidden="true">
        {axisTicks.map((tick) => <span key={tick}>{tick}{unit === "percent" ? "%" : "h"}</span>)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="grid grid-cols-12 gap-x-0.5 sm:gap-x-1">
          {MONTHS.map((month, monthIndex) => (
            <div key={month} className="min-w-0 overflow-hidden">
              <div className="relative flex items-end gap-0.5 border-b border-line px-px" style={{ height: `${CHART_HEIGHT_PX}px` }}>
                {[0, 25, 50, 75].map((pct) => (
                  <span key={pct} aria-hidden="true" className="pointer-events-none absolute inset-x-0 border-t border-dashed border-line-soft" style={{ bottom: `${pct}%` }} />
                ))}
                {sections.slice(monthIndex * 4, monthIndex * 4 + 4).map((section) => {
                  const value = metricValue(section, windowKey, unit);
                  const height = value == null ? 0 : Math.max(value > 0 ? 3 : 0, (value / scaleMax) * 100);
                  const end = section.day_end === "month_end" ? "Monatsende" : section.day_end;
                  const percent = metricValue(section, windowKey, "percent");
                  const hours = metricValue(section, windowKey, "hours");
                  const valueLabel = value == null ? "keine Daten" : `${value} ${unit === "percent" ? "Prozent" : "Stunden pro Tag"}`;
                  return <button key={section.section} type="button" className="group relative z-10 flex h-full flex-1 items-end focus:outline-none focus:ring-2 focus:ring-orange" title={`${section.day_start}.–${end} ${month}: ${percent ?? "–"}% · ${hours ?? "–"} h/Tag (${data.period!.start_year}–${data.period!.end_year})`} aria-label={`${section.day_start}. bis ${end} ${month}, ${selectedLabel}: ${valueLabel}`}>
                    {value == null ? (
                      <span aria-hidden="true" className="mx-auto mb-px block h-0.5 w-2/3 rounded bg-line" />
                    ) : value === 0 ? (
                      <span aria-hidden="true" className="mx-auto mb-px block h-0.5 w-2/3 rounded bg-teal/55" />
                    ) : (
                      <span className="mx-auto block w-2/3 rounded-t bg-teal transition-opacity group-hover:opacity-75" style={{ height: `${height}%` }}><span className="sr-only">{value}</span></span>
                    )}
                  </button>;
                })}
              </div>
              <p className="overflow-hidden whitespace-nowrap pt-1 text-center text-sz-8 font-medium uppercase leading-tight text-muted sm:text-data-caption sm:tracking-wider">{month}</p>
            </div>
          ))}
        </div>
      </div>
    </div>

    {!hasPositiveValue && (
      <p className="mt-3 text-sm text-muted" role="status">
        Für {selectedLabel} wurden im gewählten Zeitraum keine Windstunden ermittelt. Die Nulllinien zeigen vollständige Abschnitte mit dem Wert 0.
      </p>
    )}

    <div className="mt-3 flex justify-end">
      <button
        type="button"
        onClick={() => setInfoOpen((open) => !open)}
        aria-expanded={infoOpen}
        aria-controls="climatology-info"
        aria-label={infoOpen ? "Methodische Hinweise ausblenden" : "Methodische Hinweise anzeigen"}
        title={infoOpen ? "Methodische Hinweise ausblenden" : "Methodische Hinweise anzeigen"}
        className="flex h-8 w-8 items-center justify-center rounded-full text-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/30"
      >
        <InfoIcon className="h-5 w-5" />
      </button>
    </div>
    {infoOpen && (
      <div id="climatology-info">
        <p className="text-xs leading-relaxed text-muted">Windrichtung und lokale Bedingungen sind nicht berücksichtigt. Die Stunden müssen nicht zusammenhängend auftreten.</p>
        <p className="mt-2 text-xs text-muted">ERA5 · 10-Meter-Wind · {data.period?.start_year}–{data.period?.end_year} · Tageslichtstunden · ca. {data.grid?.resolution_degrees}° Raster · {data.updated_at ? new Date(data.updated_at).toLocaleDateString("de-DE") : ""} · Open-Meteo / ERA5</p>
      </div>
    )}
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
      <h3 className="font-display text-lg text-ink">Windmonate</h3>
      <div className="mt-5 grid grid-cols-12 gap-x-0.5 sm:gap-x-1" aria-hidden="true">
        {MONTHS.map((month, i) => (
          <div key={month} className="min-w-0 overflow-hidden">
            <div className="flex h-44 items-end gap-0.5 border-b border-line px-px">
              {[22, 36, 18, 29].map((height, index) => (
                <span
                  key={index}
                  className={`mx-auto block w-2/3 rounded-t bg-line-soft ${state === "loading" ? "animate-pulse" : ""}`}
                  style={{ height: `${height}%`, animationDelay: `${(i * 4 + index) * 30}ms` }}
                />
              ))}
            </div>
            <p className="overflow-hidden whitespace-nowrap pt-1 text-center text-sz-8 font-medium uppercase leading-tight text-muted sm:text-data-caption sm:tracking-wider">{month}</p>
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
