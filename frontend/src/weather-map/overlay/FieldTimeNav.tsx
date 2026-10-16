import { useMemo } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "../../lib/icons";

const DAY = new Intl.DateTimeFormat("de-DE", { weekday: "short" });
const TIME = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const DATE_KEY = new Intl.DateTimeFormat("sv-SE", { year: "numeric", month: "2-digit", day: "2-digit" });

/** How far ahead the map lets you look: today and the four days after it. */
export const FIELD_DAYS = 5;

const key = (value: number) => DATE_KEY.format(new Date(value));
const startOfDay = (value: number) => new Date(value).setHours(0, 0, 0, 0);
const addDays = (value: number, days: number) => {
  const date = new Date(value);
  date.setDate(date.getDate() + days);
  return date.setHours(0, 0, 0, 0);
};

/** The published instants inside the five-day window, in order. A publication
 *  that lies entirely outside it — a stale run, or a fixture from another week
 *  — is returned whole rather than emptied: the map draws the data it has and
 *  says which hour that is, instead of going blank. */
export function fieldWindow(times: string[], now = Date.now()): string[] {
  const ordered = [...times].sort((a, b) => Date.parse(a) - Date.parse(b));
  const from = now - 60 * 60_000;
  const to = now + FIELD_DAYS * 24 * 60 * 60_000;
  const inWindow = ordered.filter((time) => { const at = Date.parse(time); return at >= from && at <= to; });
  return inWindow.length ? inWindow : ordered;
}

/** The instant in `times` closest to `target`. */
export function nearestTime(times: string[], target: number): string | undefined {
  let best: string | undefined;
  let bestDistance = Infinity;
  for (const time of times) {
    const distance = Math.abs(Date.parse(time) - target);
    if (distance < bestDistance) { best = time; bestDistance = distance; }
  }
  return best;
}

/**
 * The slider's span for one day: today starts at *now* — a forecast map has
 * no reason to look back — every other day at midnight, and both ends are
 * clipped to what the publication actually covers.
 */
export function dayDomain(
  day: number,
  { nowAt, publishedFrom, publishedTo }: { nowAt: number; publishedFrom: number; publishedTo: number },
): { from: number; to: number } | null {
  const begins = startOfDay(day) === startOfDay(nowAt) ? nowAt : startOfDay(day);
  const from = Math.max(begins, publishedFrom);
  const to = Math.min(addDays(day, 1) - 60_000, publishedTo);
  return to > from ? { from, to } : null;
}

/** Today and the next four days, as far as the publication reaches. */
export function selectableDays(nowAt: number, publishedTo: number): number[] {
  const days: number[] = [];
  for (let index = 0; index < FIELD_DAYS; index += 1) {
    const day = index === 0 ? nowAt : addDays(nowAt, index);
    if (day > publishedTo) break;
    days.push(day);
  }
  return days;
}

/** Hour labels under the track: the six-hour marks inside the span, with the
 *  left end reading "jetzt" on today. */
export function hourMarks(from: number, to: number, nowAt: number): Array<{ at: number; label: string; offset: number }> {
  const span = Math.max(1, to - from);
  const marks: Array<{ at: number; label: string; offset: number }> = [
    { at: from, label: from === nowAt ? "jetzt" : TIME.format(new Date(from)), offset: 0 },
  ];
  for (let hour = 0; hour <= 24; hour += 6) {
    const at = new Date(from).setHours(hour, 0, 0, 0);
    if (at <= from || at > to) continue;
    const offset = (at - from) / span;
    // Two labels in the same place read as one smudge.
    if (offset - marks[marks.length - 1].offset < 0.12) continue;
    marks.push({ at, label: TIME.format(new Date(at)), offset });
  }
  // Late in the evening no six-hour mark is left inside the span, which left
  // the track labelled "jetzt" and nothing else. The end always gets a label.
  const end = new Date(to);
  if (marks[marks.length - 1].offset < 0.88) {
    marks.push({ at: to, label: end.getHours() === 23 && end.getMinutes() >= 58 ? "24:00" : TIME.format(end), offset: 1 });
  }
  return marks;
}

/**
 * The map's clock. One day per slider: the handle runs from now (left) to the
 * end of that day (right) and moves continuously — the field between two
 * published hours is interpolated, so there is nothing to snap to. The days
 * themselves are switched with the two small chevrons beside the date, today
 * plus four.
 */
export default function FieldTimeNav({
  value,
  nowAt,
  publishedFrom,
  publishedTo,
  onChange,
}: {
  value: number;
  nowAt: number;
  publishedFrom: number;
  publishedTo: number;
  onChange: (at: number) => void;
}) {
  const bounds = useMemo(() => ({ nowAt, publishedFrom, publishedTo }), [nowAt, publishedFrom, publishedTo]);
  const days = useMemo(() => selectableDays(nowAt, publishedTo), [nowAt, publishedTo]);
  const dayIndex = Math.max(0, days.findIndex((day) => key(day) === key(value)));
  const domain = useMemo(
    () => dayDomain(days[dayIndex] ?? nowAt, bounds) ?? { from: nowAt, to: nowAt + 3_600_000 },
    [days, dayIndex, nowAt, bounds],
  );
  const marks = useMemo(() => hourMarks(domain.from, domain.to, nowAt), [domain, nowAt]);

  const goToDay = (index: number) => {
    const day = days[index];
    if (day === undefined) return;
    const next = dayDomain(day, bounds);
    if (next) onChange(next.from);
  };

  const today = key(nowAt) === key(value);

  return (
    <section className="swd-wx-time" aria-label="Vorhersagezeit">
      <div className="swd-wx-time-head">
        <button type="button" aria-label="Vorheriger Tag" disabled={dayIndex <= 0} onClick={() => goToDay(dayIndex - 1)}>
          <ChevronLeftIcon className="text-ui" />
        </button>
        <p className="swd-wx-time-value">
          <span>{today ? "Heute" : DAY.format(new Date(value)).replace(".", "")}</span>
          {" "}
          <strong>{TIME.format(new Date(value))}</strong>
        </p>
        <button type="button" aria-label="Nächster Tag" disabled={dayIndex >= days.length - 1} onClick={() => goToDay(dayIndex + 1)}>
          <ChevronRightIcon className="text-ui" />
        </button>
        {Math.abs(value - nowAt) > 60_000 && (
          <button type="button" className="swd-wx-time-now" onClick={() => onChange(nowAt)}>Jetzt</button>
        )}
      </div>
      <input
        type="range"
        min={domain.from}
        max={domain.to}
        // No step: the clock runs continuously, because every moment between
        // two published hours is interpolated rather than picked.
        step="any"
        value={Math.min(Math.max(value, domain.from), domain.to)}
        aria-label={`Vorhersagezeit ${DAY.format(new Date(value))} ${TIME.format(new Date(value))}`}
        aria-valuetext={`${DAY.format(new Date(value))} ${TIME.format(new Date(value))}`}
        onChange={(event) => onChange(Math.round(Number(event.target.value)))}
      />
      <div className="swd-wx-time-marks" aria-hidden="true">
        {marks.map((mark) => <span key={mark.at} style={{ left: `${mark.offset * 100}%` }}>{mark.label}</span>)}
      </div>
    </section>
  );
}
