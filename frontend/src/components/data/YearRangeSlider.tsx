/** Single-handle "start year" slider for the climatology window. Only the start
 *  (how far into the past) moves; the end is always the present. The WHOLE track
 *  responds to click/drag (the handle jumps to the pointer), so you never have to
 *  hit a tiny thumb, and it is a focusable role="slider" with arrow-key support.
 *  The chosen window is re-aggregated server-side from stored per-year data.
 *
 *  Pointer math is zoom-invariant (clientX and rect.width scale together under
 *  the Daten page's lg:zoom-0.85), so no divide-by-zoom is needed. */

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

export default function YearRangeSlider({ fromYear, min, max, onChange, minSpan = DEFAULT_MIN_SPAN, disabled }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const span = Math.max(1, max - min);
  const maxFrom = max - Math.min(minSpan, max - min); // latest start that keeps the minimum window
  const percent = ((fromYear - min) / span) * 100;

  const apply = (year: number) => onChange(Math.min(Math.max(year, min), maxFrom));

  const yearAt = (clientX: number): number | null => {
    const el = trackRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return null;
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.round(min + ratio * span);
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
    if (year != null) apply(year);
  };
  const endDrag = () => { dragging.current = false; };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = e.key === "Home" ? min
      : e.key === "End" ? maxFrom
      : e.key === "ArrowLeft" || e.key === "ArrowDown" ? fromYear - 1
      : e.key === "ArrowRight" || e.key === "ArrowUp" ? fromYear + 1
      : null;
    if (next == null) return;
    e.preventDefault();
    apply(next);
  };

  return (
    <div className="w-full">
      <div
        ref={trackRef}
        className={`relative h-6 touch-none select-none ${disabled ? "" : "cursor-pointer"}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <div className="pointer-events-none absolute left-0 right-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-line" />
        {/* Selected window runs from the handle to the present (right edge). */}
        <div className="pointer-events-none absolute top-1/2 right-0 h-1.5 -translate-y-1/2 rounded-full bg-teal" style={{ left: `${percent}%` }} />
        <div
          role="slider"
          tabIndex={disabled ? -1 : 0}
          aria-label="Erstes Jahr"
          aria-valuemin={min}
          aria-valuemax={maxFrom}
          aria-valuenow={fromYear}
          aria-valuetext={`ab ${fromYear}`}
          aria-disabled={disabled || undefined}
          onKeyDown={onKeyDown}
          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-surface bg-teal shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
          style={{ left: `${percent}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-data-caption text-muted">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
