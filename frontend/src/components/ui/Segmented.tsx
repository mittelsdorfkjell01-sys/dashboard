import type { ReactNode } from "react";

export type SegmentedOption<T extends string> = { id: T; label: ReactNode; ariaLabel?: string };

/**
 * Atom: segmented control — one choice out of a few, switched in place (unit,
 * time window, view). A band tray holding pressed-state buttons; the active
 * segment is the inverted ink chip, so it reads in both themes and on the
 * always-dark Daten canvas. Each segment is a 44px target.
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
  return (
    <div
      role="group"
      aria-label={label}
      className={`no-scrollbar inline-flex max-w-full overflow-x-auto rounded-card bg-band p-1 ${className}`}
    >
      {options.map((option) => {
        const active = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            aria-label={option.ariaLabel}
            onClick={() => onChange(option.id)}
            className={`min-h-11 min-w-11 shrink-0 whitespace-nowrap rounded-card px-3.5 text-ui font-medium transition-colors ${
              active ? "bg-ink text-surface" : "text-muted hover:text-ink"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
