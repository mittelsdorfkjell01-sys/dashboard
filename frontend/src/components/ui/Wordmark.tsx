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
  sm: { brand: "text-[18px]", data: "text-[10px]" },
  md: { brand: "text-[26px] sm:text-[30px]", data: "text-[13px] sm:text-[15px]" },
  lg: { brand: "text-[32px]", data: "text-[16px]" },
  xl: { brand: "text-[46px] sm:text-[58px]", data: "text-[22px] sm:text-[28px]" },
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
        <span className="ml-2 self-center rounded-2xl bg-ink/5 px-2 py-0.5 text-[11px] font-medium text-muted">
          {tag}
        </span>
      )}
    </span>
  );
}
