import { useMemo } from "react";
import { useReducedMotion } from "framer-motion";
import type { MonthWind } from "../lib/types";
import { bestSeasonWindow, climatologyToMonths, climatologyToPercentile } from "../lib/seasonView";
import { usePersistedState } from "../lib/hooks";
import { windColor } from "../lib/windScale";

type Metric = "hours" | "knots";
const INK = "36,28,23"; // #241C17 as an rgb triple, for the hours-mode opacity ramp

const monthMean = (m: MonthWind) => m.weeks.reduce((a, b) => a + b, 0) / m.weeks.length;

/** Highlight rectangles as 1-indexed CSS grid column lines — one, or two
 *  when the window wraps the Dec→Jan boundary (a straight 12-column row
 *  can't draw a single wrapped rectangle). Grid lines (not %-of-width) so
 *  the highlight stays pixel-aligned with the bars regardless of the gap
 *  between them — a plain percentage would drift as the gap ate into the
 *  columns' share of the row. */
function highlightRects(win: { startIndex: number; endIndex: number } | null) {
  if (!win) return [];
  const { startIndex, endIndex } = win;
  if (startIndex <= endIndex) {
    return [{ startCol: startIndex + 1, endCol: endIndex + 2 }];
  }
  return [
    { startCol: startIndex + 1, endCol: 13 },
    { startCol: 1, endCol: endIndex + 2 },
  ];
}

/**
 * Yearly wind climatology, in a white card with a metric toggle:
 *
 *  - "Stunden" (default) — fahrbare Windstunden/Woche ≥ 14 kt
 *    (`climatologyToMonths`). Bars are monochrome ink with an opacity ramp;
 *    the windColor() scale is never used here — hours aren't knots, and the
 *    same colors can't mean two things on one page.
 *  - "Knoten" — P75 wind speed/Woche (`climatologyToPercentile`). Bar height
 *    *and* color come from `windColor()`, matching the forecast charts.
 *
 * Switching metrics morphs each bar's height/color over ~350ms instead of
 * snapping (plain CSS transitions on the same DOM nodes — the bars keep
 * their `key`, so React updates styles in place rather than remounting).
 * Reduced motion switches instantly. The best-season highlight and headline
 * work off whichever metric is active. Headless: the section heading lives
 * in the caller's `SectionBand`.
 */
export default function WindMonths({ climatology }: { climatology: Record<string, any> | null | undefined }) {
  const [metric, setMetric] = usePersistedState<Metric>("swd.windMonthsMetric", "hours");
  const reduce = useReducedMotion();

  const hoursData = useMemo(() => climatologyToMonths(climatology), [climatology]);
  const knotsData = useMemo(() => climatologyToPercentile(climatology, 75), [climatology]);
  const data = metric === "hours" ? hoursData : knotsData;

  if (!data) return null;

  const max = Math.max(...data.flatMap((m) => m.weeks));
  const win = bestSeasonWindow(data);
  const rects = highlightRects(win);
  const hoursOpacity = (w: number) => 0.25 + 0.75 * (max > 0 ? w / max : 0);

  const barStyle = (w: number): React.CSSProperties => ({
    height: `${Math.max(6, (w / max) * 100)}%`,
    backgroundColor: metric === "knots" ? windColor(w) : `rgba(${INK},${hoursOpacity(w)})`,
    transition: reduce ? "none" : "height 350ms ease-out, background-color 350ms ease-out",
  });

  return (
    <div className="rounded-3xl border border-line bg-white p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          {win && (
            <p className="text-title font-semibold text-ink">
              Beste Zeit: {win.startMonth} – {win.endMonth}
            </p>
          )}
          <p className={`text-caption text-muted ${win ? "mt-2" : ""}`}>
            {metric === "hours" ? "Fahrbarer Wind pro Woche · Std ≥ 14 kt" : "P75 Windgeschwindigkeit pro Woche"}
          </p>
        </div>

        <div className="inline-flex shrink-0 rounded-full bg-ink/5 p-1">
          {(["hours", "knots"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMetric(m)}
              aria-pressed={m === metric}
              className={`flex min-h-[36px] items-center justify-center rounded-2xl px-3 text-label font-medium transition-colors ${
                m === metric ? "bg-white text-teal" : "text-muted hover:text-teal"
              }`}
            >
              {m === "hours" ? "Stunden" : "Knoten"}
            </button>
          ))}
        </div>
      </div>

      {/* Screen-reader alternative to the bar chart (WCAG 1.1.1). */}
      <table className="sr-only">
        <caption>
          Windmonate — {metric === "hours" ? "fahrbare Windstunden pro Woche (≥ 14 kt)" : "P75 Windgeschwindigkeit pro Woche"}
        </caption>
        <thead>
          <tr>
            <th scope="col">Monat</th>
            <th scope="col">{metric === "hours" ? "Ø Windstunden/Woche" : "Ø P75 kt/Woche"}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((m) => (
            <tr key={m.month}>
              <td>{m.month}</td>
              <td>{monthMean(m).toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div aria-hidden="true" className="relative mt-6">
        {/* Highlight overlay — same column template + gap as the bar grid
            below, stacked via absolute positioning, so grid lines line up. */}
        <div className="pointer-events-none absolute inset-0 grid grid-cols-12 gap-1 sm:gap-4">
          {rects.map((r, i) => (
            <div
              key={i}
              className="rounded-lg bg-orange/[0.10]"
              style={{ gridColumn: `${r.startCol} / ${r.endCol}` }}
            />
          ))}
        </div>

        {/* Mobile: 12 monthly-mean bars — a 48-sliver cluster is unreadable at 375px. */}
        <div className="grid h-[clamp(220px,26vh,320px)] grid-cols-12 items-end gap-1 sm:hidden">
          {data.map((m) => {
            const mean = monthMean(m);
            return (
              <div key={m.month} className="flex h-full flex-col items-center gap-2">
                <div className="flex h-full w-full items-end justify-center">
                  <div
                    className="w-full max-w-[14px] rounded-t-[4px]"
                    style={barStyle(mean)}
                    title={`${m.month}: ${mean.toFixed(1)} ${metric === "hours" ? "h ≥14 kt" : "kt (P75)"}`}
                  />
                </div>
                <span className="text-caption font-medium tracking-wide text-ink-soft">{m.month}</span>
              </div>
            );
          })}
        </div>

        {/* sm and up: the full weekly-cluster reading. */}
        <div className="hidden h-[clamp(220px,26vh,320px)] grid-cols-12 items-end gap-4 sm:grid">
          {data.map((m) => (
            <div key={m.month} className="flex h-full flex-col items-center gap-2">
              <div className="flex h-full w-full items-end justify-center gap-[2px]">
                {m.weeks.map((w, i) => (
                  <div
                    key={i}
                    className="w-full max-w-[7px] rounded-t-[3px]"
                    style={barStyle(w)}
                    title={`${m.month} · W${i + 1}: ${w.toFixed(1)} ${metric === "hours" ? "h ≥14 kt" : "kt (P75)"}`}
                  />
                ))}
              </div>
              <span className="text-caption font-medium tracking-wide text-ink-soft">{m.month}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 flex items-center text-caption text-muted">
        <span className="hidden sm:block">4 Balken = 4 Wochen</span>
      </div>
    </div>
  );
}
