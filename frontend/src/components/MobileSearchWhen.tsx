import { AnimatePresence, motion } from "framer-motion";
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
    <div className="relative inline-flex shrink-0 rounded-full bg-teal p-1">
      {(["date", "flex"] as const).map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onChange(t)}
          aria-pressed={tab === t}
          className="relative rounded-full px-4 py-1 text-[12px] font-medium"
        >
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
            selected={value?.mode === "range" ? value.from : undefined}
            onPick={(iso) => onChange({ mode: "range", from: iso })}
          />
        ) : (
          <FlexPicker value={value} onChange={onChange} />
        )}
      </motion.div>
    </AnimatePresence>
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
  const months = Array.from({ length: 12 }, (_, i) => {
    const d = new Date(todayY, todayM + i, 1);
    return { year: d.getFullYear(), month0: d.getMonth() };
  });

  return (
    <div>
      {/* Weekday header — shared across all months below. */}
      <div className="grid grid-cols-7 px-1 text-center text-[11px] font-medium text-muted">
        {WEEKDAYS.map((w) => (
          <span key={w} className="py-1">
            {w}
          </span>
        ))}
      </div>

      <div className="mt-1 h-[220px] overflow-y-auto pr-1">
        {months.map(({ year, month0 }) => (
          <div key={`${year}-${month0}`} className="mb-3">
            <p className="mb-0.5 px-1 text-[14px] font-semibold text-ink">
              {MONTHS_FULL[month0]} {year}
            </p>
            <div className="grid grid-cols-7">
              {monthCells(year, month0).map((day, i) => {
                if (day === null) return <span key={`e-${i}`} />;
                const iso = isoOf(year, month0, day);
                const isPast =
                  year === todayY && month0 === todayM && day < todayD;
                const isSelected = iso === selected;
                return (
                  <div key={iso} className="flex justify-center py-0.5">
                    <motion.button
                      type="button"
                      disabled={isPast}
                      whileTap={isPast ? undefined : { scale: 0.85 }}
                      onClick={() => onPick(iso)}
                      className={`grid h-8 w-8 place-items-center rounded-full text-[13px] transition-colors ${
                        isSelected
                          ? "bg-teal font-semibold text-white"
                          : isPast
                            ? "cursor-default text-ink/25"
                            : "text-ink hover:bg-band"
                      }`}
                    >
                      {day}
                    </motion.button>
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
    `rounded-2xl border px-4 py-2.5 text-[14px] font-medium transition-colors ${
      active
        ? "border-teal bg-teal text-white"
        : "border-line text-ink hover:bg-band"
    }`;

  return (
    <div>
      <p className="text-[13px] font-medium text-muted">Monat</p>
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

      <p className="mt-4 text-[13px] font-medium text-muted">Zeitspanne</p>
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
