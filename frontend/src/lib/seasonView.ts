// Adapters: backend forecast / climatology / region-season → the panel view
// models (ForecastDay / MonthWind / RegionMonth). Return null / empty when the
// backend has no data (e.g. a spot without a derived climatology) so the page
// can hide the panel instead of inventing numbers.

import type { ForecastHour, ForecastSeries, RegionSeasonResponse } from "./api";
import type {
  DayBlock,
  DayBlocks,
  DayDetail,
  DayHours,
  DetailBlock,
  MonthWind,
  RegionMonth,
  WaterType,
} from "./types";

const WEEKDAYS = ["SO", "MO", "DI", "MI", "DO", "FR", "SA"]; // Date.getDay(): 0 = Sun
const MONTHS = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"];
const MONTHS_FULL = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

const monthOfWeek = (week: number) => Math.min(11, Math.max(0, Math.floor(((week - 1) / 52) * 12)));
const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

// Wind-speed bin lower edges (kt) of the climatology histogram — mirror of
// app/era5/bins.py WIND_SPEED_BINS_KT. Bins from STRONG_WIND_BIN up (>= 14 kt)
// count as "rideable" wind: enough to plane on a kite/board.
const WIND_SPEED_BINS_KT = [0, 6, 10, 14, 18, 25];
const STRONG_WIND_BIN = WIND_SPEED_BINS_KT.indexOf(14); // 3 → >= 14 kt

/** Climatology years from a "YYYY-YYYY" window string; 20 (the pipeline default)
 *  when it can't be parsed — only the absolute hours label depends on this, not
 *  the chart shape (the divisor is constant across weeks). */
function windowYears(window: unknown): number {
  const m = typeof window === "string" ? window.match(/(\d{4}).*?(\d{4})/) : null;
  if (m) {
    const n = Number(m[2]) - Number(m[1]) + 1;
    if (n > 0) return n;
  }
  return 20;
}

// Hour-of-day from an hourly forecast timestamp ("YYYY-MM-DDTHH:MM…").
// String slicing, not `new Date(...).getHours()` — the backend requests
// Open-Meteo with timezone=auto, so these strings are already the spot's
// local wall-clock time with no offset; parsing them as a Date would let the
// *browser's* timezone quietly reinterpret the hour.
const hourOf = (time: string) => Number(time.slice(11, 13));

// "2026-07-23" → "23.07." for the compact day-column/detail-graph headers.
function shortDate(dateStr: string): string {
  const dt = new Date(dateStr);
  if (Number.isNaN(dt.getTime())) return dateStr;
  const dd = String(dt.getDate()).padStart(2, "0");
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}.`;
}

const weekdayOf = (dateStr: string) => {
  const dt = new Date(dateStr);
  return Number.isNaN(dt.getTime()) ? dateStr.slice(5) : WEEKDAYS[dt.getDay()];
};

/** Hours of `day` whose local hour falls in `[start, end)`. */
function hoursInWindow(hours: ForecastHour[], start: number, end: number): ForecastHour[] {
  return hours.filter((h) => {
    const hr = hourOf(h.time);
    return hr >= start && hr < end;
  });
}

const windowLabel = (start: number, end: number) =>
  `${String(start).padStart(2, "0")}–${String(end).padStart(2, "0")}`;

// Ebene 1: 5 × 3h blocks, 06–21h.
const BLOCKS_L1: [number, number][] = [
  [6, 9],
  [9, 12],
  [12, 15],
  [15, 18],
  [18, 21],
];

/** 7-day forecast → the always-visible weekly overview (Ebene 1): one column
 *  per day, 5 three-hour blocks each. Each block shows its *best* hour (the
 *  highest average wind within it), not a block average — the point is "when
 *  today's peak window is", not a smoothed-over mean. Missing hours (null
 *  wind) are skipped; a block with no usable hour at all is null, not 0. */
export function forecastToBlocks(fc: ForecastSeries): DayBlocks[] {
  return fc.days.map((d) => {
    const blocks: DayBlock[] = BLOCKS_L1.map(([start, end]) => {
      let best: ForecastHour | null = null;
      for (const h of hoursInWindow(d.hours, start, end)) {
        if (h.wind == null) continue;
        if (best?.wind == null || h.wind > best.wind) best = h;
      }
      return { label: windowLabel(start, end), wind: best?.wind ?? null, dir: best?.dir ?? null };
    });

    const midday =
      d.hours.find((h) => hourOf(h.time) === 12 && h.dir != null) ??
      d.hours.find((h) => h.dir != null);
    const maxWind = blocks.reduce<number | null>(
      (m, b) => (b.wind == null ? m : m == null ? b.wind : Math.max(m, b.wind)),
      null
    );

    return {
      day: weekdayOf(d.date),
      date: shortDate(d.date),
      blocks,
      windDir: midday?.dir ?? null,
      maxWind,
    };
  });
}

// Ebene 2: 8 × 2h blocks, 06–22h.
const BLOCKS_L2: [number, number][] = [
  [6, 8],
  [8, 10],
  [10, 12],
  [12, 14],
  [14, 16],
  [16, 18],
  [18, 20],
  [20, 22],
];

const meanOf = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

/** 7-day forecast → the collapsible per-day detail graphs (Ebene 2): 8
 *  two-hour blocks, each an honest *average* wind (unlike Ebene 1's best-hour
 *  blocks — here the point is the realistic expectation for that window) plus
 *  the window's peak gust, for the gust curve. Direction is one representative
 *  hour's reading (a real bearing), never an arithmetic mean of angles. */
export function forecastToDetailBlocks(fc: ForecastSeries): DayDetail[] {
  return fc.days.map((d) => {
    const blocks: DetailBlock[] = BLOCKS_L2.map(([start, end]) => {
      const inWindow = hoursInWindow(d.hours, start, end);
      const winds = inWindow.map((h) => h.wind).filter((v): v is number => v != null);
      const gusts = inWindow.map((h) => h.gust).filter((v): v is number => v != null);
      const dir = inWindow.find((h) => h.dir != null)?.dir ?? null;
      const windAvg = meanOf(winds);
      return {
        label: windowLabel(start, end),
        windAvg: windAvg == null ? null : Math.round(windAvg * 10) / 10,
        gustMax: gusts.length ? Math.max(...gusts) : null,
        dir,
      };
    });

    const periods = d.hours.map((h) => h.period).filter((v): v is number => v != null);
    const wavePeriod = meanOf(periods);

    return {
      day: weekdayOf(d.date),
      date: shortDate(d.date),
      blocks,
      waveHeight: d.summary.swell_max ?? null,
      wavePeriod: wavePeriod == null ? null : Math.round(wavePeriod),
      airTemp: d.summary.air_max ?? null,
    };
  });
}

/** 7-day forecast → the Stundentabelle (Daten tab): every hour the forecast
 *  actually reports, unaggregated — one row per variable, one column per
 *  hour. Unlike `forecastToBlocks`/`forecastToDetailBlocks` this doesn't
 *  average or pick a "best" hour; a short/incomplete day (fewer hours than
 *  usual) just yields fewer columns, never a fabricated one. */
export function forecastToHourly(fc: ForecastSeries): DayHours[] {
  return fc.days.map((d) => ({
    day: weekdayOf(d.date),
    date: shortDate(d.date),
    isoDate: d.date,
    hours: d.hours.map((h) => ({
      time: h.time.slice(11, 16),
      hour: hourOf(h.time),
      wind: h.wind,
      gust: h.gust,
      dir: h.dir,
      waveHeight: h.swell,
      swellDir: h.swell_dir,
      period: h.period,
      air: h.air,
      water: h.sst,
      precip: h.precip,
    })),
  }));
}

export function waterTypeFromCharacter(wc?: string | null): WaterType {
  if (wc === "flach" || wc === "tiefes_wasser") return "flat";
  if (wc === "welle_klein" || wc === "welle_gross") return "swell";
  return "chop";
}

/** Spot climatology → monthly bars of *rideable wind hours per week*, or null.
 *
 * For each week we sum the histogram hours across all directions in the wind
 * bins ≥ 14 kt and divide by the number of climatology years, giving an average
 * "hours of rideable wind per week". This surfaces the **windy season** — unlike
 * the near-flat median wind, which barely moves month to month. Returns null when
 * a spot has no usable histogram (so the panel hides instead of inventing data).
 */
export function climatologyToMonths(clim: Record<string, any> | null | undefined): MonthWind[] | null {
  const weeks = clim?.weeks;
  if (!Array.isArray(weeks) || weeks.length === 0) return null;
  const years = windowYears(clim?.window);
  const buckets: number[][] = Array.from({ length: 12 }, () => []);
  for (const w of weeks) {
    const joint = w?.wind?.joint;
    if (!Array.isArray(joint)) continue;
    // Hours (all directions) in the rideable ≥ 14 kt speed bins, per year.
    const strongHours = joint.reduce(
      (sum: number, row: number[]) =>
        sum +
        (Array.isArray(row)
          ? row.slice(STRONG_WIND_BIN).reduce((a, b) => a + (Number(b) || 0), 0)
          : 0),
      0
    );
    buckets[monthOfWeek(w.week ?? 0)].push(Math.round((strongHours / years) * 10) / 10);
  }
  const out: MonthWind[] = MONTHS.map((month, i) => ({
    month,
    weeks: buckets[i].length ? buckets[i] : [0],
  }));
  return out.some((m) => m.weeks.some((v) => v > 0)) ? out : null;
}

/** The speed (kt) at percentile `p` of an hours-weighted histogram, given
 *  each bin's lower edge and hour count — linear interpolation within the bin
 *  the percentile falls in. The last bin is open-ended (≥ its lower edge), so
 *  it's extrapolated to the same width as the bin before it. `null` for an
 *  empty histogram (no hours at all). */
function percentileFromHistogram(binHours: number[], binEdges: number[], p: number): number | null {
  const total = binHours.reduce((a, b) => a + b, 0);
  if (total <= 0) return null;
  const target = (p / 100) * total;
  let cum = 0;
  for (let i = 0; i < binHours.length; i++) {
    const next = cum + binHours[i];
    if (next >= target || i === binHours.length - 1) {
      const lower = binEdges[i];
      const upper = i + 1 < binEdges.length ? binEdges[i + 1] : lower + (lower - (binEdges[i - 1] ?? 0));
      const withinBin = binHours[i] > 0 ? (target - cum) / binHours[i] : 0;
      return lower + Math.max(0, Math.min(1, withinBin)) * (upper - lower);
    }
    cum = next;
  }
  return binEdges[binEdges.length - 1];
}

/** Spot climatology → monthly bars of the **P`p` wind speed per week** (default
 *  use: P75, "how strong does it blow on the windy days"), or null.
 *
 * The mean wind barely moves across the year (the reason `climatologyToMonths`
 * exists at all) — but the upper-quartile speed does, and reads as a much more
 * legible season signal. Computed straight from the histogram (hours summed
 * across all direction sectors per speed bin, then the percentile speed
 * interpolated from that), not from the rideable-hours bins `climatologyToMonths`
 * uses. Returns null when there's no usable histogram.
 */
export function climatologyToPercentile(clim: Record<string, any> | null | undefined, p: number): MonthWind[] | null {
  const weeks = clim?.weeks;
  if (!Array.isArray(weeks) || weeks.length === 0) return null;
  const buckets: number[][] = Array.from({ length: 12 }, () => []);
  for (const w of weeks) {
    const joint = w?.wind?.joint;
    if (!Array.isArray(joint)) continue;
    // Hours per speed bin, summed across all direction sectors.
    const binHours = WIND_SPEED_BINS_KT.map((_, i) =>
      joint.reduce((sum: number, row: number[]) => sum + (Array.isArray(row) ? Number(row[i]) || 0 : 0), 0)
    );
    const value = percentileFromHistogram(binHours, WIND_SPEED_BINS_KT, p);
    if (value != null) buckets[monthOfWeek(w.week ?? 0)].push(Math.round(value * 10) / 10);
  }
  const out: MonthWind[] = MONTHS.map((month, i) => ({
    month,
    weeks: buckets[i].length ? buckets[i] : [0],
  }));
  return out.some((m) => m.weeks.some((v) => v > 0)) ? out : null;
}

/**
 * The best contiguous season window from a year of monthly wind bars — the
 * longest run of consecutive months whose mean is within `threshold` of the
 * year's peak, wrapping across the Dec→Jan boundary (a Nov–Mar season is one
 * contiguous run, not two). Returns null when the year is too flat to call a
 * "season" at all (peak and trough within 25% of each other) — an honest
 * "no highlight" beats a highlight drawn from noise.
 */
export function bestSeasonWindow(
  data: MonthWind[],
  threshold = 0.65
): { startMonth: string; endMonth: string; startIndex: number; endIndex: number } | null {
  if (data.length !== 12) return null;
  const means = data.map((m) => avg(m.weeks));
  const max = Math.max(...means);
  const min = Math.min(...means);
  if (max <= 0 || (max - min) / max < 0.25) return null;

  const inSeason = means.map((v) => v >= threshold * max);

  if (inSeason.every(Boolean)) {
    return { startIndex: 0, endIndex: 11, startMonth: MONTHS_FULL[0], endMonth: MONTHS_FULL[11] };
  }

  // Walk the circle starting right after a month that's NOT in season, so a
  // run that wraps Dec→Jan is counted as one contiguous stretch rather than
  // split across the array's start/end.
  const falseAt = inSeason.findIndex((v) => !v);
  let bestStart = -1;
  let bestLen = 0;
  let runStart = -1;
  let runLen = 0;
  for (let k = 0; k < 12; k++) {
    const i = (falseAt + 1 + k) % 12;
    if (inSeason[i]) {
      if (runLen === 0) runStart = i;
      runLen++;
      if (runLen > bestLen) {
        bestLen = runLen;
        bestStart = runStart;
      }
    } else {
      runLen = 0;
    }
  }
  if (bestStart === -1) return null;
  const endIndex = (bestStart + bestLen - 1) % 12;
  return {
    startIndex: bestStart,
    endIndex,
    startMonth: MONTHS_FULL[bestStart],
    endMonth: MONTHS_FULL[endIndex],
  };
}

/** Region season aggregate → monthly "spots working" bars + peak months, or null. */
export function regionSeasonToView(
  resp: RegionSeasonResponse,
  totalSpots: number
): { season: RegionMonth[]; bestMonths: string[] } | null {
  const weeks = resp.season?.weeks;
  if (!Array.isArray(weeks) || weeks.length === 0) return null;

  const working: number[][] = Array.from({ length: 12 }, () => []);
  const wind: number[][] = Array.from({ length: 12 }, () => []);
  for (const w of weeks) {
    const m = monthOfWeek(w.week);
    if (typeof w.spots_working === "number") working[m].push(w.spots_working);
    if (typeof w.wind_p50 === "number") wind[m].push(w.wind_p50);
  }

  const season: RegionMonth[] = MONTHS.map((month, i) => ({
    month,
    working: Math.round(avg(working[i])),
    total: totalSpots,
    wind: Math.round(avg(wind[i]) * 10) / 10,
  }));

  // No signal at all (spots without climatology) → hide the panel.
  if (!season.some((m) => m.working > 0 || m.wind > 0)) return null;

  const peak = Math.max(...season.map((m) => m.working));
  const bestMonths =
    peak > 0
      ? season.map((m, i) => ({ m, i })).filter(({ m }) => m.working >= peak).map(({ i }) => MONTHS_FULL[i])
      : [];
  return { season, bestMonths };
}
