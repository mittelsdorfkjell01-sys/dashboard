// "Wann?" panel for the desktop search. The Datum/flexibel toggle (owned by the
// SearchBar and passed as `tab`) picks the mode; this renders only the active
// one, full width:
//  • "date" → a two-month calendar for an explicit range (mode:"range").
//  • "flex" → a month grid + a duration (mode:"flex").

import { useState } from "react";
import type { SVGProps } from "react";
import type { WhenDuration, WhenValue } from "../../lib/searchSubmit";
import type { WhenTab } from "../MobileSearchWhen";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS_SHORT = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"];
const MONTHS_LONG = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

const chev = {
  width: "1em",
  height: "1em",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};
const ChevL = (p: SVGProps<SVGSVGElement>) => (
  <svg {...chev} {...p}><path d="m15 6-6 6 6 6" /></svg>
);
const ChevR = (p: SVGProps<SVGSVGElement>) => (
  <svg {...chev} {...p}><path d="m9 6 6 6-6 6" /></svg>
);

const toISO = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Mon-first grid of the month; leading blanks as null. */
function monthCells(year: number, month: number): (Date | null)[] {
  const startDow = (new Date(year, month, 1).getDay() + 6) % 7;
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (Date | null)[] = Array.from({ length: startDow }, () => null);
  for (let d = 1; d <= days; d++) cells.push(new Date(year, month, d));
  return cells;
}

const addMonth = (a: { y: number; m: number }, delta: number) => {
  const total = a.y * 12 + a.m + delta;
  return { y: Math.floor(total / 12), m: ((total % 12) + 12) % 12 };
};

export default function SearchWhen({
  value,
  onChange,
  tab,
}: {
  value: WhenValue;
  onChange: (next: WhenValue) => void;
  /** Datum (calendar) or flexibel (month + duration); owned by the SearchBar. */
  tab: WhenTab;
}) {
  const today = new Date();
  const [anchor, setAnchor] = useState({ y: today.getFullYear(), m: today.getMonth() });

  const range = value?.mode === "range" ? value : null;
  const flex = value?.mode === "flex" ? value : null;
  const selMonth = flex?.month ?? null;
  const selDuration = flex?.duration ?? null;

  const clickDay = (d: Date) => {
    const iso = toISO(d);
    if (!range || range.to || !range.from) {
      onChange({ mode: "range", from: iso });
      return;
    }
    onChange(
      iso < range.from
        ? { mode: "range", from: iso, to: range.from }
        : { mode: "range", from: range.from, to: iso }
    );
  };

  // Merge a month/duration change into the flexible pick; clearing both → null.
  const setFlex = (next: { month?: number; duration?: WhenDuration }) => {
    const month = "month" in next ? next.month : flex?.month;
    const duration = "duration" in next ? next.duration : flex?.duration;
    if (!month && !duration) {
      onChange(null);
      return;
    }
    onChange({
      mode: "flex",
      ...(month ? { month } : {}),
      ...(duration ? { duration } : {}),
    });
  };

  const pickMonth = (m1: number) => setFlex({ month: selMonth === m1 ? undefined : m1 });
  const pickDuration = (d: WhenDuration) =>
    setFlex({ duration: selDuration === d ? undefined : d });

  const inRange = (d: Date) => {
    if (!range?.from) return false;
    const iso = toISO(d);
    if (!range.to) return iso === range.from;
    return iso >= range.from && iso <= range.to;
  };
  const isEdge = (d: Date) => {
    if (!range?.from) return false;
    const iso = toISO(d);
    return iso === range.from || iso === range.to;
  };

  const months = [anchor, addMonth(anchor, 1)];

  // ── Datum: two-month calendar, full width ────────────────────────────────
  if (tab === "date") {
    return (
      <div className="flex items-start gap-8">
        {months.map((mm, idx) => (
          <div key={idx} className="flex-1">
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setAnchor(addMonth(anchor, -1))}
                aria-label="Vorheriger Monat"
                className={`grid h-7 w-7 place-items-center rounded-lg text-ink transition-colors hover:bg-band ${idx === 0 ? "" : "invisible"}`}
              >
                <ChevL className="text-sz-18" />
              </button>
              <span className="text-ui font-semibold text-ink">
                {MONTHS_LONG[mm.m]} {mm.y}
              </span>
              <button
                type="button"
                onClick={() => setAnchor(addMonth(anchor, 1))}
                aria-label="Nächster Monat"
                className={`grid h-7 w-7 place-items-center rounded-lg text-ink transition-colors hover:bg-band ${idx === months.length - 1 ? "" : "invisible"}`}
              >
                <ChevR className="text-sz-18" />
              </button>
            </div>
            <div className="grid grid-cols-7 gap-y-0.5">
              {WEEKDAYS.map((w) => (
                <span key={w} className="pb-1 text-center text-sz-11 font-medium text-muted">
                  {w}
                </span>
              ))}
              {monthCells(mm.y, mm.m).map((d, i) =>
                d ? (
                  <button
                    key={i}
                    type="button"
                    onClick={() => clickDay(d)}
                    className={`mx-auto grid h-8 w-8 place-items-center rounded-full text-label transition-colors ${
                      isEdge(d)
                        ? "bg-teal text-white"
                        : inRange(d)
                        ? "bg-teal/15 text-ink"
                        : "text-ink hover:bg-band"
                    }`}
                  >
                    {d.getDate()}
                  </button>
                ) : (
                  <span key={i} />
                )
              )}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // ── flexibel: month grid + duration, full width ──────────────────────────
  const monthChip = (active: boolean) =>
    `flex h-10 items-center justify-center rounded-xl border px-2 text-label font-medium transition-colors ${
      active ? "border-teal bg-teal/10 text-teal" : "border-line text-ink hover:border-teal"
    }`;
  const durChip = (active: boolean) =>
    `flex h-10 items-center justify-center rounded-full border px-5 text-label font-medium transition-colors ${
      active ? "border-teal bg-teal/10 text-teal" : "border-line text-ink hover:border-teal"
    }`;

  return (
    <div>
      <p className="mb-2 text-label font-medium text-muted">Monat</p>
      <div className="grid grid-cols-6 gap-2">
        {MONTHS_SHORT.map((mon, i) => (
          <button key={mon} type="button" onClick={() => pickMonth(i + 1)} className={monthChip(selMonth === i + 1)}>
            {mon}
          </button>
        ))}
      </div>

      <p className="mb-2 mt-5 text-label font-medium text-muted">Zeitspanne</p>
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["Ein Wochenende", "weekend"],
            ["Eine Woche", "week"],
            ["zwei Wochen", "twoweeks"],
          ] as const
        ).map(([label, dur]) => (
          <button key={dur} type="button" onClick={() => pickDuration(dur)} className={durChip(selDuration === dur)}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
