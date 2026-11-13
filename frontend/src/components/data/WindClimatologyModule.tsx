import { lazy, Suspense, useEffect, useId, useRef, useState, type RefObject } from "react";
import { useSearchParams } from "react-router-dom";
import type { WindClimatologyV3Read, WindClimatologyV3Week, WindDirectionMode } from "../../lib/api";
import { usePersistedState, useWindClimatologyV3, type WindClimatologyV3Selection } from "../../lib/hooks";
import type { Spot } from "../../lib/types";
import { formatMonthDayRange } from "../../lib/bestSeason";
import { ChevronDownIcon } from "../../lib/icons";
import WindWindowSlider, { WIND_WINDOW_MAX, WIND_WINDOW_MIN, formatWindWindow } from "./WindWindowSlider";
import YearRangeSlider from "./YearRangeSlider";

type YearWindow = { fromYear: number; toYear: number };

const ClimatologyV2 = lazy(() => import("./Climatology"));

const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const DEFAULT_SELECTION: WindClimatologyV3Selection = { minWindKn: 15, maxWindKn: 20, directionMode: "all" };
const PRESETS: [string, number, number | null][] = [["10–15 kn", 10, 15], ["15–20 kn", 15, 20], ["20–30 kn", 20, 30], ["30+ kn", 30, null]];
const STORAGE_KEY = "swd.wind-climatology-v3-selection.v1";

// --- selection parsing / URL + storage priority ----------------------------

function parseIntParam(value: string | null): number | null {
  if (value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n) : null;
}

export function selectionFromUrl(params: URLSearchParams): Partial<WindClimatologyV3Selection> {
  const result: Partial<WindClimatologyV3Selection> = {};
  const min = parseIntParam(params.get("wind_min"));
  if (min != null && min >= WIND_WINDOW_MIN && min < WIND_WINDOW_MAX) result.minWindKn = min;
  const maxRaw = params.get("wind_max");
  if (maxRaw === "plus") result.maxWindKn = null;
  else {
    const max = parseIntParam(maxRaw);
    if (max != null && max > WIND_WINDOW_MIN && max <= WIND_WINDOW_MAX) result.maxWindKn = max;
  }
  const dir = params.get("wind_dir");
  if (dir === "all" || dir === "usable") result.directionMode = dir;
  return result;
}

export function normalizeSelection(raw: Partial<WindClimatologyV3Selection>): WindClimatologyV3Selection {
  let minWindKn = Math.round(raw.minWindKn ?? DEFAULT_SELECTION.minWindKn);
  minWindKn = Math.min(Math.max(minWindKn, WIND_WINDOW_MIN), WIND_WINDOW_MAX - 1);
  let maxWindKn = raw.maxWindKn === undefined ? DEFAULT_SELECTION.maxWindKn : raw.maxWindKn;
  if (maxWindKn != null) {
    maxWindKn = Math.round(maxWindKn);
    maxWindKn = Math.min(Math.max(maxWindKn, minWindKn + 1), WIND_WINDOW_MAX);
    if (maxWindKn >= WIND_WINDOW_MAX) maxWindKn = null;
  }
  const directionMode: WindDirectionMode = raw.directionMode === "usable" ? "usable" : "all";
  return { minWindKn, maxWindKn, directionMode };
}

function selectionsEqual(a: WindClimatologyV3Selection, b: WindClimatologyV3Selection): boolean {
  return a.minWindKn === b.minWindKn && a.maxWindKn === b.maxWindKn && a.directionMode === b.directionMode;
}

// Mirrors app.wind_climatology.v3_time: month/day mapped onto a fixed
// leap-year (2000) template, then floor(p*52/366)+1 — the one canonical
// 52-week calendar. Client-side only to highlight "today" in the chart; the
// server is the sole source of the weekly reliability values themselves.
export function seasonalWeekForToday(): number {
  const now = new Date();
  const templateStart = Date.UTC(2000, 0, 1);
  const templateDay = Date.UTC(2000, now.getMonth(), now.getDate());
  const p = Math.round((templateDay - templateStart) / 86_400_000);
  return Math.min(52, Math.floor((p * 52) / 366) + 1);
}

export function reliabilityBand(percent: number | null): 0 | 1 | 2 | 3 {
  if (percent == null || percent < 30) return 0;
  if (percent < 50) return 1;
  if (percent < 70) return 2;
  return 3;
}

const BAND_CLASSES = ["bg-reliability-0", "bg-reliability-1", "bg-reliability-2", "bg-reliability-3"];

function monthOf(week: WindClimatologyV3Week): number {
  return Number(week.date_range.start.slice(0, 2));
}

export function groupByMonth(weeks: WindClimatologyV3Week[]): WindClimatologyV3Week[][] {
  const groups: WindClimatologyV3Week[][] = Array.from({ length: 12 }, () => []);
  for (const week of weeks) groups[monthOf(week) - 1].push(week);
  return groups;
}

function formatDateRange(week: WindClimatologyV3Week): string {
  return formatMonthDayRange(week.date_range.start, week.date_range.end);
}

// --- root: decides V3 vs. V2, owns URL/storage selection state -------------

export default function WindClimatologyModule({ spot }: { spot: Spot }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [stored, setStored] = usePersistedState<Partial<WindClimatologyV3Selection>>(STORAGE_KEY, {});
  const directionExplicitRef = useRef(selectionFromUrl(searchParams).directionMode != null);

  const [selection, setSelection] = useState<WindClimatologyV3Selection>(() =>
    normalizeSelection({ ...stored, ...selectionFromUrl(searchParams) }),
  );
  const [yearWindow, setYearWindow] = useState<{ fromYear: number; toYear: number } | null>(null);

  const v3 = useWindClimatologyV3(spot.id, selection, true, yearWindow);

  // Default to the spot's usable-direction filter once we learn it exists,
  // unless the user (or an explicit URL) already made a direction choice.
  useEffect(() => {
    if (directionExplicitRef.current) return;
    if (v3.data?.direction.usable_available && selection.directionMode === "all") {
      directionExplicitRef.current = true;
      setSelection((s) => ({ ...s, directionMode: "usable" }));
    }
  }, [v3.data, selection.directionMode]);

  // A stale/foreign "usable" selection (e.g. a shared link for a spot without
  // reviewed directions) 422s — recover to "all" instead of stalling on it.
  useEffect(() => {
    if (!v3.ready && !v3.notFound && v3.error && selection.directionMode === "usable") {
      setSelection((s) => ({ ...s, directionMode: "all" }));
    }
  }, [v3.error, v3.ready, v3.notFound, selection.directionMode]);

  // Reflect the settled selection in the URL (replace, no history spam while
  // dragging the slider — the hook itself already debounces the fetch) and in
  // the spot-agnostic browser default for next time.
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    next.set("wind_min", String(selection.minWindKn));
    next.set("wind_max", selection.maxWindKn == null ? "plus" : String(selection.maxWindKn));
    next.set("wind_dir", selection.directionMode);
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
    setStored((current) => (selectionsEqual(normalizeSelection(current), selection) ? current : selection));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection.minWindKn, selection.maxWindKn, selection.directionMode]);

  if (v3.notFound) return <Suspense fallback={<div className="h-40 animate-pulse bg-band" role="status" aria-label="Datenansicht wird geladen" />}><ClimatologyV2 spot={spot} /></Suspense>;

  if (!v3.ready && !v3.data) {
    if (v3.error) return <V3ErrorState message={v3.error} />;
    return <V3Skeleton />;
  }

  return (
    <V3Panel
      data={v3.data!}
      switching={v3.switching}
      selection={selection}
      onSelectionChange={(next) => {
        directionExplicitRef.current = true;
        setSelection(normalizeSelection(next));
      }}
      yearWindow={yearWindow}
      onYearWindowChange={setYearWindow}
    />
  );
}

function V3Skeleton() {
  return (
    <div className="py-2" role="status" aria-label="Windzuverlässigkeit wird geladen">
      <div className="h-5 w-36 animate-pulse rounded bg-line" />
      <div className="mt-4 flex h-28 items-end gap-1">
        {Array.from({ length: 52 }).map((_, i) => (
          <span key={i} className="flex-1 animate-pulse rounded-t bg-line-soft" style={{ height: `${20 + ((i * 37) % 60)}%` }} />
        ))}
      </div>
    </div>
  );
}

function V3ErrorState({ message }: { message: string }) {
  return (
    <div className="py-2" role="alert">
      <h3 className="text-lg font-semibold text-ink">Windmonate</h3>
      <p className="mt-2 text-sm text-muted">Die Windzuverlässigkeit konnte nicht geladen werden. {message}</p>
    </div>
  );
}

// --- main panel: header, controls, chart, detail, methodology --------------

function V3Panel({
  data, switching, selection, onSelectionChange, yearWindow, onYearWindowChange,
}: {
  data: WindClimatologyV3Read;
  switching: boolean;
  selection: WindClimatologyV3Selection;
  onSelectionChange: (next: WindClimatologyV3Selection) => void;
  yearWindow: YearWindow | null;
  onYearWindowChange: (next: YearWindow | null) => void;
}) {
  const currentWeek = seasonalWeekForToday();
  const [selectedWeek, setSelectedWeek] = useState<number>(currentWeek);
  const liveRegionRef = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const isPreset = PRESETS.some(([, min, max]) => min === selection.minWindKn && max === selection.maxWindKn);
  // Custom controls (slider + direction filter) start collapsed once a preset
  // is active — presets are the primary path. A non-preset selection (e.g.
  // from a shared link) opens them so the active value stays visible.
  const [customOpen, setCustomOpen] = useState(!isPreset);
  const customControlsId = useId();

  // Announce completed variant switches only — not every slider tick.
  useEffect(() => {
    if (!switching && liveRegionRef.current) {
      liveRegionRef.current.textContent = `${formatWindWindow(data.selection.min_wind_kn, data.selection.max_wind_kn)}, ${data.direction.selected_mode === "usable" ? "passende Richtung" : "alle Richtungen"} geladen.`;
    }
  }, [data, switching]);

  const week = data.weeks.find((w) => w.week === selectedWeek) ?? null;
  const monthGroups = groupByMonth(data.weeks);
  const directionSummary = data.direction.selected_mode === "usable" ? "passende Richtung" : "alle Richtungen";

  // Year-range window: only the start year moves; the end is always the present.
  // Re-aggregated server-side from stored per-year data.
  const availableYears = data.available_years ?? null;
  const fromYear = availableYears
    ? Math.max(availableYears.min, Math.min(yearWindow?.fromYear ?? availableYears.min, availableYears.max))
    : null;
  const onYearChange = (nextFrom: number) =>
    onYearWindowChange(availableYears && nextFrom > availableYears.min ? { fromYear: nextFrom, toYear: availableYears.max } : null);

  return (
    <div className="py-2">
      <div ref={liveRegionRef} aria-live="polite" className="sr-only" />

      <div className="flex flex-wrap items-baseline justify-between gap-x-5 gap-y-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="text-lg font-semibold text-ink">Windmonate</h3>
          {data.best_season && (
            <p className="text-sm font-medium text-orange">
              Beste Zeit: {formatMonthDayRange(data.best_season.start_date, data.best_season.end_date)}
            </p>
          )}
        </div>
        <p className="text-data-caption tabular-nums text-muted">
          {formatWindWindow(data.selection.min_wind_kn, data.selection.max_wind_kn)} · {directionSummary} · {data.period[0]}–{data.period[1]}
        </p>
      </div>

      <div className="mt-3">
        <div className="flex flex-wrap items-center gap-2" aria-label="Windfenster">
          {PRESETS.map(([label, min, max]) => (
            <button
              key={label}
              type="button"
              onClick={() => onSelectionChange({ ...selection, minWindKn: min, maxWindKn: max })}
              aria-pressed={selection.minWindKn === min && selection.maxWindKn === max}
              className={`min-h-11 rounded-full border px-3 py-1 text-label ${selection.minWindKn === min && selection.maxWindKn === max ? "border-teal bg-teal text-white" : "border-line text-muted hover:border-line-soft"}`}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            aria-expanded={customOpen}
            aria-controls={customControlsId}
            onClick={() => setCustomOpen((open) => !open)}
            className="inline-flex min-h-11 items-center gap-1 rounded-full border border-line px-3 py-1 text-label text-muted hover:border-line-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
          >
            Anpassen
            <ChevronDownIcon className={`transition-transform ${customOpen ? "rotate-180" : ""}`} width={14} height={14} />
          </button>
        </div>

        {customOpen && (
          <div id={customControlsId} className="mt-3 grid grid-cols-1 gap-4 border-t border-line-soft pt-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <span className="text-data-label font-medium uppercase tracking-wider text-muted">Genaues Fenster</span>
              <div className="mt-2 max-w-md">
                <WindWindowSlider
                  minWindKn={selection.minWindKn}
                  maxWindKn={selection.maxWindKn}
                  onChange={(minWindKn, maxWindKn) => onSelectionChange({ ...selection, minWindKn, maxWindKn })}
                />
              </div>
            </div>

            <div className="sm:min-w-[220px]">
              <span className="text-data-label font-medium uppercase tracking-wider text-muted">Windrichtung</span>
              <label className="mt-2 flex min-h-[44px] items-center gap-2 text-data-value text-ink-soft">
                <input
                  type="checkbox"
                  checked={data.direction.selected_mode === "usable"}
                  disabled={!data.direction.usable_available}
                  onChange={(e) => onSelectionChange({ ...selection, directionMode: e.target.checked ? "usable" : "all" })}
                  className="h-4 w-4"
                />
                Passende Windrichtung berücksichtigen
              </label>
              {data.direction.usable_available ? (
                <p className="mt-1 text-data-caption text-muted">Freigegeben: {data.direction.description}</p>
              ) : (
                <p className="mt-1 text-data-caption text-muted">Für diesen Spot sind noch keine geprüften Windrichtungen hinterlegt.</p>
              )}
            </div>
            {availableYears && fromYear != null && availableYears.max > availableYears.min && (
              <div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-data-label font-medium uppercase tracking-wider text-muted">Zeitraum</span>
                  <span className="text-data-value tabular-nums text-ink">{fromYear}–{availableYears.max}</span>
                </div>
                <div className="mt-2">
                  <YearRangeSlider fromYear={fromYear} min={availableYears.min} max={availableYears.max} onChange={onYearChange} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className={`mt-4 transition-opacity ${switching ? "opacity-60" : ""}`}>
        <WeekChart weeks={data.weeks} monthGroups={monthGroups} currentWeek={currentWeek} selectedWeek={selectedWeek} onSelect={setSelectedWeek} scrollerRef={scroller} />
        {switching && <p className="mt-1 text-data-caption text-muted">Aktualisiere Auswahl …</p>}
      </div>

      {week && <WeekDetail week={week} />}

      <details className="mt-3 border-t border-line-soft pt-2 text-data-caption text-muted">
        <summary className="min-h-11 cursor-pointer py-3 font-medium text-ink-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal">
          Methodik und Datenquelle
        </summary>
        <p className="max-w-measure pb-2 leading-relaxed">
          Historische Orientierung, keine Vorhersage. ERA5 · 10-Meter-Wind · {data.period[0]}–{data.period[1]} · Tageslichtstunden · Drei-Stunden-Sessionregel · erfolgreiche Woche = mindestens zwei brauchbare Windtage · ca. {data.grid_resolution_degrees}° Raster · {data.updated_at ? new Date(data.updated_at).toLocaleDateString("de-DE") : "–"} · {data.attribution}. Lokale Thermik, Gelände und kleinräumige Effekte können abweichen. {data.direction.selected_mode === "usable" ? "Es zählen nur die für diesen Spot freigegebenen Windrichtungen." : "Die Windrichtung ist nicht eingeschränkt."}
        </p>
      </details>
    </div>
  );
}

// --- 52-week chart -----------------------------------------------------

export function WeekChart({
  weeks, monthGroups, currentWeek, selectedWeek, onSelect, scrollerRef,
}: {
  weeks: WindClimatologyV3Week[];
  monthGroups: WindClimatologyV3Week[][];
  currentWeek: number;
  selectedWeek: number;
  onSelect: (week: number) => void;
  scrollerRef: RefObject<HTMLDivElement>;
}) {
  if (weeks.length !== 52) {
    return <p role="alert" className="text-sm text-muted">Unerwartete Anzahl Wochen ({weeks.length}) — Darstellung übersprungen.</p>;
  }
  const selectedIndex = Math.max(0, weeks.findIndex((week) => week.week === selectedWeek));
  const selected = weeks[selectedIndex];
  const selectedLabel = selected.reliability_percent == null
    ? `${formatDateRange(selected)}: keine ausreichende Datenbasis`
    : `${formatDateRange(selected)}: ${selected.reliability_percent}% Zuverlässigkeit`;

  const selectIndex = (index: number) => {
    const bounded = Math.min(weeks.length - 1, Math.max(0, index));
    onSelect(weeks[bounded].week);
  };

  return (
    <div>
      <div className="flex justify-end text-data-caption text-muted">
        <span>Chance auf mindestens zwei brauchbare Windtage</span>
      </div>
      <div className="mt-2 flex gap-2">
        <div aria-hidden="true" className="flex h-28 w-8 shrink-0 flex-col justify-between text-right text-data-caption leading-none text-muted">
          {[100, 50, 0].map((value) => <span key={value}>{value}%</span>)}
        </div>
        {/* Horizontal scroller: on phones the 52 weekly bars keep a real minimum
            width so each week is legible and the track scrolls month-to-month;
            from lg the track fits the column and no longer scrolls. The click
            math reads from the track element's own rect, so it stays correct
            while scrolled. */}
        <div ref={scrollerRef} className="min-w-0 flex-1 overflow-x-auto [scrollbar-width:thin] lg:overflow-visible">
          <div className="min-w-[680px] lg:min-w-0">
            <div
              role="slider"
              tabIndex={0}
              aria-label="52 Wochen Windzuverlässigkeit, Januar bis Dezember"
              aria-valuemin={1}
              aria-valuemax={52}
              aria-valuenow={selected.week}
              aria-valuetext={selectedLabel}
              className="relative h-28 cursor-crosshair border-b border-line focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
              onKeyDown={(event) => {
                if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
                  event.preventDefault();
                  selectIndex(selectedIndex - 1);
                } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
                  event.preventDefault();
                  selectIndex(selectedIndex + 1);
                } else if (event.key === "Home") {
                  event.preventDefault();
                  selectIndex(0);
                } else if (event.key === "End") {
                  event.preventDefault();
                  selectIndex(weeks.length - 1);
                }
              }}
              onClick={(event) => {
                const bounds = event.currentTarget.getBoundingClientRect();
                if (bounds.width <= 0) return;
                const position = Math.min(0.999999, Math.max(0, (event.clientX - bounds.left) / bounds.width));
                selectIndex(Math.floor(position * weeks.length));
              }}
            >
              {[25, 50, 75].map((value) => (
                <span key={value} aria-hidden="true" className="pointer-events-none absolute inset-x-0 z-0 border-t border-dashed border-line-soft" style={{ bottom: `${value}%` }} />
              ))}
              {/* Month groups: filled bars with a small gap, but no vertical
                  separator stroke between months (removed on request). */}
              <div aria-hidden="true" className="relative z-10 flex h-full items-end">
                {monthGroups.map((group, monthIndex) => (
                  <div
                    key={monthIndex}
                    className="flex h-full min-w-0 items-end gap-px pr-px last:pr-0"
                    style={{ flexBasis: 0, flexGrow: group.length }}
                  >
                    {group.map((week) => (
                      <WeekBar key={week.week} week={week} isCurrent={week.week === currentWeek} isSelected={week.week === selectedWeek} />
                    ))}
                  </div>
                ))}
              </div>
            </div>
            <div aria-hidden="true" className="mt-1 flex">
              {monthGroups.map((group, monthIndex) => (
                <span
                  key={MONTHS[monthIndex]}
                  className="min-w-0 text-center text-sz-10 uppercase leading-tight text-muted sm:text-data-caption sm:tracking-wider"
                  style={{ flexBasis: 0, flexGrow: group.length }}
                >
                  {MONTHS[monthIndex].slice(0, 3)}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-data-caption text-muted" aria-label="Legende Windzuverlässigkeit">
        {[
          ["bg-reliability-0", "0–29 %"],
          ["bg-reliability-1", "30–49 %"],
          ["bg-reliability-2", "50–69 %"],
          ["bg-reliability-3", "70–100 %"],
        ].map(([tone, label]) => (
          <span key={label} className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-sm ${tone}`} />
            {label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 border-t border-dashed border-muted" />
          Keine Daten
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-orange" />
          Aktuelle Woche
        </span>
      </div>
    </div>
  );
}

export function WeekBar({ week, isCurrent, isSelected }: { week: WindClimatologyV3Week; isCurrent: boolean; isSelected: boolean }) {
  const missing = week.reliability_percent == null;
  const height = missing ? 0 : week.reliability_percent!;
  const band = reliabilityBand(week.reliability_percent);
  const dateLabel = formatDateRange(week);
  const label = missing
    ? `${dateLabel}: keine ausreichende Datenbasis (${week.sample_years} Jahre)`
    : `${dateLabel}: ${week.reliability_percent}% Zuverlässigkeit, ${week.successful_years} von ${week.sample_years} Jahren erfolgreich`;

  return (
    <span
      data-week={week.week}
      title={label}
      className={`relative flex h-full min-w-0 flex-1 items-end justify-center ${isSelected ? "ring-2 ring-inset ring-teal" : ""}`}
    >
      {isCurrent && <span aria-hidden="true" className="absolute -top-1 h-1 w-1 rounded-full bg-orange" />}
      {missing ? (
        <span aria-hidden="true" className="mb-0.5 w-full border-t border-dashed border-muted" />
      ) : height === 0 ? (
        <span aria-hidden="true" className="mb-0.5 h-[2px] w-full rounded bg-reliability-0" />
      ) : (
        <span aria-hidden="true" className={`w-full rounded-t ${BAND_CLASSES[band]}`} style={{ height: `${height}%` }} />
      )}
    </span>
  );
}

// --- detail panel below the chart -------------------------------------

export function WeekDetail({ week }: { week: WindClimatologyV3Week }) {
  const rows: [string, string][] = [
    ["Zeitraum", formatDateRange(week)],
    ["Zuverlässigkeit", week.reliability_percent == null ? "keine ausreichende Datenbasis" : `${week.reliability_percent}%`],
    ["Windtage", week.median_usable_days == null ? "–" : `${week.median_usable_days} im Median`],
    ["Sessionstunden", week.median_session_hours == null ? "–" : `${week.median_session_hours} h im Median`],
    ["Datenbasis", `${week.successful_years}/${week.sample_years} erfolgreiche Jahre`],
  ];
  return (
    <div className="mt-3 border-t border-line-soft pt-3">
      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-5">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-data-caption text-muted">{label}</dt>
            <dd className="mt-0.5 break-words text-data-value font-medium tabular-nums text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      {week.quality_status !== "high" && (
        <p className="mt-2 text-data-caption text-muted">
          {week.quality_status === "insufficient" ? "Zu wenige vollständige Jahre für eine belastbare Aussage." : "Eingeschränkte Datenqualität — Werte mit Vorsicht interpretieren."}
        </p>
      )}
    </div>
  );
}
