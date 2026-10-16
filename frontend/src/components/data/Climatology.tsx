import { useEffect, useMemo, useState } from "react";
import type { WindClimatologyRead, WindClimatologySection, WindWindowKey } from "../../lib/api";
import { useWindClimatology } from "../../lib/hooks";
import { InfoIcon } from "../../lib/icons";
import type { Spot } from "../../lib/types";
import YearRangeSlider from "./YearRangeSlider";

type YearWindow = { fromYear: number; toYear: number };

function storedYears(): YearWindow | null {
  try {
    const raw = sessionStorage.getItem("wind-years");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (typeof parsed?.fromYear === "number" && typeof parsed?.toYear === "number") return parsed;
    }
  } catch {
    // ignore unavailable/blocked sessionStorage
  }
  return null;
}

const MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const WINDOWS: [WindWindowKey, string][] = [["10_15", "10–15 kt"], ["15_20", "15–20 kt"], ["20_30", "20–30 kt"], ["30_plus", "30+ kt"]];

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

/** Axis ticks along the top of the bar track: ~4–5 evenly spaced, round steps up
 *  to the scale maximum (no zero — bars start at the track's left edge). */
function makeTicks(max: number, unit: "percent" | "hours"): number[] {
  const steps = unit === "percent" ? [5, 10, 20, 25, 50] : [1, 2, 5, 10];
  const raw = max / 5;
  const step = steps.find((s) => s >= raw) ?? steps[steps.length - 1];
  const ticks: number[] = [];
  for (let t = step; t <= max + 1e-6; t += step) ticks.push(Math.round(t * 100) / 100);
  return ticks;
}

export default function Climatology({ spot }: { spot: Spot }) {
  const [yearWindow, setYearWindow] = useState<YearWindow | null>(storedYears);
  const { data, loading, error, reload } = useWindClimatology(spot.id, yearWindow);
  const [windowKey, setWindowKey] = useState<WindWindowKey>(storedWindow);
  const [unit, setUnit] = useState<"percent" | "hours">(() => sessionStorage.getItem("wind-unit") === "hours" ? "hours" : "percent");
  const [infoOpen, setInfoOpen] = useState(false);

  // Keep the last ready payload on screen while a new year-window request is in
  // flight, so dragging the slider refreshes the bars in place instead of
  // dropping to the skeleton (which looked like a full page reload).
  const [display, setDisplay] = useState<WindClimatologyRead | null>(null);
  useEffect(() => { if (data && data.status === "ready") setDisplay(data); }, [data]);
  useEffect(() => { setDisplay(null); }, [spot.id]);
  const active = data && data.status === "ready" ? data : display;
  const sections = active?.sections;

  const scaleMax = useMemo(() => {
    if (!sections) return unit === "percent" ? 100 : 24;
    const peak = Math.max(0, ...sections.map((s) => metricValue(s, windowKey, unit) ?? 0));
    // ~15% headroom above the tallest bar, rounded to a round tick value —
    // the scale tracks the data instead of a fixed 100%/24h ceiling that
    // leaves most of the chart empty for typical wind-window values.
    return niceCeiling(peak * 1.15, unit);
  }, [sections, windowKey, unit]);

  if (!active || !sections) {
    if (loading) return <ClimatologyEmptyState state="loading" />;
    if (error || data?.status === "failed") return <ClimatologyEmptyState state="error" onRetry={reload} />;
    return <ClimatologyEmptyState state={data?.status === "processing" || data?.status === "pending" ? "pending" : "unavailable"} />;
  }

  const selectedLabel = WINDOWS.find(([key]) => key === windowKey)![1];
  const selectedValues = sections.map((section) => metricValue(section, windowKey, unit));
  const hasPositiveValue = selectedValues.some((value) => value != null && value > 0);
  const ticks = makeTicks(scaleMax, unit);
  const refreshing = loading && !!display; // a year-window change is in flight
  const toggleUnit = () => {
    const next = unit === "percent" ? "hours" : "percent";
    setUnit(next);
    sessionStorage.setItem("wind-unit", next);
  };

  // Year-range window: only the START year moves (how far into the past); the end
  // is always the present. A chosen window is re-aggregated server-side from the
  // stored per-year data; the full span sends no params so the edge keeps caching.
  const availableYears = active.available_years ?? null;
  const fromYear = availableYears
    ? Math.max(availableYears.min, Math.min(yearWindow?.fromYear ?? availableYears.min, availableYears.max))
    : null;
  const onYearChange = (nextFrom: number) => {
    if (!availableYears) return;
    const next = nextFrom <= availableYears.min ? null : { fromYear: nextFrom, toYear: availableYears.max };
    setYearWindow(next);
    try {
      if (next) sessionStorage.setItem("wind-years", JSON.stringify(next));
      else sessionStorage.removeItem("wind-years");
    } catch {
      // ignore unavailable/blocked sessionStorage
    }
  };

  // Flush to the content column like the meteogram — no card padding of its own.
  return <div>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-lg font-semibold tracking-tight text-ink">Windmonate</h3>
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        {/* Wind-window selection. */}
        <div className="no-scrollbar flex min-w-0 max-w-full overflow-x-auto rounded-full bg-band p-1" aria-label="Windfenster">{WINDOWS.map(([key, label]) => <button key={key} type="button" onClick={() => { setWindowKey(key); sessionStorage.setItem("wind-window", key); }} aria-pressed={windowKey === key} className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors ${windowKey === key ? "bg-ink/10 text-ink" : "text-muted hover:text-ink"}`}>{label}</button>)}</div>
        {/* Unit toggle: one tap swaps Prozent ↔ Stunden pro Tag. */}
        <button type="button" onClick={toggleUnit} aria-label={`Einheit umschalten, aktuell ${unit === "percent" ? "Prozent" : "Stunden pro Tag"}`} className="inline-flex shrink-0 items-center gap-1 rounded-full bg-band px-3 py-1.5 text-xs font-medium text-ink transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
          {unit === "percent" ? "%" : "h/Tag"}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
    </div>
    {active.refresh_status && <p className="mt-3 text-xs text-muted">Eine aktualisierte Berechnung läuft; angezeigt bleibt die letzte vollständige Version.</p>}

    {/* Year-range window selector — start year only; the end is always "today". */}
    {availableYears && fromYear != null && availableYears.max > availableYears.min && (
      <div className="mt-4 max-w-sm">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-data-label font-medium uppercase tracking-wider text-muted">Zeitraum</span>
          <span className="text-data-value tabular-nums text-ink">{fromYear}–{availableYears.max}</span>
        </div>
        <YearRangeSlider fromYear={fromYear} min={availableYears.min} max={availableYears.max} onChange={onYearChange} />
      </div>
    )}

    {/* Horizontal bars: month at left, strength bar in the middle, value at
        right; the scale ticks (current unit) run along the top of the track. */}
    <div className={`mt-5 transition-opacity ${refreshing ? "opacity-60" : ""}`}>
      {/* Top axis — ticks in the current unit, aligned to the bar track. */}
      <div className="flex items-end gap-3 pb-1">
        <div className="w-9 shrink-0 sm:w-10" aria-hidden="true" />
        <div className="relative h-4 flex-1">
          {ticks.map((t) => (
            <span key={t} className="absolute -translate-x-1/2 text-sz-10 tabular-nums text-muted" style={{ left: `${(t / scaleMax) * 100}%` }}>{t}</span>
          ))}
        </div>
        <div className="w-12 shrink-0 text-right text-sz-10 font-medium uppercase tracking-wide text-muted sm:w-14">{unit === "percent" ? "%" : "Std/Tag"}</div>
      </div>

      {/* One row per month; each month's bar is split into its four half-month
          sections (thin stacked sub-bars), so twelve rows replace forty-eight. */}
      <div className="border-b border-line-soft">
        {MONTHS.map((month, monthIndex) => {
          const monthSections = sections.slice(monthIndex * 4, monthIndex * 4 + 4);
          return (
            <div key={month} className="flex items-stretch gap-3 border-t border-line py-1">
              <div className="flex w-9 shrink-0 items-center text-xs font-medium text-muted sm:w-10">{month}</div>
              <div className="flex flex-1 flex-col justify-center gap-1">
                {monthSections.map((section) => {
                  const value = metricValue(section, windowKey, unit);
                  const barPct = value == null ? 0 : Math.max(value > 0 ? 1.5 : 0, (value / scaleMax) * 100);
                  const end = section.day_end === "month_end" ? "Monatsende" : section.day_end;
                  const valueText = value == null ? "–" : unit === "percent" ? `${Math.round(value)}%` : `${value.toFixed(1)} h`;
                  return (
                    <div
                      key={section.section}
                      title={`${section.day_start}.–${end} ${month}: ${valueText} (${active.period!.start_year}–${active.period!.end_year})`}
                      className="relative flex h-2.5 items-center"
                    >
                      {ticks.map((t) => (
                        <span key={t} aria-hidden="true" className="pointer-events-none absolute inset-y-0 w-px bg-line-soft/60" style={{ left: `${(t / scaleMax) * 100}%` }} />
                      ))}
                      {value == null ? (
                        <span aria-hidden="true" className="relative h-px w-2 rounded bg-line" />
                      ) : (
                        <span className="relative h-full rounded-sm bg-teal" style={{ width: `${barPct}%`, minWidth: value > 0 ? 4 : 2 }} />
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="flex w-14 shrink-0 flex-col justify-center gap-1 text-right sm:w-16">
                {monthSections.map((section) => {
                  const value = metricValue(section, windowKey, unit);
                  const valueText = value == null ? "–" : unit === "percent" ? `${Math.round(value)}%` : `${value.toFixed(1)} h`;
                  return <span key={section.section} className="flex h-2.5 items-center justify-end text-sz-10 leading-none tabular-nums text-ink">{valueText}</span>;
                })}
              </div>
            </div>
          );
        })}
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
        className="flex h-8 w-8 items-center justify-center rounded-full text-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30"
      >
        <InfoIcon className="h-5 w-5" />
      </button>
    </div>
    {infoOpen && (
      <div id="climatology-info">
        <p className="text-xs leading-relaxed text-muted">Windrichtung und lokale Bedingungen sind nicht berücksichtigt. Die Stunden müssen nicht zusammenhängend auftreten.</p>
        <p className="mt-2 text-xs text-muted">ERA5 · 10-Meter-Wind · {active.period?.start_year}–{active.period?.end_year} · Tageslichtstunden · ca. {active.grid?.resolution_degrees}° Raster · {active.updated_at ? new Date(active.updated_at).toLocaleDateString("de-DE") : ""} · Open-Meteo / ERA5</p>
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
    <div aria-live="polite">
      <h3 className="text-lg font-semibold tracking-tight text-ink">Windmonate</h3>
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
