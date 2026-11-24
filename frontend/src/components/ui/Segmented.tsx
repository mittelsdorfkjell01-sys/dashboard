import { useRef, type ReactNode } from "react";
import { useStretchIndicator } from "../../lib/useStretchIndicator";

export type SegmentedOption<T extends string> = { id: T; label: ReactNode; ariaLabel?: string };

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
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (id: T) => void;
  /** Accessible name of the group, e.g. "Windfenster". */
  label: string;
  className?: string;
}) {
  const trayRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  useStretchIndicator(trayRef, indicatorRef, value);

  return (
    <div
      ref={trayRef}
      role="group"
      aria-label={label}
      className={`no-scrollbar relative inline-flex max-w-full overflow-x-auto rounded-card bg-band p-1 ${className}`}
    >
      <span
        ref={indicatorRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-1 rounded-card bg-ink opacity-0"
      />
      {options.map((option) => {
        const active = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            aria-label={option.ariaLabel}
            onClick={() => onChange(option.id)}
            className={`relative min-h-11 min-w-11 shrink-0 whitespace-nowrap rounded-card px-3.5 text-ui font-medium transition-colors ${
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
