import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import type { ReactNode } from "react";
import HeroImage from "../HeroImage";

/**
 * Full-bleed editorial hero. Two states, both deliberately designed:
 *  • with photo → cinematic HeroImage, focal-point aware, scroll parallax.
 *  • without photo → a brand colour field (.editorial-hero-fallback) with a
 *    faint animated wind motif, so a missing image never reads as empty/broken.
 *
 * `children` is a top slot (e.g. a back pill) tucked below the floating header.
 * `title`, when given, renders as the page's single <h1> in Poppins display
 * size (not the wordmark face) — omit it when the <h1> lives elsewhere on the
 * page (the spot page's SpotIdentityCard owns it instead).
 */
export default function EditorialHero({
  image,
  focal,
  alt,
  kicker,
  title,
  meta,
  credit,
  children,
}: {
  image?: string | null;
  focal?: { x: number; y: number } | null;
  alt: string;
  kicker?: ReactNode;
  title?: string;
  meta?: ReactNode;
  /** Photographer name / Instagram tag, shown small in the hero's bottom
   *  corner. Plain text only — there's no credit-URL field in the data model
   *  yet, so this never renders as a link. */
  credit?: string;
  children?: ReactNode;
}) {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();

  // Image parallax: the wrapper is pre-inflated by the max travel distance
  // (60px top + 60px bottom = the 120px range the spec calls for) so the
  // translate never uncovers the dark background at the top edge — a literal
  // [0,120] range would open exactly that gap, since the image sits flush
  // with the container at rest.
  const imageY = useTransform(scrollY, [0, 600], [-60, 60]);
  const titleY = useTransform(scrollY, [0, 400], [0, -40]);

  return (
    <section className="hero-h relative w-full overflow-hidden bg-ink">
      {image ? (
        <motion.div
          className="absolute inset-x-0"
          style={{ top: -60, bottom: -60, y: reduce ? 0 : imageY }}
        >
          <HeroImage
            src={image}
            alt={alt}
            focal={focal}
            className="h-full w-full object-cover"
          />
        </motion.div>
      ) : (
        <div className="editorial-hero-fallback absolute inset-0" role="img" aria-label={alt}>
          <div aria-hidden className="pointer-events-none absolute inset-0 opacity-60">
            {Array.from({ length: 6 }).map((_, i) => (
              <span
                key={i}
                className="swd-wind-streak absolute block h-24 w-[2px] rounded-full bg-white/40"
                style={{ left: `${12 + i * 14}%`, top: "18%", animationDelay: `${i * 0.4}s` }}
              />
            ))}
          </div>
        </div>
      )}

      {/* scrim: bottom layer for title legibility, top layer for the header */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(to top, rgba(0,0,0,.72) 0%, rgba(0,0,0,.45) 22%, rgba(0,0,0,.12) 48%, transparent 70%)",
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-40"
        style={{ backgroundImage: "linear-gradient(to bottom, rgba(0,0,0,.35), transparent)" }}
      />

      {/* top slot (back pill etc.) */}
      {children && (
        <div className="pointer-events-none absolute inset-x-0 top-[88px] z-20 sm:top-[120px]">
          <div className="mx-auto flex max-w-[1180px] px-4 sm:px-8">{children}</div>
        </div>
      )}

      {/* headline block — the kicker (region name) stays put; only the title/
          meta get the parallax nudge, so the region name never drifts */}
      <div className="absolute inset-x-0 bottom-0 z-10">
        <div className="mx-auto max-w-[1180px] px-4 pb-10 sm:px-8 sm:pb-14">
          {kicker && (
            <div className="mb-3 text-label font-semibold uppercase tracking-[0.16em] text-white/85">
              {kicker}
            </div>
          )}
          <motion.div style={{ y: reduce ? 0 : titleY }}>
            {title && <h1 className="text-display-1 font-bold text-white text-balance">{title}</h1>}
            {meta && <div className="mt-3 text-body font-medium text-white/90">{meta}</div>}
          </motion.div>
        </div>
      </div>

      {/* credit */}
      {credit && (
        <div className="pointer-events-none absolute bottom-4 right-4 z-10 text-caption tracking-wide text-white/55 sm:bottom-6 sm:right-8">
          {credit}
        </div>
      )}

      {/* scroll hint — signals there's more below; a longform cue, not a UI control */}
      <div aria-hidden="true" className="absolute inset-x-0 bottom-3 z-10 flex justify-center">
        <div className="relative h-12 w-px overflow-hidden bg-white/40">
          {!reduce && (
            <span className="animate-swd-scroll-hint absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-transparent via-white to-transparent" />
          )}
        </div>
      </div>
    </section>
  );
}
