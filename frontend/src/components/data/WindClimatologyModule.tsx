import { lazy, Suspense, useEffect, useId, useRef, useState, type RefObject } from "react";
import { useSearchParams } from "react-router-dom";
import type { WindClimatologyV3Read, WindClimatologyV3Week, WindDirectionMode } from "../../lib/api";
import { usePersistedState, useWindClimatologyV3, type WindClimatologyV3Selection } from "../../lib/hooks";
import type { Spot } from "../../lib/types";
import WindWindowSlider, { WIND_WINDOW_MAX, WIND_WINDOW_MIN, formatWindWindow } from "./WindWindowSlider";

const ClimatologyV2 = lazy(() => import("./Climatology"));

const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const DEFAULT_SELECTION: WindClimatologyV3Selection = { minWindKn: 15, maxWindKn: 20, directionMode: "all" };
const PRESETS: [string, number, number | null][] = [["10–15 kt", 10, 15], ["15–20 kt", 15, 20], ["20–30 kt", 20, 30], ["30+ kt", 30, null]];
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

export function formatMonthDayRange(startDate: string, endDate: string): string {
  const [startMonth, startDay] = startDate.split("-").map(Number);
  const [endMonth, endDay] = endDate.split("-").map(Number);
  if (startMonth === endMonth) return `${startDay}.–${endDay}. ${MONTHS[startMonth - 1]}`;
  return `${startDay}. ${MONTHS[startMonth - 1]} – ${endDay}. ${MONTHS[endMonth - 1]}`;
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

  const v3 = useWindClimatologyV3(spot.id, selection, true);

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
    />
  );
}

function V3Skeleton() {
  return (
    <div className="p-4" role="status" aria-label="Windzuverlässigkeit wird geladen">
      <div className="h-5 w-64 animate-pulse rounded bg-line" />
      <div className="mt-2 h-4 w-96 max-w-full animate-pulse rounded bg-line" />
      <div className="mt-6 flex h-40 items-end gap-1">
        {Array.from({ length: 52 }).map((_, i) => (
          <span key={i} className="flex-1 animate-pulse rounded-t bg-line-soft" style={{ height: `${20 + ((i * 37) % 60)}%` }} />
        ))}
      </div>
    </div>
  );
}

function V3ErrorState({ message }: { message: string }) {
  return (
    <div className="p-4" role="alert">
      <h3 className="font-display text-lg text-ink">Wann ist regelmäßig Wind?</h3>
      <p className="mt-2 text-sm text-muted">Die Windzuverlässigkeit konnte nicht geladen werden. {message}</p>
    </div>
  );
}

// --- main panel: header, controls, chart, detail, methodology --------------

function V3Panel({
  data, switching, selection, onSelectionChange,
}: {
  data: WindClimatologyV3Read;
  switching: boolean;
  selection: WindClimatologyV3Selection;
  onSelectionChange: (next: WindClimatologyV3Selection) => void;
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

  useEffect(() => {
    const el = scroller.current?.querySelector<HTMLElement>(`[data-week="${currentWeek}"]`);
    el?.scrollIntoView({ inline: "center", block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const week = data.weeks.find((w) => w.week === selectedWeek) ?? null;
  const monthGroups = groupByMonth(data.weeks);
  const directionSummary = data.direction.selected_mode === "usable" ? "passende Richtung" : "alle Richtungen";

  return (
    <div className="p-4">
      <div ref={liveRegionRef} aria-live="polite" className="sr-only" />

      <h3 className="font-display text-lg text-ink">Wann ist regelmäßig Wind?</h3>
      <p className="mt-1 text-sm text-muted">Historische Wahrscheinlichkeit für mindestens zwei Windtage mit jeweils drei zusammenhängenden brauchbaren Stunden.</p>
      {data.best_season ? (
        <p className="mt-1 text-sm font-medium text-orange">Beste Planungszeit: {formatMonthDayRange(data.best_season.start_date, data.best_season.end_date)}</p>
      ) : (
        <p className="mt-1 text-sm text-muted">Kein klarer verlässlicher Saisonzeitraum erkennbar.</p>
      )}

      <p className="mt-3 text-data-value text-ink-soft">
        {formatWindWindow(data.selection.min_wind_kn, data.selection.max_wind_kn)} · {directionSummary} · {data.period[0]}–{data.period[1]}
      </p>

      <div className="mt-4">
        <span className="text-data-label font-medium uppercase tracking-wider text-muted">Windfenster</span>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {PRESETS.map(([label, min, max]) => (
            <button
              key={label}
              type="button"
              onClick={() => onSelectionChange({ ...selection, minWindKn: min, maxWindKn: max })}
              aria-pressed={selection.minWindKn === min && selection.maxWindKn === max}
              className={`min-h-[44px] rounded-full border px-3 py-1 text-label ${selection.minWindKn === min && selection.maxWindKn === max ? "border-teal bg-teal text-white" : "border-line text-muted hover:border-line-soft"}`}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            aria-expanded={customOpen}
            aria-controls={customControlsId}
            onClick={() => setCustomOpen((open) => !open)}
            className="ml-1 min-h-[44px] rounded-full border border-line px-3 py-1 text-label text-muted hover:border-line-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
          >
            Anpassen {customOpen ? "▴" : "▾"}
          </button>
        </div>

        {customOpen && (
          <div id={customControlsId} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-[1fr_auto]">
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
          </div>
        )}
      </div>

      <div className={`mt-6 transition-opacity ${switching ? "opacity-60" : ""}`}>
        <WeekChart weeks={data.weeks} monthGroups={monthGroups} currentWeek={currentWeek} selectedWeek={selectedWeek} onSelect={setSelectedWeek} scrollerRef={scroller} />
        {switching && <p className="mt-1 text-data-caption text-muted">Aktualisiere Auswahl …</p>}
      </div>

      {week && <WeekDetail week={week} selection={data.selection} />}

      <p className="mt-4 text-data-caption leading-relaxed text-muted">
        Historische Orientierung, keine Vorhersage. ERA5 · 10-Meter-Wind · {data.period[0]}–{data.period[1]} · Tageslichtstunden · Drei-Stunden-Sessionregel · erfolgreiche Woche = mindestens zwei brauchbare Windtage · ca. {data.grid_resolution_degrees}° Raster · {data.updated_at ? new Date(data.updated_at).toLocaleDateString("de-DE") : "–"} · {data.attribution}
        <br />
        Lokale Thermik, Gelände und kleinräumige Effekte können vom ERA5-Raster abweichen. {data.direction.selected_mode === "usable" ? "Es zählen nur die für diesen Spot freigegebenen Windrichtungen." : "Die Windrichtung ist in dieser Ansicht nicht eingeschränkt."}
      </p>
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
  return (
    <div>
      <div className="flex text-data-caption text-muted">
        <span>100 %</span>
        <span className="ml-auto">Chance auf mindestens zwei brauchbare Windtage</span>
      </div>
      <div ref={scrollerRef} className="mt-1 flex gap-px overflow-x-auto pb-2" role="group" aria-label="52 Wochen Windzuverlässigkeit, Januar bis Dezember">
        {monthGroups.map((group, monthIndex) => (
          <div key={monthIndex} className="flex shrink-0 flex-col border-r border-line-soft pr-px last:border-r-0">
            <div className="flex h-40 items-end gap-px">
              {group.map((week) => (
                <WeekBar key={week.week} week={week} isCurrent={week.week === currentWeek} isSelected={week.week === selectedWeek} onSelect={onSelect} />
              ))}
            </div>
            <p className="mt-1 w-full text-center text-data-caption uppercase tracking-wider text-muted">{MONTHS[monthIndex].slice(0, 3)}</p>
          </div>
        ))}
      </div>
      <div className="flex justify-between text-data-caption text-muted">
        <span>0 %</span><span>25 %</span><span>50 %</span><span>75 %</span><span>100 %</span>
      </div>
    </div>
  );
}

export function WeekBar({ week, isCurrent, isSelected, onSelect }: { week: WindClimatologyV3Week; isCurrent: boolean; isSelected: boolean; onSelect: (week: number) => void }) {
  const missing = week.reliability_percent == null;
  const height = missing ? 0 : week.reliability_percent!;
  const band = reliabilityBand(week.reliability_percent);
  const dateLabel = formatDateRange(week);
  const label = missing
    ? `${dateLabel}: keine ausreichende Datenbasis (${week.sample_years} Jahre)`
    : `${dateLabel}: ${week.reliability_percent}% Zuverlässigkeit, ${week.successful_years} von ${week.sample_years} Jahren erfolgreich`;

  return (
    <button
      type="button"
      data-week={week.week}
      onClick={() => onSelect(week.week)}
      aria-pressed={isSelected}
      title={label}
      aria-label={label}
      className={`group relative flex h-full w-[10px] min-w-[10px] items-end justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-teal sm:w-3 ${isSelected ? "ring-2 ring-teal ring-offset-1" : ""}`}
    >
      {isCurrent && <span aria-hidden="true" className="absolute -top-1 h-1 w-1 rounded-full bg-orange" />}
      {missing ? (
        <span aria-hidden="true" className="mb-0.5 h-[2px] w-full rounded bg-line" />
      ) : (
        <span aria-hidden="true" className={`w-full rounded-t transition-opacity group-hover:opacity-80 ${BAND_CLASSES[band]}`} style={{ height: `${height}%` }} />
      )}
    </button>
  );
}

// --- detail panel below the chart -------------------------------------

export function WeekDetail({ week, selection }: { week: WindClimatologyV3Week; selection: WindClimatologyV3Read["selection"] }) {
  const rows: [string, string][] = [
    ["Zeitraum", formatDateRange(week)],
    ["Zuverlässigkeit", week.reliability_percent == null ? "keine ausreichende Datenbasis" : `${week.reliability_percent}%`],
    ["Gültige Jahre", String(week.sample_years)],
    ["Erfolgreiche Jahre", String(week.successful_years)],
    ["Median brauchbare Windtage", week.median_usable_days == null ? "–" : String(week.median_usable_days)],
    ["Median Sessionstunden", week.median_session_hours == null ? "–" : `${week.median_session_hours} h`],
    ["Typische Spanne (25.–75. Perzentil)", week.p25_session_hours == null || week.p75_session_hours == null ? "–" : `${week.p25_session_hours}–${week.p75_session_hours} h`],
    ["Median längste Session", week.median_longest_session == null ? "–" : `${week.median_longest_session} h`],
    ["Mind. 1 Windtag", week.probability_at_least_1_day == null ? "–" : `${week.probability_at_least_1_day}%`],
    ["Mind. 2 Windtage", week.probability_at_least_2_days == null ? "–" : `${week.probability_at_least_2_days}%`],
    ["Mind. 3 Windtage", week.probability_at_least_3_days == null ? "–" : `${week.probability_at_least_3_days}%`],
    ["Windfenster", formatWindWindow(selection.min_wind_kn, selection.max_wind_kn)],
    ["Richtungsmodus", selection.direction_mode === "usable" ? "passende Richtung" : "alle Richtungen"],
    ["Datenqualität", { high: "hoch", limited: "eingeschränkt", insufficient: "unzureichend" }[week.quality_status]],
  ];
  return (
    <div className="mt-4 rounded-lg border border-line-soft bg-band p-4">
      <h4 className="text-data-label font-medium uppercase tracking-wider text-muted">Wochendetail</h4>
      <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3 border-b border-line-soft/60 py-1 text-data-value">
            <dt className="text-ink-soft">{label}</dt>
            <dd className="text-right font-medium text-ink">{value}</dd>
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
