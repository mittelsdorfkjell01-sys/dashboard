// The landing search's value model + how it maps onto the backend search APIs.

export type WhenValue =
  // Explicit calendar range (left side of the "Wann?" panel).
  | { mode: "range"; from: string; to?: string } // yyyy-mm-dd
  // Flexible: pick a month without committing to exact dates.
  | { mode: "flex"; month: number } // month 1..12
  // Explicitly open ("egal wann" / ganze Saison) — the open time axis.
  | { mode: "open" }
  | null;

export interface WhereSelection {
  label: string;
  kind: "spot" | "region";
  id?: string;
}

export interface SearchValue {
  whereText: string;
  whereSel: WhereSelection | null;
  whereOpen: boolean; // explicitly "egal wo" / überall — the open place axis
  when: WhenValue;
  which: string[]; // single selected backend sport; array retained for draft compatibility
}

export const EMPTY_SEARCH: SearchValue = {
  whereText: "",
  whereSel: null,
  whereOpen: false,
  when: null,
  which: [],
};

const SEARCH_DRAFT_KEY = "swd.search-draft.v1";

function sessionStore(): Pick<Storage, "getItem" | "setItem" | "removeItem"> | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function loadSearchDraft(
  storage: Pick<Storage, "getItem"> | null = sessionStore(),
): SearchValue {
  if (!storage) return EMPTY_SEARCH;
  try {
    const parsed = JSON.parse(storage.getItem(SEARCH_DRAFT_KEY) ?? "null") as Partial<SearchValue> | null;
    if (!parsed || typeof parsed.whereText !== "string" || !Array.isArray(parsed.which)) return EMPTY_SEARCH;
    const when = parsed.when?.mode === "flex" && !parsed.when.month
      ? null
      : parsed.when ?? null;
    return { ...EMPTY_SEARCH, ...parsed, which: parsed.which.slice(0, 1), when };
  } catch {
    return EMPTY_SEARCH;
  }
}

export function saveSearchDraft(
  value: SearchValue | null,
  storage: Pick<Storage, "setItem" | "removeItem"> | null = sessionStore(),
): void {
  if (!storage) return;
  try {
    if (value) storage.setItem(SEARCH_DRAFT_KEY, JSON.stringify(value));
    else storage.removeItem(SEARCH_DRAFT_KEY);
  } catch {
    /* Private browsing or quota: the current search still works. */
  }
}

/** Whether the place axis is left open ("egal wo" / no concrete place). */
export function isPlaceOpen(v: SearchValue): boolean {
  return v.whereOpen || (!v.whereSel && !v.whereText.trim());
}

/** Whether the time axis is left open (no concrete week). */
export function isTimeOpen(v: SearchValue): boolean {
  return weekFromWhen(v.when) == null;
}

/** ISO-8601 week number (1..53) for a date. */
export function isoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = (d.getUTCDay() + 6) % 7; // Mon=0 … Sun=6
  d.setUTCDate(d.getUTCDate() - dayNum + 3); // Thursday of this ISO week
  const firstThursday = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);
  return 1 + Math.round((d.getTime() - firstThursday.getTime()) / (7 * 24 * 3600 * 1000));
}

type CalendarDate = { year: number; month: number; day: number };

function parseCalendarDate(iso: string): CalendarDate | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (
    candidate.getUTCFullYear() !== year
    || candidate.getUTCMonth() !== month - 1
    || candidate.getUTCDate() !== day
  ) return null;
  return { year, month, day };
}

function isoWeekFromCalendarDate(iso: string): number | undefined {
  const value = parseCalendarDate(iso);
  if (!value) return undefined;
  return isoWeek(new Date(value.year, value.month - 1, value.day));
}

/** Representative week for a month (its 15th) — used when only a month is chosen. */
export function weekOfMonth(month1to12: number, year = new Date().getFullYear()): number {
  return isoWeek(new Date(year, month1to12 - 1, 15));
}

export function weekFromWhen(when: WhenValue): number | undefined {
  if (!when) return undefined;
  if (when.mode === "flex") return when.month ? weekOfMonth(when.month) : undefined;
  if (when.mode === "range" && when.from) return isoWeekFromCalendarDate(when.from);
  return undefined;
}

/** Inclusive ISO-week range for an explicit date range. */
export function weeksFromWhen(when: WhenValue): string | undefined {
  if (when?.mode !== "range" || !when.from) return undefined;
  const start = isoWeekFromCalendarDate(when.from);
  const end = isoWeekFromCalendarDate(when.to ?? when.from);
  if (start == null || end == null) return undefined;
  return `${Math.min(start, 52)}-${Math.min(end, 52)}`;
}

/** Month (1..12) implied by the time pick — used to rank the open place axis. */
function monthFromWhen(when: WhenValue): number | undefined {
  if (when?.mode === "flex" && when.month) return when.month;
  if (when?.mode === "range" && when.from) return parseCalendarDate(when.from)?.month;
  return undefined;
}

/** Build the /search query params from the full search value.
 *
 * The place axis is encoded as an entity id (``spot_id``/``region_id``), free
 * text (``q``), or *nothing* when open. The time axis is a concrete ``week``
 * (+``month``) or *nothing* when open. The results page reads which axes are
 * present to pick the right ranking (spots · best-weeks · best-regions).
 */
export function buildSearchParams(v: SearchValue): URLSearchParams {
  const p = new URLSearchParams();

  // --- place axis ---
  if (!isPlaceOpen(v)) {
    if (v.whereSel?.id) {
      p.set(v.whereSel.kind === "region" ? "region_id" : "spot_id", v.whereSel.id);
      p.set("q", v.whereSel.label);
    } else {
      const q = (v.whereSel?.label ?? v.whereText).trim();
      if (q) p.set("q", q);
    }
  }

  // /search takes a single sport → use the first selected discipline.
  if (v.which.length) p.set("sport", v.which[0]);

  // --- time axis ---
  const week = weekFromWhen(v.when);
  if (week) p.set("week", String(week));
  const weeks = weeksFromWhen(v.when);
  if (weeks) p.set("weeks", weeks);
  const month = monthFromWhen(v.when);
  if (month) p.set("month", String(month));
  if (v.when?.mode === "range" && parseCalendarDate(v.when.from)) {
    p.set("from", v.when.from);
    if (v.when.to && parseCalendarDate(v.when.to)) p.set("to", v.when.to);
  }

  return p;
}

/** Human-readable summary of a `when` value for the collapsed segment. */
const MONTHS_FULL = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];
export function whenLabel(when: WhenValue): string {
  if (!when) return "";
  if (when.mode === "open") return "unentschlossen";
  if (when.mode === "flex") return MONTHS_FULL[when.month - 1];
  const fmt = (iso: string) => {
    const value = parseCalendarDate(iso);
    return value ? `${value.day}.${value.month}.` : iso;
  };
  return when.to ? `${fmt(when.from)} – ${fmt(when.to)}` : fmt(when.from);
}

export function searchDateRangeLabel(from?: string | null, to?: string | null): string | null {
  if (!from) return null;
  const start = parseCalendarDate(from);
  const end = parseCalendarDate(to ?? from);
  if (!start || !end) return null;
  const includeYear = start.year !== end.year;
  const format = (value: CalendarDate) => new Intl.DateTimeFormat("de-DE", {
    day: "numeric",
    month: "long",
    year: includeYear ? "numeric" : undefined,
    timeZone: "UTC",
  }).format(new Date(Date.UTC(value.year, value.month - 1, value.day)));
  return from === (to ?? from) ? format(start) : `${format(start)} – ${format(end)}`;
}
