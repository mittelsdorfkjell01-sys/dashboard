/**
 * "Geöffnet" / "Geschlossen" from an OpenStreetMap `opening_hours` value, at
 * the spot's local time — never the visitor's, who may be planning from
 * another time zone.
 *
 * Only the everyday form is read: weekday selectors (ranges, lists, ranges
 * across the week end like Th-Tu), times (also past midnight), `off`, and
 * later rules overriding earlier ones for their days (`Mo-Fr 10-17; We off`).
 * Anything we cannot be sure about returns null and the card shows no status:
 * months and seasons, school holidays, public holidays that close the place
 * (we do not know the holiday calendar), sunrise/sunset, nth weekdays,
 * comments, fallback rules, and an open end (`16:00+`) once it has started.
 */

export type OpeningState = "open" | "closed";

const DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"] as const;
const DAY_INDEX: Record<string, number> = Object.fromEntries(DAYS.map((day, index) => [day, index]));

/** Too rich to be sure of: we answer nothing rather than something wrong. */
const UNSURE =
  /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|week|SH|easter|sunrise|sunset|dawn|dusk)\b|\|\||"|\[|\b\d{4}\b|\bPH\s+(off|closed)\b/i;

type Range = { start: number; end: number; openEnd: boolean };
type DayPlan = Range[];

function minutes(text: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(text);
  if (!match) return null;
  const hours = Number(match[1]);
  const mins = Number(match[2]);
  if (hours > 48 || mins > 59) return null;
  return hours * 60 + mins;
}

function parseDays(selector: string): number[] | null {
  const days = new Set<number>();
  for (const part of selector.split(",")) {
    const token = part.trim();
    if (token === "PH") continue; // "PH,Mo-Su": also on holidays — the weekdays still decide.
    const [from, to] = token.split("-");
    if (!(from in DAY_INDEX) || (to !== undefined && !(to in DAY_INDEX))) return null;
    const start = DAY_INDEX[from];
    const end = to === undefined ? start : DAY_INDEX[to];
    for (let day = start; ; day = (day + 1) % 7) {
      days.add(day);
      if (day === end) break;
    }
  }
  return [...days];
}

function parseTimes(text: string): DayPlan | null {
  if (/^(off|closed)$/i.test(text)) return [];
  const ranges: DayPlan = [];
  for (const part of text.split(",")) {
    const token = part.trim();
    const openOnly = /^(\d{1,2}:\d{2})\+$/.exec(token);
    if (openOnly) {
      const start = minutes(openOnly[1]);
      if (start == null) return null;
      ranges.push({ start, end: start, openEnd: true });
      continue;
    }
    const match = /^(\d{1,2}:\d{2})-(\d{1,2}:\d{2})(\+)?$/.exec(token);
    if (!match) return null;
    const start = minutes(match[1]);
    let end = minutes(match[2]);
    if (start == null || end == null) return null;
    if (end <= start) end += 24 * 60; // 22:00-02:00 runs into the next day
    ranges.push({ start, end, openEnd: Boolean(match[3]) });
  }
  return ranges;
}

/** The week as seven day plans, or null when the value is outside what we read. */
export function parseOpeningHours(raw: string): DayPlan[] | null {
  const value = raw.trim();
  if (!value || UNSURE.test(value)) return null;
  if (value === "24/7") return DAYS.map(() => [{ start: 0, end: 24 * 60, openEnd: false }]);
  const week: Array<DayPlan | null> = DAYS.map(() => null);
  for (const rawRule of value.split(";")) {
    const rule = rawRule.trim();
    if (!rule) continue;
    const match = /^((?:PH|Mo|Tu|We|Th|Fr|Sa|Su)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?(?:\s*,\s*(?:PH|Mo|Tu|We|Th|Fr|Sa|Su)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?)*)?\s*(.*)$/.exec(rule);
    if (!match) return null;
    const selector = match[1]?.replace(/\s+/g, "");
    const timeText = match[2].trim();
    if (selector === "PH") continue; // holidays only: says nothing about an ordinary day
    const days = selector ? parseDays(selector) : DAYS.map((_, index) => index);
    const plan = timeText ? parseTimes(timeText) : null;
    if (!days || !plan) return null;
    for (const day of days) week[day] = plan; // later rules win for their days
  }
  return week.map((plan) => plan ?? []);
}

/** Weekday (Mo = 0) and minutes after midnight at `timeZone`. */
function localClock(now: Date, timeZone: string): { day: number; minute: number } | null {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone, weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(now);
    const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
    const day = DAY_INDEX[get("weekday").slice(0, 2)];
    if (day === undefined) return null;
    return { day, minute: Number(get("hour")) * 60 + Number(get("minute")) };
  } catch {
    return null; // unknown time zone name
  }
}

export function openingState(raw: string | null | undefined, now: Date, timeZone: string | null | undefined): OpeningState | null {
  if (!raw || !timeZone) return null;
  const week = parseOpeningHours(raw);
  const clock = week && localClock(now, timeZone);
  if (!week || !clock) return null;
  const { day, minute } = clock;
  const yesterday = (day + 6) % 7;
  const candidates = [
    ...week[day].map((range) => ({ range, at: minute })),
    ...week[yesterday].map((range) => ({ range, at: minute + 24 * 60 })),
  ];
  let unsure = false;
  for (const { range, at } of candidates) {
    if (range.openEnd && range.start === range.end) {
      // "16:00+": open, but until when? Assume it is over by the next morning.
      if (at >= range.start && at < range.start + 12 * 60) unsure = true;
      continue;
    }
    if (at >= range.start && at < range.end) return "open";
    if (range.openEnd && at >= range.end && at < range.end + 6 * 60) unsure = true;
  }
  return unsure ? null : "closed";
}
