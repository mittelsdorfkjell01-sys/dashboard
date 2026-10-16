import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import type { WhenDuration, WhenValue } from "../lib/searchSubmit";

/**
 * "Wann?" picker for the mobile search sheet (Figma Frames 18/19), controlled
 * by `tab`. The Datum/flexibel toggle lives in the tile header (WhenToggle);
 * this renders only the active mode:
 *   - Datum    → a compact scrolling month calendar; a tapped day → mode:"range".
 *   - flexibel → a month grid + duration → mode:"flex".
 */

export type WhenTab = "date" | "flex";

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

/** Segmented Datum/flexibel toggle with a sliding active pill. */
export function WhenToggle({
  tab,
  onChange,
}: {
  tab: WhenTab;
  onChange: (t: WhenTab) => void;
}) {
  return (
    <div className="relative inline-flex shrink-0 rounded-card bg-teal p-0.5">
      {(["date", "flex"] as const).map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onChange(t)}
          aria-pressed={tab === t}
          className="relative rounded-card px-3.5 py-0.5 text-caption font-medium"
        >
          {tab === t && (
            <motion.span
              layoutId="when-toggle-pill"
              className="absolute inset-0 rounded-card bg-surface"
              transition={{ type: "spring", stiffness: 500, damping: 38 }}
            />
          )}
          <span
            className={`relative transition-colors ${
              tab === t ? "text-ink" : "text-on-photo"
            }`}
          >
            {t === "date" ? "Datum" : "flexibel"}
          </span>
        </button>
      ))}
    </div>
  );
}

export default function MobileSearchWhen({
  tab,
  value,
  onChange,
}: {
  tab: WhenTab;
  value: WhenValue;
  onChange: (when: WhenValue) => void;
}) {
  return (
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
            selectedFrom={value?.mode === "range" ? value.from : undefined}
            selectedTo={value?.mode === "range" ? value.to : undefined}
            onPick={(from, to) => onChange({ mode: "range", from, to })}
          />
        ) : (
          <FlexPicker value={value} onChange={onChange} />
        )}
      </motion.div>
    </AnimatePresence>
  );
}

function DateCalendar({
  selectedFrom,
  selectedTo,
  onPick,
}: {
  selectedFrom?: string;
  selectedTo?: string;
  onPick: (from: string, to?: string) => void;
}) {
  const today = new Date();
  const todayY = today.getFullYear();
  const todayM = today.getMonth();
  const todayD = today.getDate();
  const [monthOffset, setMonthOffset] = useState(0);
  const visibleMonth = new Date(todayY, todayM + monthOffset, 1);
  const year = visibleMonth.getFullYear();
  const month0 = visibleMonth.getMonth();
  const dateIso = (date: Date) => isoOf(date.getFullYear(), date.getMonth(), date.getDate());
  const addDays = (date: Date, days: number) => {
    const next = new Date(date);
    next.setDate(next.getDate() + days);
    return next;
  };
  const weekendStart = addDays(today, (6 - today.getDay() + 7) % 7);

  return (
    <div>
      <div className="mb-4 grid grid-cols-3 gap-2">
        <button type="button" onClick={() => onPick(dateIso(today))} className="min-h-11 rounded-card border border-line px-2 text-caption font-medium text-ink">Heute</button>
        <button type="button" onClick={() => onPick(dateIso(weekendStart), dateIso(addDays(weekendStart, 1)))} className="min-h-11 rounded-card border border-line px-2 text-caption font-medium text-ink">Wochenende</button>
        <button type="button" onClick={() => onPick(dateIso(today), dateIso(addDays(today, 6)))} className="min-h-11 rounded-card border border-line px-2 text-caption font-medium text-ink">7 Tage</button>
      </div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <button
          type="button"
          disabled={monthOffset === 0}
          onClick={() => setMonthOffset((value) => Math.max(0, value - 1))}
          className="min-h-11 rounded-card px-3 text-ui font-semibold text-ink disabled:opacity-30"
        >
          Zurück
        </button>
        <p aria-live="polite" className="text-center text-body font-semibold text-ink">
          {MONTHS_FULL[month0]} {year}
        </p>
        <button
          type="button"
          disabled={monthOffset === 11}
          onClick={() => setMonthOffset((value) => Math.min(11, value + 1))}
          className="min-h-11 rounded-card px-3 text-ui font-semibold text-ink disabled:opacity-30"
        >
          Weiter
        </button>
      </div>
      <div>
          <div className="grid grid-cols-7 text-center text-caption font-medium text-muted">
            {WEEKDAYS.map((w) => (
              <span key={w} className="pb-1">
                {w}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {monthCells(year, month0).map((day, i) => {
                if (day === null) return <span key={`e-${i}`} />;
                const iso = isoOf(year, month0, day);
                const isPast =
                  year === todayY && month0 === todayM && day < todayD;
                const isSelected = iso === selectedFrom || iso === selectedTo;
                const isInRange = Boolean(selectedFrom && selectedTo && iso > selectedFrom && iso < selectedTo);
                return (
                  <div key={iso} className="flex justify-center py-0.5">
                    <button
                      type="button"
                      disabled={isPast}
                      onClick={() => onPick(iso)}
                      aria-label={`${day}. ${MONTHS_FULL[month0]} ${year}`}
                      className={`grid h-11 w-11 place-items-center rounded-full text-ui transition-[background-color,color,transform] active:scale-[0.9] ${
                        isSelected
                          ? "bg-teal font-semibold text-white"
                          : isInRange
                            ? "bg-band font-medium text-ink"
                          : isPast
                            ? "cursor-default text-ink/25 active:scale-100"
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
    `min-h-11 rounded-card border px-4 py-2.5 text-ui font-medium transition-colors ${
      active
        ? "border-teal bg-teal text-white"
        : "border-line text-ink hover:bg-band"
    }`;

  return (
    <div>
      <p className="text-ui font-medium text-muted">Monat</p>
      <div className="mt-2 grid grid-cols-4 gap-2">
        {MONTHS_ABBR.map((label, i) => {
          const m = i + 1;
          const active = month === m;
          return (
            <motion.button
              key={label}
              type="button"
              whileTap={{ scale: 0.94 }}
              onClick={() => commit(active ? undefined : m, duration)}
              className={chip(active)}
            >
              {label}
            </motion.button>
          );
        })}
      </div>

      <p className="mt-4 text-ui font-medium text-muted">Zeitspanne</p>
      <div className="mt-2 space-y-2">
        <motion.button
          type="button"
          whileTap={{ scale: 0.97 }}
          onClick={() =>
            commit(month, duration === "weekend" ? undefined : "weekend")
          }
          className={`w-full ${chip(duration === "weekend")}`}
        >
          Ein Wochenende
        </motion.button>
        <div className="grid grid-cols-2 gap-2">
          {DURATIONS.filter((d) => d.value !== "weekend").map((d) => (
            <motion.button
              key={d.value}
              type="button"
              whileTap={{ scale: 0.96 }}
              onClick={() =>
                commit(month, duration === d.value ? undefined : d.value)
              }
              className={chip(duration === d.value)}
            >
              {d.label}
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  );
}
