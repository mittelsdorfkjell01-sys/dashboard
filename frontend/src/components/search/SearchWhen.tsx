// "Wann?" panel (Frame_3). Two ways to say "when", which are mutually exclusive:
//  • LEFT  — a two-month calendar for an explicit date range.
//  • RIGHT — a flexible pick: a month AND/OR a duration (e.g. "January + a
//    weekend" → the backend finds the best weekend(s) in that month).
// Touching one side greys out + disables the other; "Zurücksetzen" clears both.

import { useState } from "react";
import type { SVGProps } from "react";
import type { WhenDuration, WhenValue } from "../../lib/searchSubmit";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEC"];
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
}: {
  value: WhenValue;
  onChange: (next: WhenValue) => void;
}) {
  const today = new Date();
  const [anchor, setAnchor] = useState({ y: today.getFullYear(), m: today.getMonth() });

  const range = value?.mode === "range" ? value : null;
  const flex = value?.mode === "flex" ? value : null;
  const selMonth = flex?.month ?? null;
  const selDuration = flex?.duration ?? null;

  // A choice on one side locks the other until reset; "egal wann" locks both.
  const isOpen = value?.mode === "open";
  const calDisabled = value?.mode === "flex" || isOpen;
  const flexDisabled = value?.mode === "range" || isOpen;

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

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-6">
      <div
        aria-disabled={calDisabled}
        className={`flex flex-1 gap-4 transition-opacity ${
          calDisabled ? "pointer-events-none opacity-40" : ""
        }`}
      >
        {months.map((mm, idx) => (
          <div key={idx} className="flex-1">
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setAnchor(addMonth(anchor, -1))}
                aria-label="Vorheriger Monat"
                className={`grid h-7 w-7 place-items-center rounded-lg text-ink transition-colors hover:bg-band ${idx === 0 ? "" : "invisible"}`}
              >
                <ChevL className="text-[16px]" />
              </button>
              <span className="text-[13px] font-semibold text-ink">
                {MONTHS_LONG[mm.m]} {mm.y}
              </span>
              <button
                type="button"
                onClick={() => setAnchor(addMonth(anchor, 1))}
                aria-label="Nächster Monat"
                className={`grid h-7 w-7 place-items-center rounded-lg text-ink transition-colors hover:bg-band ${idx === months.length - 1 ? "" : "invisible"}`}
              >
                <ChevR className="text-[16px]" />
              </button>
            </div>
            <div className="grid grid-cols-7 gap-y-0.5">
              {WEEKDAYS.map((w) => (
                <span key={w} className="pb-0.5 text-center text-[10px] font-medium text-muted">
                  {w}
                </span>
              ))}
              {monthCells(mm.y, mm.m).map((d, i) =>
                d ? (
                  <button
                    key={i}
                    type="button"
                    onClick={() => clickDay(d)}
                    className={`mx-auto grid h-7 w-7 place-items-center rounded-lg text-[11px] transition-colors ${
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

      <div className="sm:w-[200px]">
        <div
          aria-disabled={flexDisabled}
          className={`transition-opacity ${
            flexDisabled ? "pointer-events-none opacity-40" : ""
          }`}
        >
          <p className="mb-1.5 text-[12px] font-medium text-muted">Monat</p>
          <div className="grid grid-cols-4 gap-1.5">
            {MONTHS_SHORT.map((mon, i) => (
              <button
                key={mon}
                type="button"
                onClick={() => pickMonth(i + 1)}
                className={`rounded-lg border px-2 py-1.5 text-[12px] font-medium transition-colors ${
                  selMonth === i + 1
                    ? "border-teal bg-teal/10 text-teal"
                    : "border-line text-teal hover:border-teal"
                }`}
              >
                {mon}
              </button>
            ))}
          </div>

          <p className="mb-1.5 mt-3 text-[12px] font-medium text-muted">Zeitspanne</p>
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                ["Ein Wochenende", "weekend"],
                ["Eine Woche", "week"],
                ["zwei Wochen", "twoweeks"],
              ] as const
            ).map(([label, dur]) => (
              <button
                key={dur}
                type="button"
                onClick={() => pickDuration(dur)}
                className={`rounded-2xl border px-3 py-1.5 text-[12px] transition-colors ${
                  selDuration === dur
                    ? "border-teal bg-teal/10 text-teal"
                    : "border-line text-teal hover:border-teal"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Always rendered (just hidden when empty) so showing it doesn't grow the panel. */}
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-hidden={!value}
          tabIndex={value ? 0 : -1}
          className={`mt-3 text-[12px] font-medium text-teal underline underline-offset-2 transition-colors hover:text-teal-hover ${
            value ? "" : "invisible"
          }`}
        >
          Zurücksetzen
        </button>
      </div>
    </div>
  );
}
