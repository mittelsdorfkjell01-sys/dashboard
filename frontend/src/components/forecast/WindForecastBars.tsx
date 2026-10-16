import { useMemo, type ReactNode } from "react";
import { windColor } from "../../lib/windScale";
import { windValue } from "../../lib/units";
import type { WindUnit } from "../../lib/units";

/**
 * The least a slot must carry to be drawn as a wind bar. A
 * `NormalizedForecastHour` satisfies it, and so does a field sample mapped
 * onto it — the chart does not care where the hour came from.
 */
export type WindBarSlot = {
  utcKey: string;
  /** "HH:MM" local; only the hour is printed. */
  localTime: string;
  localHour: number;
  wind?: number | null;
  gust?: number | null;
};

/** Default column pitch, bar width and band height of one wind hour. */
export const WIND_BAR_COL_W = 13;
const BAR_W = 10;
const BAND_H = 31;

function fade(hex: string, alpha = 0.45): string {
  const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex);
  if (!m) return hex;
  const [r, g, b] = [m[1], m[2], m[3]].map((h) => parseInt(h, 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * The hourly wind bars: a faded gust cap behind, the solid wind bar in front,
 * both tinted by the shared wind scale, with the hour printed every second
 * column. One row of buttons — the caller owns the scroll container.
 *
 * Shared on purpose: the Spot-Daten map overlay and the wind map's spot
 * forecast must read as the same chart, so there is one implementation of what
 * a wind bar looks like rather than two that drift apart.
 */
export default function WindForecastBars<Slot extends WindBarSlot>({
  slots,
  selectedUtcKey,
  onSelect,
  windUnit,
  renderAbove,
  colWidth = WIND_BAR_COL_W,
}: {
  slots: Slot[];
  selectedUtcKey: string | null;
  onSelect: (utcKey: string) => void;
  windUnit: WindUnit;
  /** Extra cells stacked above the bar, e.g. temperature and wave height. */
  renderAbove?: (slot: Slot) => ReactNode;
  /** Wider columns when `renderAbove` adds values that need room to read. The
   *  bars keep their width, so only the spacing changes. */
  colWidth?: number;
}) {
  const windMax = useMemo(() => {
    let max = 0;
    for (const slot of slots) {
      if (slot.wind != null && slot.wind > max) max = slot.wind;
      if (slot.gust != null && slot.gust > max) max = slot.gust;
    }
    return Math.max(max, 5);
  }, [slots]);

  return (
    <div className="flex w-max items-end">
      {slots.map((slot) => {
        const selected = slot.utcKey === selectedUtcKey;
        const wind = slot.wind ?? null;
        const gust = slot.gust ?? wind ?? null;
        const windH = wind == null ? 0 : Math.max(3, (wind / windMax) * BAND_H);
        const gustH = wind == null ? 0 : Math.max(windH, ((gust ?? wind) / windMax) * BAND_H);
        const showTime = slot.localHour % 2 === 0;
        return (
          <button
            key={slot.utcKey}
            type="button"
            data-selected={selected}
            aria-pressed={selected}
            aria-label={`${slot.localTime} Uhr${wind == null ? "" : ` — ${windValue(wind, windUnit)} ${windUnit}`}`}
            onClick={() => onSelect(slot.utcKey)}
            className={`flex shrink-0 flex-col items-center rounded-card ${selected ? "bg-white/10" : ""} focus-visible:outline-none`}
            style={{ width: colWidth }}
          >
            {renderAbove?.(slot)}
            <span className="flex items-end" style={{ height: BAND_H }}>
              {wind != null && (
                <span data-wind-bar="gust" className="relative rounded-card" style={{ width: BAR_W, height: gustH, background: fade(windColor(wind)) }}>
                  <span data-wind-bar="wind" className="absolute inset-x-0 bottom-0 rounded-card" style={{ height: windH, background: windColor(wind) }} />
                </span>
              )}
            </span>
            <span className="mt-1 leading-none tabular-nums text-on-photo-muted text-micro" style={{ height: 10 }}>
              {showTime ? slot.localTime.slice(0, 2) : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}
