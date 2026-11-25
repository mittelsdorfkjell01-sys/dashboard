/** "Start year" control for the climatology window, drawn as one block per
 *  year (chosen 2026-11-24, "Jahresblöcke"). Only the start moves — how far
 *  into the past; the end is always the present. The years inside the window
 *  are filled, so the number of years that feed the figures is visible at a
 *  glance. Tapping or dragging anywhere on the row sets the start; the row is
 *  one focusable role="slider" with arrow, Page and Home/End keys.
 *
 *  Motion: when the start changes, the blocks fill or empty as a short wave
 *  running out from the new start (12 ms per block, at most 14 steps), and
 *  the first block of the window stands taller, settling with the switch's
 *  slight overshoot. Reduced motion: colours change at once, no wave.
 *  The chosen window is re-aggregated server-side from stored per-year data. */

import { useRef, type KeyboardEvent, type PointerEvent } from "react";

export const DEFAULT_MIN_SPAN = 5; // shortest window the slider allows

interface Props {
  fromYear: number;
  min: number;
  max: number; // present (fixed end of the window)
  onChange: (fromYear: number) => void;
  minSpan?: number;
  disabled?: boolean;
}

const WAVE_STEP_MS = 12;
const WAVE_MAX_STEPS = 14;

export default function YearRangeSlider({ fromYear, min, max, onChange, minSpan = DEFAULT_MIN_SPAN, disabled }: Props) {
  const rowRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  // The start before the latest change: the wave runs out from the new start
  // across the blocks that actually changed.
  const previous = useRef(fromYear);
  const last = useRef(fromYear);
  if (last.current !== fromYear) {
    previous.current = last.current;
    last.current = fromYear;
  }

  const count = Math.max(1, max - min + 1);
  const maxFrom = max - Math.min(minSpan, max - min); // latest start that keeps the minimum window
  const years = Array.from({ length: count }, (_, i) => min + i);

  const apply = (year: number) => onChange(Math.min(Math.max(year, min), maxFrom));

  const yearAt = (clientX: number): number | null => {
    const el = rowRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return null;
    const ratio = Math.min(0.9999, Math.max(0, (clientX - rect.left) / rect.width));
    return min + Math.floor(ratio * count);
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    const year = yearAt(e.clientX);
    if (year == null) return;
    dragging.current = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    apply(year);
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (disabled || !dragging.current || e.buttons !== 1) return;
    const year = yearAt(e.clientX);
    if (year != null && year !== fromYear) apply(year);
  };
  const endDrag = () => { dragging.current = false; };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = e.key === "Home" ? min
      : e.key === "End" ? maxFrom
      : e.key === "PageDown" ? fromYear - 5
      : e.key === "PageUp" ? fromYear + 5
      : e.key === "ArrowLeft" || e.key === "ArrowDown" ? fromYear - 1
      : e.key === "ArrowRight" || e.key === "ArrowUp" ? fromYear + 1
      : null;
    if (next == null) return;
    e.preventDefault();
    apply(next);
  };

  // Year labels under the row: the ends plus every round decade/half-decade
  // that has room.
  const marks = years.filter((y) => y === min || y === max || (y % 5 === 0 && y - min >= 3 && max - y >= 3));
  const changedFrom = Math.min(previous.current, fromYear);
  const changedTo = Math.max(previous.current, fromYear);

  return (
    <div className="w-full">
      <div
        ref={rowRef}
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label="Erstes Jahr"
        aria-valuemin={min}
        aria-valuemax={maxFrom}
        aria-valuenow={fromYear}
        aria-valuetext={`${fromYear} bis ${max}, ${max - fromYear + 1} Jahre`}
        aria-disabled={disabled || undefined}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        // 14px blocks (half height, 2026-11-24) inside a 44px tap row; the
        // negative margin keeps the row's layout footprint at the blocks.
        className={`-my-[15px] grid h-11 touch-none select-none items-center gap-0.5 rounded-[6px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ${disabled ? "opacity-50" : "cursor-pointer"}`}
        style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }}
      >
        {years.map((year) => {
          const inside = year >= fromYear;
          const edge = year === fromYear;
          // Only blocks between the old and the new start change colour; they
          // do so one after another, outward from the new start.
          const changed = year >= changedFrom && year < changedTo;
          const delay = changed ? Math.min(Math.abs(year - fromYear), WAVE_MAX_STEPS) * WAVE_STEP_MS : 0;
          return (
            <span
              key={year}
              aria-hidden="true"
              className={`h-3.5 rounded-[2px] transition-[background-color,transform] duration-fast ease-switch motion-reduce:transition-none ${
                inside ? "bg-teal" : "bg-line"
              } ${edge ? "scale-y-[1.35]" : "scale-y-100"}`}
              style={{ transitionDelay: `${delay}ms, 0ms` }}
            />
          );
        })}
      </div>
      <div className="relative mt-1.5 h-4 text-data-caption tabular-nums text-muted" aria-hidden="true">
        {marks.map((year) => {
          const left = ((year - min) / count) * 100;
          return year === max ? (
            <span key={year} className="absolute right-0">{year}</span>
          ) : (
            <span key={year} className="absolute" style={{ left: `${left}%` }}>{year}</span>
          );
        })}
      </div>
    </div>
  );
}
