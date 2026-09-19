// The landing search's value model + how it maps onto the backend `/search`
// query. IMPORTANT: the existing /search endpoint (see getSearch in api.ts) only
// understands `q`, a single `sport`, one `week`, and `level`. Richer inputs
// (multiple sports, a real date range) are sent through as extra params but are
// marked `// TODO backend` — they are NOT invented endpoints, just forward-compat
// hints the current backend ignores.

/** Flexible-search duration, combinable with a month (e.g. "best weekend in January"). */
export type WhenDuration = "weekend" | "week" | "twoweeks";

export type WhenValue =
  // Explicit calendar range (left side of the "Wann?" panel).
  | { mode: "range"; from: string; to?: string } // yyyy-mm-dd
  // Flexible: a month and/or a duration (right side). At least one is set.
  | { mode: "flex"; month?: number; duration?: WhenDuration } // month 1..12
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
  which: string[]; // backend sport values: surf | kitesurf | windsurf | wing
  /** Optional second-stage variant key (windsurf:fin|foil, kitesurf:classic|foil).
   *  Set only when the user narrows a wind/kite sport to a discipline. */
  variant: string | null;
  disciplines: string[]; // freestyle | big_air (riding styles)
}

export const EMPTY_SEARCH: SearchValue = {
  whereText: "",
  whereSel: null,
  whereOpen: false,
  when: null,
  which: [],
  variant: null,
  disciplines: [],
};

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

/** Representative week for a month (its 15th) — used when only a month is chosen. */
export function weekOfMonth(month1to12: number, year = new Date().getFullYear()): number {
  return isoWeek(new Date(year, month1to12 - 1, 15));
}

export function weekFromWhen(when: WhenValue): number | undefined {
  if (!when) return undefined;
  if (when.mode === "flex") return when.month ? weekOfMonth(when.month) : undefined;
  if (when.mode === "range" && when.from) return isoWeek(new Date(when.from));
  return undefined;
}

/** Month (1..12) implied by the time pick — used to rank the open place axis. */
function monthFromWhen(when: WhenValue): number | undefined {
  if (when?.mode === "flex" && when.month) return when.month;
  if (when?.mode === "range" && when.from) return new Date(when.from).getMonth() + 1;
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

  // /search takes a single sport → use the first selected sport. A chosen
  // variant (Windfoil/Kitefoil/…) is sent alongside; the backend filters to
  // spots that actually offer that variant, never merely the parent sport.
  if (v.which.length) p.set("sport", v.which[0]);
  if (v.variant) p.set("variant", v.variant);

  // --- time axis ---
  const week = weekFromWhen(v.when);
  if (week) p.set("week", String(week));
  const month = monthFromWhen(v.when);
  if (month) p.set("month", String(month));

  // Richer inputs, forwarded for future backend support (currently unread):
  if (v.which.length > 1) p.set("sports", v.which.join(",")); // TODO backend
  if (v.disciplines.length) p.set("disciplines", v.disciplines.join(",")); // TODO backend
  if (v.when?.mode === "range") {
    p.set("from", v.when.from); // TODO backend
    if (v.when.to) p.set("to", v.when.to); // TODO backend
  }
  if (v.when?.mode === "flex" && v.when.duration) p.set("duration", v.when.duration); // TODO backend
  return p;
}

/** Human-readable summary of a `when` value for the collapsed segment. */
const MONTHS_FULL = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];
const DURATION_LABEL: Record<WhenDuration, string> = {
  weekend: "ein Wochenende",
  week: "eine Woche",
  twoweeks: "zwei Wochen",
};
export function whenLabel(when: WhenValue): string {
  if (!when) return "";
  if (when.mode === "open") return "unentschlossen";
  if (when.mode === "flex") {
    const parts: string[] = [];
    if (when.month) parts.push(MONTHS_FULL[when.month - 1]);
    if (when.duration) parts.push(DURATION_LABEL[when.duration]);
    return parts.join(" · ");
  }
  const fmt = (iso: string) => {
    const d = new Date(iso);
    return `${d.getDate()}.${d.getMonth() + 1}.`;
  };
  return when.to ? `${fmt(when.from)} – ${fmt(when.to)}` : fmt(when.from);
}
