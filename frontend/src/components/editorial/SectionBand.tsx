import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

type Tone = "white" | "band";
type Width = "narrow" | "content" | "wide" | "bleed";
type Pad = "md" | "lg";

const WIDTH_MAX: Record<Width, string> = {
  narrow: "max-w-[720px]",
  content: "max-w-[1180px]",
  wide: "max-w-[1440px]",
  bleed: "max-w-none",
};

const PAD_Y: Record<Pad, string> = {
  lg: "py-[clamp(4rem,9vw,8rem)]",
  md: "py-[clamp(2.5rem,5vw,4rem)]",
};

const TONE_BG: Record<Tone, string> = {
  white: "bg-white",
  band: "bg-band",
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
  kicker,
  heading,
  intro,
  className = "",
  children,
}: {
  /** Anchor id for the sticky subnav's jump links. `scroll-mt-24` is applied
   *  alongside it so the target doesn't land underneath the subnav bar. */
  id?: string;
  tone?: Tone;
  width?: Width;
  pad?: Pad;
  align?: "left" | "center";
  kicker?: string;
  heading?: string;
  intro?: string;
  className?: string;
  /** Optional — omit for a header-only band (kicker/heading/intro with no
   *  body), e.g. a centered intro that precedes a separate full-bleed section. */
  children?: ReactNode;
}) {
  const isBleed = width === "bleed";
  const hasHeader = Boolean(kicker || heading || intro);
  const reduce = useReducedMotion();

  return (
    <motion.section
      id={id}
      initial={reduce ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className={`${id ? "scroll-mt-24" : ""} ${TONE_BG[tone]}`}
    >
      <div
        className={`mx-auto ${WIDTH_MAX[width]} ${
          isBleed ? "px-0" : "px-4 sm:px-8"
        } ${PAD_Y[pad]} ${className}`}
      >
        {hasHeader && (
          <div className={align === "center" ? "text-center" : ""}>
            {kicker && (
              <p className="text-caption font-medium uppercase tracking-[0.18em] text-teal">
                {kicker}
              </p>
            )}
            {heading && (
              <h2 className={`text-display-2 font-semibold text-balance text-ink ${kicker ? "mt-2" : ""}`}>
                {heading}
              </h2>
            )}
            {intro && (
              <p
                className={`mt-4 max-w-[60ch] text-body text-ink-soft ${
                  align === "center" ? "mx-auto" : ""
                }`}
              >
                {intro}
              </p>
            )}
          </div>
        )}
        {hasHeader && children != null ? <div className="mt-8">{children}</div> : children}
      </div>
    </motion.section>
  );
}
