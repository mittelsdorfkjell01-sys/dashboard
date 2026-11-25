import Segmented from "../ui/Segmented";
import { useEffect, useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { WindClimatologyRead, WindClimatologySection, WindWindowKey } from "../../lib/api";
import { useWindClimatology } from "../../lib/hooks";
import { InfoIcon } from "../../lib/icons";
import type { Spot } from "../../lib/types";
import { windColor } from "../../lib/windScale";
import YearRangeSlider from "./YearRangeSlider";

type YearWindow = { fromYear: number; toYear: number };
type Unit = "percent" | "hours";
type View = "raster" | "kurve";

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

function readSession(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSession(key: string, value: string) {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // ignore unavailable/blocked sessionStorage
  }
}

const MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const MONTHS_LONG = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const WINDOWS: [WindWindowKey, string][] = [["10_15", "10–15 kn"], ["15_20", "15–20 kn"], ["20_30", "20–30 kn"], ["30_plus", "30+ kn"]];
/** One hue per wind window, taken from the site's wind scale at the window's
 *  lower edge, so the Windmonate speak the same colours as the meteogram. */
const WINDOW_HEX: Record<WindWindowKey, string> = {
  "10_15": windColor(10),
  "15_20": windColor(15),
  "20_30": windColor(20),
  "30_plus": windColor(30),
};

export function metricValue(section: WindClimatologySection, windowKey: WindWindowKey, unit: Unit): number | null {
  const metric = section.windows[windowKey];
  const value = unit === "percent" ? metric?.percent : metric?.hours_per_day;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function storedWindow(): WindWindowKey {
  const value = readSession("wind-window");
  return WINDOWS.some(([key]) => key === value) ? value as WindWindowKey : "15_20";
}

/** Rounds a scale ceiling up to a "nice" step (5/10/25/50/100 family) so axis
 *  labels read as round numbers instead of an arbitrary decimal. */
function niceCeiling(value: number, unit: Unit): number {
  if (value <= 0) return unit === "percent" ? 10 : 2;
  // Even steps only, so the half-way gridline is a round number too.
  const steps = unit === "percent" ? [4, 6, 8, 10, 20, 30, 40, 50, 60, 80, 100] : [1, 2, 3, 4, 6, 8, 12, 16, 20, 24];
  return steps.find((step) => step >= value) ?? (unit === "percent" ? 100 : 24);
}

function formatValue(value: number | null, unit: Unit): string {
  if (value == null) return "–";
  if (unit === "hours") return `${value.toFixed(1).replace(".", ",")} h`;
  const rounded = value > 0 && value < 1 ? value.toFixed(1).replace(".", ",") : String(Math.round(value));
  return `${rounded} %`;
}

/** Short, readable label for a quarter-month: "1.–7.", "24.–Ende". */
function sectionLabel(section: WindClimatologySection): string {
  return `${section.day_start}.–${section.day_end === "month_end" ? "Ende" : `${section.day_end}.`}`;
}

/** Index of the quarter-month that contains today, or -1 if none matches. */
function todayIndex(sections: WindClimatologySection[]): number {
  const now = new Date();
  const month = now.getMonth() + 1;
  const day = now.getDate();
  return sections.findIndex(
    (s) => s.month === month && day >= s.day_start && (s.day_end === "month_end" || day <= s.day_end),
  );
}

/**
 * Windmonate (V2): how often each wind window blew in daylight, per
 * quarter-month, from ERA5. Two readings of the same numbers, switchable
 * (chosen 2026-11-24):
 *  - Raster — 12 months × 4 quarters; the colour depth runs from the year's
 *    lowest to its highest value in the window's wind-scale hue, the number
 *    sits in the cell, the month mean underneath. The whole year at once.
 *  - Kurve  — one line through all 48 quarters with the highest and lowest
 *    value labelled and today marked; dragging across shows every value.
 * Both share one readout line underneath, so a value is always readable in
 * full words, not only as colour or position.
 */
export default function Climatology({ spot }: { spot: Spot }) {
  const [yearWindow, setYearWindow] = useState<YearWindow | null>(storedYears);
  const { data, loading, error, reload } = useWindClimatology(spot.id, yearWindow);
  const [windowKey, setWindowKey] = useState<WindWindowKey>(storedWindow);
  const [unit, setUnit] = useState<Unit>(() => (readSession("wind-unit") === "hours" ? "hours" : "percent"));
  const [view, setView] = useState<View>(() => (readSession("wind-view") === "kurve" ? "kurve" : "raster"));
  const [selected, setSelected] = useState<number | null>(null);
  const [infoOpen, setInfoOpen] = useState(false);

  // Keep the last ready payload on screen while a new year-window request is in
  // flight, so dragging the slider refreshes the values in place instead of
  // dropping to the skeleton (which looked like a full page reload).
  const [display, setDisplay] = useState<WindClimatologyRead | null>(null);
  useEffect(() => { if (data && data.status === "ready") setDisplay(data); }, [data]);
  useEffect(() => { setDisplay(null); setSelected(null); }, [spot.id]);
  const active = data && data.status === "ready" ? data : display;
  const sections = active?.sections;

  const values = useMemo(
    () => (sections ?? []).map((section) => metricValue(section, windowKey, unit)),
    [sections, windowKey, unit],
  );

  if (!active || !sections || sections.length === 0) {
    if (loading) return <ClimatologyEmptyState state="loading" />;
    if (error || data?.status === "failed") return <ClimatologyEmptyState state="error" onRetry={reload} />;
    return <ClimatologyEmptyState state={data?.status === "processing" || data?.status === "pending" ? "pending" : "unavailable"} />;
  }

  const today = todayIndex(sections);
  const current = selected != null && selected < sections.length ? selected : today >= 0 ? today : 0;
  const selectedLabel = WINDOWS.find(([key]) => key === windowKey)![1];
  const hex = WINDOW_HEX[windowKey];
  const hasPositiveValue = values.some((value) => value != null && value > 0);
  const refreshing = loading && !!display; // a year-window change is in flight
  const period = active.period ? `${active.period.start_year}–${active.period.end_year}` : "";

  const pick = (index: number) => setSelected(Math.max(0, Math.min(sections.length - 1, index)));

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

  const chosen = sections[current];
  const readout = chosen
    ? {
        when: `${sectionLabel(chosen)} ${MONTHS_LONG[chosen.month - 1]}`,
        percent: formatValue(metricValue(chosen, windowKey, "percent"), "percent"),
        hours: formatValue(metricValue(chosen, windowKey, "hours"), "hours"),
      }
    : null;

  // Flush to the content column like the meteogram — no card padding of its own.
  return <div>
    {/* Controls (chosen 2026-11-24, "Legende als Auswahl"): reading and unit
        as two small symbol toggles beside the heading; the wind windows as
        colour chips above the chart — the legend is the choice. */}
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-lead font-semibold tracking-tight text-ink">Windmonate</h3>
      <div className="flex items-center gap-2">
        <IconToggle<View>
          label="Ansicht"
          value={view}
          onChange={(next) => { setView(next); writeSession("wind-view", next); }}
          options={[
            { id: "raster", label: "Raster", icon: <RasterIcon /> },
            { id: "kurve", label: "Kurve", icon: <CurveIcon /> },
          ]}
        />
        <IconToggle<Unit>
          label="Einheit"
          value={unit}
          onChange={(next) => { setUnit(next); writeSession("wind-unit", next); }}
          options={[
            { id: "percent", label: "Prozent der Tageslichtstunden", icon: <span className="font-figures text-caption font-bold">%</span> },
            { id: "hours", label: "Stunden pro Tag", icon: <span className="font-figures text-caption font-bold">h</span> },
          ]}
        />
      </div>
    </div>
    {/* All four windows always in one row: equal shares of the width, the
        "kn" dropped on narrow screens so they fit side by side on a phone. */}
    <div className="mt-3 grid grid-cols-4 gap-1.5" role="group" aria-label="Windfenster">
      {WINDOWS.map(([key, text]) => {
        const on = key === windowKey;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={on}
            aria-label={text}
            onClick={() => { setWindowKey(key); writeSession("wind-window", key); }}
            className={`relative inline-flex min-h-7 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-1.5 text-caption sm:px-2.5 font-medium transition-[color,background-color,box-shadow] duration-fast before:absolute before:inset-x-0 before:-inset-y-2 before:content-[''] motion-reduce:transition-none ${
              on ? "text-ink" : "text-muted hover:text-ink"
            }`}
            style={{
              boxShadow: `inset 0 0 0 ${on ? "1.5px" : "1px"} ${on ? WINDOW_HEX[key] : "var(--sw-line)"}`,
              background: on ? `color-mix(in oklab, ${WINDOW_HEX[key]} 18%, transparent)` : "transparent",
            }}
          >
            <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-[2px]" style={{ background: WINDOW_HEX[key] }} />
            <span aria-hidden="true">
              {text.replace(" kn", "")}
              <span className="hidden sm:inline"> kn</span>
            </span>
          </button>
        );
      })}
    </div>
    {active.refresh_status && <p className="mt-3 text-caption text-muted">Eine aktualisierte Berechnung läuft; angezeigt bleibt die letzte vollständige Version.</p>}

    {/* Year-range window selector — start year only; the end is always "today". */}
    {availableYears && fromYear != null && availableYears.max > availableYears.min && (
      <div className="mt-4 max-w-sm">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-data-label font-medium uppercase text-muted">Zeitraum</span>
          <span className="text-data-value tabular-nums text-ink">{fromYear}–{availableYears.max}</span>
        </div>
        <YearRangeSlider fromYear={fromYear} min={availableYears.min} max={availableYears.max} onChange={onYearChange} />
      </div>
    )}

    {/* Keyed by view: the newly chosen reading fades up into place (.swd-view-in). */}
    <div key={view} className={`swd-view-in mt-5 transition-opacity ${refreshing ? "opacity-60" : ""}`}>
      {view === "raster" ? (
        <Raster sections={sections} values={values} unit={unit} hex={hex} windowKey={windowKey} current={current} today={today} onPick={pick} />
      ) : (
        <Curve sections={sections} values={values} unit={unit} hex={hex} current={current} today={today} onPick={pick} readoutText={readout ? `${readout.when}: ${unit === "percent" ? readout.percent : readout.hours}` : ""} />
      )}
    </div>

    {/* The selected value is read in the chart itself (cell number, or the
        moving label on the curve's axis); screen readers get it here. */}
    {readout && (
      <p className="sr-only" aria-live="polite">
        {readout.when}, {selectedLabel}: {readout.percent} der Tageslichtstunden, {readout.hours} pro Tag
      </p>
    )}

    {!hasPositiveValue && (
      <p className="mt-3 text-ui text-muted" role="status">
        Für {selectedLabel} wurden im gewählten Zeitraum keine Windstunden ermittelt.
      </p>
    )}

    <div className="mt-3 flex items-center justify-between gap-3 border-t border-line pt-2">
      <p className="text-data-caption text-muted">ERA5 · 10 m · {period} · Tageslicht</p>
      <button
        type="button"
        onClick={() => setInfoOpen((open) => !open)}
        aria-expanded={infoOpen}
        aria-controls="climatology-info"
        aria-label={infoOpen ? "Methodische Hinweise ausblenden" : "Methodische Hinweise anzeigen"}
        title={infoOpen ? "Methodische Hinweise ausblenden" : "Methodische Hinweise anzeigen"}
        className="-m-1.5 flex h-11 w-11 items-center justify-center rounded-full text-muted transition-colors hover:text-ink"
      >
        <InfoIcon className="h-5 w-5" />
      </button>
    </div>
    {infoOpen && (
      <div id="climatology-info" className="swd-view-in">
        <p className="text-caption leading-relaxed text-muted">Anteil der Tageslichtstunden, in denen der Wind im gewählten Fenster lag. Windrichtung und lokale Bedingungen sind nicht berücksichtigt. Die Stunden müssen nicht zusammenhängend auftreten.</p>
        <p className="mt-2 text-caption text-muted">ERA5 · 10-Meter-Wind · {period} · Tageslichtstunden · ca. {active.grid?.resolution_degrees}° Raster · {active.updated_at ? new Date(active.updated_at).toLocaleDateString("de-DE") : ""} · Open-Meteo / ERA5</p>
      </div>
    )}
  </div>;
}

// --- Raster: 12 months × 4 quarters ---------------------------------------

function Raster({
  sections, values, unit, hex, windowKey, current, today, onPick,
}: {
  sections: WindClimatologySection[];
  values: (number | null)[];
  unit: Unit;
  hex: string;
  windowKey: WindWindowKey;
  current: number;
  today: number;
  onPick: (index: number) => void;
}) {
  const valid = values.filter((v): v is number => v != null);
  const min = valid.length ? Math.min(...valid) : 0;
  const max = valid.length ? Math.max(...valid) : 0;
  const quarters = sections.slice(0, 4);

  // One tab stop for all 48 cells: arrows move by month (←/→) and quarter (↑/↓).
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const moves: Record<string, number> = { ArrowRight: 4, ArrowLeft: -4, ArrowDown: 1, ArrowUp: -1 };
    const step = moves[event.key];
    if (step == null) return;
    event.preventDefault();
    const next = index + step;
    if (next < 0 || next >= sections.length) return;
    onPick(next);
    const grid = event.currentTarget.closest("[data-wind-raster]");
    grid?.querySelector<HTMLButtonElement>(`[data-index="${next}"]`)?.focus();
  };

  const cell = (index: number) => {
    const section = sections[index];
    const value = values[index];
    if (!section) return <span key={`empty-${index}`} />;
    // Colour depth from the year's lowest to its highest value in this window.
    const share = value == null ? 0 : max > min ? (value - min) / (max - min) : 1;
    const mix = value == null ? 0 : Math.round(14 + share * 86);
    // Dark figures on the light yellow of 20–30 kn once it is saturated.
    const ink = value == null ? "var(--sw-muted)" : windowKey === "20_30" && mix > 45 ? "var(--sw-page)" : mix < 30 ? "var(--sw-ink-soft)" : "var(--sw-ink)";
    const number = value == null ? "–" : unit === "hours" ? value.toFixed(1).replace(".", ",") : value > 0 && value < 1 ? value.toFixed(1).replace(".", ",") : Math.round(value);
    const isCurrent = index === current;
    return (
      <button
        key={index}
        type="button"
        data-index={index}
        tabIndex={isCurrent ? 0 : -1}
        aria-pressed={isCurrent}
        aria-label={`${sectionLabel(section)} ${MONTHS_LONG[section.month - 1]}: ${formatValue(value, unit)}`}
        onClick={() => onPick(index)}
        onKeyDown={(event) => onKeyDown(event, index)}
        className={`grid h-8 place-items-center rounded-[6px] font-figures text-micro font-semibold tabular-nums transition-[background-color] duration-base sm:h-9 sm:text-caption ${
          isCurrent ? "outline outline-2 outline-offset-1 outline-ink" : ""
        }`}
        style={{
          background: value == null ? "var(--sw-band)" : `color-mix(in oklab, ${hex} ${mix}%, var(--sw-band))`,
          color: ink,
          boxShadow: index === today ? "inset 0 -2px 0 var(--sw-ink)" : undefined,
        }}
      >
        {number}
      </button>
    );
  };

  const monthMean = (month: number) => {
    const own = values.slice(month * 4, month * 4 + 4).filter((v): v is number => v != null);
    if (!own.length) return "–";
    const mean = own.reduce((a, b) => a + b, 0) / own.length;
    return unit === "hours" ? mean.toFixed(1).replace(".", ",") : Math.round(mean);
  };

  return (
    <div>
      <div
        data-wind-raster
        role="group"
        aria-label={`Windmonate als Raster, ${unit === "percent" ? "Prozent der Tageslichtstunden" : "Stunden pro Tag"}`}
        className="grid grid-cols-[2.25rem_repeat(12,minmax(0,1fr))] gap-0.5 sm:grid-cols-[3.5rem_repeat(12,minmax(0,1fr))] sm:gap-1"
      >
        <span aria-hidden="true" />
        {MONTHS.map((month) => (
          <span key={month} aria-hidden="true" className="pb-1 text-center text-micro text-muted sm:text-data-caption">{month}</span>
        ))}
        {quarters.map((quarter, q) => (
          <div key={quarter.section} className="contents">
            <span aria-hidden="true" className="flex items-center text-micro tabular-nums text-muted sm:text-data-caption">{sectionLabel(quarter)}</span>
            {MONTHS.map((_, month) => cell(month * 4 + q))}
          </div>
        ))}
        <span aria-hidden="true" className="border-t border-line pt-1.5 text-micro text-muted sm:text-data-caption">Mittel</span>
        {MONTHS.map((month, i) => (
          <span key={month} aria-hidden="true" className="border-t border-line pt-1.5 text-center font-figures text-caption font-bold tabular-nums text-ink sm:text-data-value">{monthMean(i)}</span>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-data-caption text-muted" aria-hidden="true">
        <span className="font-figures tabular-nums">{formatValue(min, unit)}</span>
        <span className="h-2 w-32 rounded-full" style={{ background: `linear-gradient(90deg, color-mix(in oklab, ${hex} 14%, var(--sw-band)), ${hex})` }} />
        <span className="font-figures tabular-nums">{formatValue(max, unit)}</span>
        <span>· Unterstrich = heute</span>
      </div>
    </div>
  );
}

// --- Kurve: one line through the 48 quarters --------------------------------

const CURVE_W = 1000;
const CURVE_H = 220;

function Curve({
  sections, values, unit, hex, current, today, onPick, readoutText,
}: {
  sections: WindClimatologySection[];
  values: (number | null)[];
  unit: Unit;
  hex: string;
  current: number;
  today: number;
  onPick: (index: number) => void;
  readoutText: string;
}) {
  const count = sections.length;
  const valid = values.map((v, i) => [v, i] as const).filter((p): p is readonly [number, number] => p[0] != null);
  const peak = valid.length ? Math.max(...valid.map(([v]) => v)) : 0;
  const scaleMax = niceCeiling(peak * 1.1, unit);
  const x = (i: number) => ((i + 0.5) / count) * 100; // percent of width
  const y = (v: number) => (1 - v / scaleMax) * 100; // percent of height

  // Line and area, broken where a quarter has no value.
  // A light smoothing of the drawn line only (neighbours weighted ¼ · ½ · ¼),
  // so single quarter-month spikes don't read as needles. Every number shown
  // — axis reading, high, low — stays the exact value; the markers sit on the
  // drawn line.
  const drawn = values.map((v, i) => {
    if (v == null) return null;
    const prev = values[i - 1] ?? v;
    const next = values[i + 1] ?? v;
    return prev * 0.25 + v * 0.5 + next * 0.25;
  });
  const yDrawn = (i: number) => y(drawn[i] ?? values[i] ?? 0);
  const runs: [number, number][][] = [];
  values.forEach((v, i) => {
    if (v == null) return;
    const point: [number, number] = [(x(i) / 100) * CURVE_W, (yDrawn(i) / 100) * CURVE_H];
    const last = runs[runs.length - 1];
    if (last && values[i - 1] != null) last.push(point);
    else runs.push([point]);
  });
  // Drawn as a smooth monotone curve through the exact values (2026-11-24):
  // the corners round off, but the line never overshoots a value and the
  // dots and readings still sit on it.
  const line = runs.map(smoothPath).join(" ");
  const area = runs
    .filter((run) => run.length > 1)
    .map((run) => `${smoothPath(run)} L${run[run.length - 1][0].toFixed(1)} ${CURVE_H} L${run[0][0].toFixed(1)} ${CURVE_H} Z`)
    .join(" ");

  const hi = valid.reduce((best, p) => (p[0] > best[0] ? p : best), valid[0] ?? [0, 0]);
  const lo = valid.reduce((best, p) => (p[0] < best[0] ? p : best), valid[0] ?? [0, 0]);
  const axis = [0, 0.5, 1].map((f) => scaleMax * f);
  const axisLabel = (v: number) => (unit === "hours" ? (Number.isInteger(v) ? String(v) : v.toFixed(1).replace(".", ",")) : String(Math.round(v)));

  const indexAt = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return Math.floor(((event.clientX - rect.left) / rect.width) * count);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const keys: Record<string, number> = { ArrowRight: current + 1, ArrowLeft: current - 1, Home: 0, End: count - 1 };
    const next = keys[event.key];
    if (next == null) return;
    event.preventDefault();
    onPick(next);
  };

  const currentValue = values[current];
  const annotation = (index: number, value: number, label: string, above: boolean) => {
    const left = x(index);
    const top = yDrawn(index);
    const alignRight = left > 55;
    return (
      <span
        className="pointer-events-none absolute whitespace-nowrap text-data-caption text-ink-soft"
        style={{
          top: `calc(${top}% ${above && top > 14 ? "- 1.6rem" : "+ 0.6rem"})`,
          ...(alignRight ? { right: `calc(${100 - left}% + 0.4rem)` } : { left: `calc(${left}% + 0.5rem)` }),
        }}
      >
        {label} <span className="font-figures font-semibold tabular-nums text-ink">{formatValue(value, unit)}</span>
        <span className="hidden sm:inline">{" · "}{sectionLabel(sections[index])} {MONTHS[sections[index].month - 1]}</span>
      </span>
    );
  };

  return (
    <div className="pt-5">
      <div
        role="slider"
        tabIndex={0}
        aria-label="Windmonate als Kurve, Viertelmonat wählen"
        aria-valuemin={1}
        aria-valuemax={count}
        aria-valuenow={current + 1}
        aria-valuetext={readoutText}
        onPointerDown={(event) => onPick(indexAt(event))}
        onPointerMove={(event) => { if (event.pointerType === "mouse" || event.buttons) onPick(indexAt(event)); }}
        onKeyDown={onKeyDown}
        className="relative h-56 touch-pan-y"
      >
        {axis.map((_, i) => (
          <div key={i} className="absolute inset-x-0 border-t border-line" style={{ top: `${(1 - i / 2) * 100}%` }} aria-hidden="true" />
        ))}
        <svg viewBox={`0 0 ${CURVE_W} ${CURVE_H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
          <path d={area} fill={hex} fillOpacity={0.16} />
          <path d={line} fill="none" stroke={hex} strokeWidth={2.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
        {/* Axis values sit on their own gridline inside the plot (chosen
            2026-11-24, "Werte in der Fläche"): no gutter, the curve gets the
            full width. A small page-coloured ground keeps them legible over
            the curve; the top value carries the unit. A value steps aside
            while the moving reading passes over it. */}
        {axis.map((v, i) => {
          const near = currentValue != null && Math.abs(y(v) - yDrawn(current)) < 12;
          return (
            <span
              key={`label-${i}`}
              aria-hidden="true"
              className={`pointer-events-none absolute left-0 bg-page pr-1 font-figures text-data-caption leading-none tabular-nums text-muted transition-opacity duration-fast ${near ? "opacity-0" : "opacity-100"}`}
              style={{ top: `calc(${(1 - i / 2) * 100}% - ${i === 0 ? "0.875rem" : "1rem"})` }}
            >
              {axisLabel(v)}{i === axis.length - 1 ? (unit === "hours" ? " h" : " %") : ""}
            </span>
          );
        })}
        {/* The value under the cursor, riding the left edge at its height. */}
        {currentValue != null && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-0 rounded-[6px] bg-ink px-1.5 py-0.5 font-figures text-data-caption font-bold leading-none tabular-nums text-page"
            style={{ top: `calc(${yDrawn(current)}% - 0.6rem)` }}
          >
            {unit === "hours" ? currentValue.toFixed(1).replace(".", ",") : Math.round(currentValue)}
          </span>
        )}
        {today >= 0 && (
          <div className="pointer-events-none absolute inset-y-0 border-l border-dashed border-muted" style={{ left: `${x(today)}%` }} aria-hidden="true">
            <span className={`absolute -top-5 whitespace-nowrap text-data-caption text-muted ${x(today) > 85 ? "right-1" : "left-1"}`}>heute</span>
          </div>
        )}
        {valid.length > 0 && (
          <div aria-hidden="true">
            <span className="pointer-events-none absolute -ml-[4.5px] -mt-[4.5px] h-[9px] w-[9px] rounded-full bg-page ring-2 ring-ink" style={{ left: `${x(hi[1])}%`, top: `${yDrawn(hi[1])}%` }} />
            <span className="pointer-events-none absolute -ml-[4.5px] -mt-[4.5px] h-[9px] w-[9px] rounded-full bg-page ring-2 ring-ink" style={{ left: `${x(lo[1])}%`, top: `${yDrawn(lo[1])}%` }} />
            {annotation(hi[1], hi[0], "Höchstwert", true)}
            {hi[1] !== lo[1] && annotation(lo[1], lo[0], "Tiefstwert", false)}
          </div>
        )}
        <div className="pointer-events-none absolute inset-y-0 w-px bg-ink" style={{ left: `${x(current)}%` }} aria-hidden="true" />
        {currentValue != null && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -ml-[4.5px] -mt-[4.5px] h-[9px] w-[9px] rounded-full bg-page ring-2 ring-ink"
            style={{ left: `${x(current)}%`, top: `${yDrawn(current)}%` }}
          />
        )}
      </div>
      <div className="grid grid-cols-12 text-micro text-muted sm:text-data-caption" aria-hidden="true">
        {MONTHS.map((month) => <span key={month} className="border-l border-line pl-0.5 sm:pl-1">{month}</span>)}
      </div>
    </div>
  );
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
      <h3 className="text-lead font-semibold tracking-tight text-ink">Windmonate</h3>
      <div className="mt-5 grid grid-cols-12 gap-0.5 sm:gap-1" aria-hidden="true">
        {Array.from({ length: 48 }).map((_, i) => (
          <span
            key={i}
            className={`h-8 rounded-[6px] bg-line-soft sm:h-9 ${state === "loading" ? "animate-pulse" : ""}`}
            style={{ animationDelay: `${(i % 12) * 30}ms` }}
          />
        ))}
      </div>
      <div role={state === "error" ? "alert" : "status"} className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <p className="text-ui text-muted">{copy}</p>
        {state === "error" && onRetry && (
          <button type="button" onClick={onRetry} className="text-ui font-medium text-teal underline decoration-teal/40 underline-offset-4 hover:text-teal-hover">
            Erneut laden
          </button>
        )}
      </div>
    </div>
  );
}

/** Two or more symbol buttons in a small band tray; the pressed one is the
 *  ink chip. 28px high, with the tap target extended to 44px. */
// The Windmonate symbol switches: the site's small Segmented switch with a
// symbol per option (2026-11-25: one switch for the whole Daten tab, with the
// language switch's motion; until then a tray without a sliding surface).
function IconToggle<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (next: T) => void;
  options: { id: T; label: string; icon: React.ReactNode }[];
}) {
  return (
    <Segmented
      size="sm"
      label={label}
      value={value}
      onChange={onChange}
      options={options.map((option) => ({ id: option.id, label: option.icon, ariaLabel: option.label, title: option.label }))}
    />
  );
}

function RasterIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <rect x="3" y="5" width="5" height="5" rx="1" /><rect x="10" y="5" width="5" height="5" rx="1" /><rect x="17" y="5" width="4" height="5" rx="1" />
      <rect x="3" y="13" width="5" height="5" rx="1" /><rect x="10" y="13" width="5" height="5" rx="1" /><rect x="17" y="13" width="4" height="5" rx="1" />
    </svg>
  );
}

function CurveIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <path d="M3 17c3-6 5-9 8-6s5 2 10-6" />
    </svg>
  );
}

/**
 * Monotone cubic path (Fritsch–Carlson) through the points: rounded corners
 * without the overshoot a plain spline would add above a peak or below a dip.
 */
function smoothPath(points: [number, number][]): string {
  const n = points.length;
  if (n === 0) return "";
  if (n < 3) return points.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`).join(" ");
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i += 1) {
    dx.push(points[i + 1][0] - points[i][0]);
    slope.push((points[i + 1][1] - points[i][1]) / (dx[i] || 1));
  }
  const tangent: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i += 1) {
    tangent.push(slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2);
  }
  tangent.push(slope[n - 2]);
  for (let i = 0; i < n - 1; i += 1) {
    if (slope[i] === 0) {
      tangent[i] = 0;
      tangent[i + 1] = 0;
      continue;
    }
    const a = tangent[i] / slope[i];
    const b = tangent[i + 1] / slope[i];
    const h = a * a + b * b;
    if (h > 9) {
      const t = 3 / Math.sqrt(h);
      tangent[i] = t * a * slope[i];
      tangent[i + 1] = t * b * slope[i];
    }
  }
  let d = `M${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i += 1) {
    const [x0, y0] = points[i];
    const [x1, y1] = points[i + 1];
    const third = dx[i] / 3;
    d += ` C${(x0 + third).toFixed(1)} ${(y0 + tangent[i] * third).toFixed(1)} ${(x1 - third).toFixed(1)} ${(y1 - tangent[i + 1] * third).toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  }
  return d;
}
