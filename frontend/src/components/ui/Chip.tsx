import type { ReactNode } from "react";

/**
 * Atom: a pill-style toggle used for single- and multi-select filter/category
 * chips. Consolidates the two identical copies that previously lived in
 * SortDropdown and AdminSpotForm. Exposes checkbox semantics for screen readers.
 */
export default function Chip({
  active,
  onClick,
  children,
  className = "",
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={active}
      onClick={onClick}
      className={`rounded-2xl px-3.5 py-2 text-ui font-medium transition-colors ${
        active
          ? // white on the single deep-blue teal (#1C4E63) clears AA in both
            // themes (9:1); teal no longer lightens in dark mode, so this is safe
            "bg-teal text-white"
          : "bg-surface text-ink ring-1 ring-line hover:ring-accent/40"
      } ${className}`}
    >
      {children}
    </button>
  );
}
