import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { WhenDuration, WhenValue } from "../lib/searchSubmit";

/**
 * "Wann?" picker for the mobile search sheet (Figma Frames 18/19). A segmented
 * toggle switches between:
 *   - Datum    → a scrolling month calendar; a tapped day sets `mode:"range"`.
 *   - flexibel → a month grid + duration, setting `mode:"flex"`.
 * Touch-first layout; drives the shared `WhenValue` model.
 */

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS_FULL = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];
const MONTHS_ABBR = [
  "JAN", "FEB", "MÄR", "APR", "MAI", "JUN",
  "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ",
];
const DURATIONS: { value: WhenDuration; label: string }[] = [
  { value: "weekend", label: "Ein Wochenende" },
  { value: "week", label: "Eine Woche" },
  { value: "twoweeks", label: "zwei Wochen" },
];

const pad = (n: number) => String(n).padStart(2, "0");
const isoOf = (y: number, m0: number, d: number) => `${y}-${pad(m0 + 1)}-${pad(d)}`;

/** Monday-first cell layout for a month: leading nulls then day numbers. */
function monthCells(year: number, month0: number): (number | null)[] {
  const startOffset = (new Date(year, month0, 1).getDay() + 6) % 7;
  const days = new Date(year, month0 + 1, 0).getDate();
  return [
    ...Array.from({ length: startOffset }, () => null),
    ...Array.from({ length: days }, (_, i) => i + 1),
  ];
}

export default function MobileSearchWhen({
  value,
  onChange,
}: {
  value: WhenValue;
  onChange: (when: WhenValue) => void;
}) {
  const [tab, setTab] = useState<"date" | "flex">(
    value?.mode === "flex" ? "flex" : "date"
  );

  const switchTab = (t: "date" | "flex") => {
    if (t === tab) return;
    setTab(t);
    onChange(null); // start the new mode fresh — the two are mutually exclusive
  };

  return (
    <div>
      {/* Centred Datum/flexibel toggle (the section header carries the title). */}
      <div className="flex justify-center">
        <div className="relative inline-flex rounded-full bg-teal p-1">
          {(["date", "flex"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => switchTab(t)}
              aria-pressed={tab === t}
              className="relative rounded-full px-5 py-1.5 text-[13px] font-medium"
            >
              {/* Sliding white pill behind the active label. */}
              {tab === t && (
                <motion.span
                  layoutId="when-toggle-pill"
                  className="absolute inset-0 rounded-full bg-surface"
                  transition={{ type: "spring", stiffness: 500, damping: 38 }}
                />
              )}
              <span
                className={`relative transition-colors ${
                  tab === t ? "text-ink" : "text-white/90"
                }`}
              >
                {t === "date" ? "Datum" : "flexibel"}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Animated swap between the two modes. */}
      <div className="mt-4">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={tab}
            initial={{ opacity: 0, x: tab === "flex" ? 16 : -16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: tab === "flex" ? -16 : 16 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            {tab === "date" ? (
              <DateCalendar
                selected={value?.mode === "range" ? value.from : undefined}
                onPick={(iso) => onChange({ mode: "range", from: iso })}
              />
            ) : (
              <FlexPicker value={value} onChange={onChange} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function DateCalendar({
  selected,
  onPick,
}: {
  selected?: string;
  onPick: (iso: string) => void;
}) {
  const today = new Date();
  const todayY = today.getFullYear();
  const todayM = today.getMonth();
  const todayD = today.getDate();
  // Current month + the next 11.
  const months = Array.from({ length: 12 }, (_, i) => {
    const d = new Date(todayY, todayM + i, 1);
    return { year: d.getFullYear(), month0: d.getMonth() };
  });

  return (
    <div>
      {/* Weekday header — shared across all months below. */}
      <div className="grid grid-cols-7 px-1 text-center text-[12px] font-medium text-muted">
        {WEEKDAYS.map((w) => (
          <span key={w} className="py-1">
            {w}
          </span>
        ))}
      </div>

      <div className="mt-1 max-h-[42vh] overflow-y-auto pr-1">
        {months.map(({ year, month0 }) => (
          <div key={`${year}-${month0}`} className="mb-4">
            <p className="mb-1 px-1 text-[16px] font-semibold text-ink">
              {MONTHS_FULL[month0]} {year}
            </p>
            <div className="grid grid-cols-7 gap-y-1">
              {monthCells(year, month0).map((day, i) => {
                if (day === null) return <span key={`e-${i}`} />;
                const iso = isoOf(year, month0, day);
                const isPast =
                  year === todayY && month0 === todayM && day < todayD;
                const isSelected = iso === selected;
                return (
                  <div key={iso} className="flex justify-center py-0.5">
                    <button
                      type="button"
                      disabled={isPast}
                      onClick={() => onPick(iso)}
                      className={`grid h-10 w-10 place-items-center rounded-full text-[15px] transition-colors ${
                        isSelected
                          ? "bg-teal font-semibold text-white"
                          : isPast
                            ? "cursor-default text-ink/25"
                            : "text-ink hover:bg-band"
                      }`}
                    >
                      {day}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FlexPicker({
  value,
  onChange,
}: {
  value: WhenValue;
  onChange: (when: WhenValue) => void;
}) {
  const flex = value?.mode === "flex" ? value : undefined;
  const month = flex?.month;
  const duration = flex?.duration;

  const commit = (nextMonth?: number, nextDuration?: WhenDuration) => {
    if (!nextMonth && !nextDuration) onChange(null);
    else onChange({ mode: "flex", month: nextMonth, duration: nextDuration });
  };

  const chip = (active: boolean) =>
    `rounded-2xl border px-4 py-3 text-[14px] font-medium transition-colors ${
      active
        ? "border-teal bg-teal text-white"
        : "border-line text-ink hover:bg-band"
    }`;

  return (
    <div>
      <p className="text-[14px] font-medium text-muted">Monat</p>
      <div className="mt-2 grid grid-cols-4 gap-2">
        {MONTHS_ABBR.map((label, i) => {
          const m = i + 1;
          const active = month === m;
          return (
            <button
              key={label}
              type="button"
              onClick={() => commit(active ? undefined : m, duration)}
              className={chip(active)}
            >
              {label}
            </button>
          );
        })}
      </div>

      <p className="mt-5 text-[14px] font-medium text-muted">Zeitspanne</p>
      <div className="mt-2 space-y-2">
        <button
          type="button"
          onClick={() =>
            commit(month, duration === "weekend" ? undefined : "weekend")
          }
          className={`w-full ${chip(duration === "weekend")}`}
        >
          Ein Wochenende
        </button>
        <div className="grid grid-cols-2 gap-2">
          {DURATIONS.filter((d) => d.value !== "weekend").map((d) => (
            <button
              key={d.value}
              type="button"
              onClick={() =>
                commit(month, duration === d.value ? undefined : d.value)
              }
              className={chip(duration === d.value)}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
