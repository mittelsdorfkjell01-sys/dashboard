type WordmarkSize = "sm" | "md" | "lg" | "xl";

/**
 * Atom: the "surfwind data" wordmark — the single brand lockup used everywhere
 * (landing hero, shared header, admin). Replaces the old inconsistent mix of
 * this two-tone display wordmark and the plain "SpotInfo" text.
 *
 * Orange "surfwind" + teal "data" in the MADE Mountain display face (see the
 * `.wordmark` base class). `tag` renders a small suffix pill, e.g. "Admin".
 */
const SIZE: Record<WordmarkSize, { brand: string; data: string }> = {
  sm: { brand: "text-sz-18", data: "text-sz-10" },
  md: { brand: "text-sz-26 sm:text-sz-30", data: "text-label sm:text-body" },
  lg: { brand: "text-sz-32", data: "text-sz-16" },
  xl: { brand: "text-sz-34 sm:text-sz-58", data: "text-sz-16 sm:text-sz-28" },
};

export default function Wordmark({
  size = "md",
  tag,
  className = "",
}: {
  size?: WordmarkSize;
  tag?: string;
  className?: string;
}) {
  const s = SIZE[size];
  return (
    <span className={`inline-flex items-baseline leading-none ${className}`}>
      <span className={`wordmark ${s.brand} text-orange`}>surfwind</span>
      <span className={`wordmark ml-1.5 align-baseline ${s.data} text-teal`}>
        data
      </span>
      {tag && (
        <span className="ml-2 self-center rounded-2xl bg-ink/5 px-2 py-0.5 text-sz-11 font-medium text-muted">
          {tag}
        </span>
      )}
    </span>
  );
}
