type WordmarkSize = "sm" | "md" | "lg" | "xl" | "dock";

/**
 * Atom: the "surfwind data" wordmark — the single brand lockup used everywhere
 * (landing hero, shared header, admin). Replaces the old inconsistent mix of
 * this two-tone display wordmark and the plain "SpotInfo" text.
 *
 * Orange "surfwind" + neutral "data" in the MADE Mountain display face (see the
 * `.wordmark` base class). `tag` renders a small suffix pill, e.g. "Admin".
 */
const SIZE: Record<WordmarkSize, { brand: string; data: string }> = {
  sm: { brand: "text-lead", data: "text-micro" },
  md: { brand: "text-heading sm:text-heading", data: "text-ui sm:text-body" },
  lg: { brand: "text-heading-lg", data: "text-body" },
  xl: { brand: "text-heading-lg sm:text-display-lg", data: "text-body sm:text-heading" },
  // Landing header target size. It matches the former visual scale without
  // keeping the text permanently transformed after the glide completes.
  dock: { brand: "text-lead sm:text-heading", data: "text-micro sm:text-body" },
};

export default function Wordmark({
  size = "md",
  tag,
  className = "",
  animateSize = false,
}: {
  size?: WordmarkSize;
  tag?: string;
  className?: string;
  animateSize?: boolean;
}) {
  const s = SIZE[size];
  const sizeTransition = animateSize
    ? "transition-[font-size] duration-[820ms] ease-brand motion-reduce:transition-none"
    : "";
  return (
    <span className={`inline-flex items-baseline leading-none ${className}`}>
      <span className={`wordmark ${s.brand} ${sizeTransition} text-orange`}>surfwind</span>
      <span className={`wordmark ml-1.5 align-baseline ${s.data} ${sizeTransition} text-ink`}>
        data
      </span>
      {tag && (
        <span className="ml-2 self-center rounded-2xl bg-ink/5 px-2 py-0.5 text-caption font-medium text-muted">
          {tag}
        </span>
      )}
    </span>
  );
}
