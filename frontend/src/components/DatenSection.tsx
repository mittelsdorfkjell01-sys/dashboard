import type { ReactNode } from "react";

/**
 * Section chassis for the Daten tab — the weather-instrument half of the
 * page, a different visual language from the Info tab's `SectionBand`:
 * no radius, no shadow, no card, left-aligned and full-width instead of a
 * centered 1180px measure, an 8–12px rhythm instead of 32–48px. Section
 * labels here are labels, not headings — `data-label`, uppercase, muted,
 * never the editorial `<h2>` treatment.
 */
export default function DatenSection({
  label,
  className = "",
  children,
}: {
  label?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`min-w-0 max-w-full overflow-hidden border-t border-line px-4 py-3 sm:px-8 ${className}`}>
      {label && <p className="mb-3 text-data-label uppercase text-muted">{label}</p>}
      <div className="min-w-0 max-w-full">{children}</div>
    </section>
  );
}
