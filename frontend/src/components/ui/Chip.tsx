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
      className={`rounded-2xl px-3.5 py-2 text-label font-medium transition-colors ${
        active
          ? "bg-teal text-white"
          : "bg-white text-ink ring-1 ring-line hover:ring-teal/40"
      } ${className}`}
    >
      {children}
    </button>
  );
}
