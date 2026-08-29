import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

type Tone = "white" | "band" | "page";
type Width = "narrow" | "content" | "spotBody" | "wide" | "bleed";
type Pad = "sm" | "md" | "lg";
type MaxWidth = "narrow" | "default" | "wide";

const WIDTH_MAX: Record<Width, string> = {
  narrow: "max-w-[720px]",
  content: "max-w-[1570px]",
  // Spot-detail body only: 10% wider than the regular 1570px content frame.
  // Typography, padding and component gaps remain untouched.
  spotBody: "max-w-[1727px]",
  wide: "max-w-[1440px]",
  bleed: "max-w-none",
};

const MAX_WIDTH_CLASS: Record<MaxWidth, string> = {
  narrow: "max-w-[960px]",
  default: "max-w-[1570px]",
  wide: "max-w-[1440px]",
};

const PAD_Y: Record<Pad, string> = {
  lg: "py-[clamp(3rem,6vw,5rem)]",
  md: "py-[clamp(2.5rem,5vw,4rem)]",
  sm: "py-[clamp(1rem,2.5vw,1.5rem)]",
};

const TONE_BG: Record<Tone, string> = {
  white: "bg-white",
  band: "bg-band",
  page: "bg-page",
};

/**
 * A full-bleed editorial section. `tone` alternates the page rhythm
 * (white / band); `width` sets the reading measure (narrow/content/wide/bleed);
 * vertical padding is fluid.
 *
 * Every section fades/slides in once scrolled into view (Sprint 5: one
 * motion rule for the whole page, applied here instead of per-piece so
 * nothing needs its own stagger). This supersedes an earlier "no
 * visibility-gating reveal" stance — the concern was content disappearing in
 * headless renders / hidden tabs, but `whileInView` + `viewport={{ once:
 * true }}` never removes content from the DOM, it only animates opacity/
 * position on a class toggle, so that risk doesn't apply. `useReducedMotion`
 * disables it via `initial={false}`.
 */
export default function SectionBand({
  id,
  tone = "white",
  width = "content",
  pad = "lg",
  align = "left",
  heading,
  className = "",
  maxWidth,
  children,
}: {
  /** Anchor id for the sticky subnav's jump links. `scroll-mt-24` is applied
   *  alongside it so the target doesn't land underneath the subnav bar. */
  id?: string;
  tone?: Tone;
  width?: Width;
  pad?: Pad;
  align?: "left" | "center";
  heading?: string;
  className?: string;
  /** Override the inner max-width independently of `width`. narrow=960px,
   *  default=1180px, wide=1440px. Falls back to WIDTH_MAX[width] when omitted. */
  maxWidth?: MaxWidth;
  /** Optional — omit for a header-only band (heading with no body), e.g. a
   *  centered heading that precedes a separate full-bleed section. */
  children?: ReactNode;
}) {
  const isBleed = width === "bleed";
  const hasHeader = Boolean(heading);
  const reduce = useReducedMotion();
  const nativeTouch =
    typeof window !== "undefined" &&
    window.matchMedia("(pointer: coarse) and (hover: none)").matches;
  const innerMaxWidth = maxWidth ? MAX_WIDTH_CLASS[maxWidth] : WIDTH_MAX[width];

  return (
    <motion.section
      id={id}
      initial={reduce || nativeTouch ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className={`${id ? "scroll-mt-24" : ""} ${TONE_BG[tone]}`}
    >
      <div
        className={`mx-auto min-w-0 ${innerMaxWidth} ${
          isBleed ? "px-0" : "px-4 sm:px-8"
        } ${PAD_Y[pad]} ${className}`}
      >
        {hasHeader && (
          <div className={align === "center" ? "text-center" : ""}>
            <h2 className="text-sz-28 font-semibold leading-tight text-balance text-ink sm:text-sz-32">{heading}</h2>
          </div>
        )}
        {hasHeader && children != null ? <div className="mt-8">{children}</div> : children}
      </div>
    </motion.section>
  );
}
