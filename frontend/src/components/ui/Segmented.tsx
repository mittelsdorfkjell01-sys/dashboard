import { useRef, useState, type ReactNode } from "react";
import { useStretchIndicator } from "../../lib/useStretchIndicator";

export type SegmentedOption<T extends string> = { id: T; label: ReactNode; ariaLabel?: string; title?: string };

/**
 * Atom: segmented control — one choice out of a few, switched in place (unit,
 * time window, view). A band tray holding pressed-state buttons; the active
 * segment is the inverted ink chip, so it reads in both themes and on the
 * always-dark Daten canvas. Each segment is a 44px target.
 *
 * Motion: the ink surface is one element that stretches over to the pressed
 * segment (see useStretchIndicator) instead of jumping.
 *
 * Semantics: a labelled group of toggle buttons (`aria-pressed`) — the
 * pattern screen readers announce clearly for an immediate-effect switch.
 */
export default function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  className = "",
  size = "md",
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (id: T) => void;
  /** Accessible name of the group, e.g. "Windfenster". */
  label: string;
  className?: string;
  /** "sm": half-height segments (28px) for dense instrument headers; the
   *  tap target still extends to 44px above and below the segment. Since
   *  2026-11-25 it is the Daten tab's switch: the Windmonate corners (10px
   *  segments in the 14px tray) and the motion of the menu's language
   *  switch — the surface travels on the overshooting switch curve and,
   *  while a segment is held, leans toward the side it will move to. */
  size?: "md" | "sm";
}) {
  const small = size === "sm";
  const trayRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  useStretchIndicator(trayRef, indicatorRef, value, small ? "switch" : "stretch");
  const [lean, setLean] = useState<"left" | "right" | null>(null);
  const activeIndex = options.findIndex((option) => option.id === value);

  return (
    <div
      ref={trayRef}
      role="group"
      aria-label={label}
      className={`no-scrollbar relative inline-flex max-w-full rounded-card bg-band ${small ? "gap-0.5 p-0.5" : "overflow-x-auto p-1"} ${className}`}
      onPointerUp={() => setLean(null)}
      onPointerLeave={() => setLean(null)}
      onPointerCancel={() => setLean(null)}
    >
      <span
        ref={indicatorRef}
        aria-hidden="true"
        className={`pointer-events-none absolute bg-ink opacity-0 ${small ? "inset-y-0.5 rounded-[10px]" : "inset-y-1 rounded-card"} ${
          lean === "right" ? "-mr-1" : lean === "left" ? "-ml-1" : ""
        }`}
      />
      {options.map((option, index) => {
        const active = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            aria-label={option.ariaLabel}
            title={option.title}
            onPointerDown={() => {
              if (small && !active && activeIndex >= 0) setLean(index > activeIndex ? "right" : "left");
            }}
            onClick={() => onChange(option.id)}
            className={`relative shrink-0 whitespace-nowrap font-medium transition-colors ${small ? "rounded-[10px]" : "rounded-card"} ${
              small
                ? "grid min-h-7 min-w-8 place-items-center px-2.5 text-caption before:absolute before:inset-x-0 before:-inset-y-2 before:content-['']"
                : "min-h-11 min-w-11 px-3.5 text-ui"
            } ${
              active ? "text-surface" : "text-muted hover:text-ink"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
