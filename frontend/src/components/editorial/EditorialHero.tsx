import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import type { ReactNode } from "react";
import HeroImage from "../HeroImage";
import ImageCredit from "../ImageCredit";
import { hasCredit, type CreditSource } from "../../lib/imageCredit";

/**
 * Full-bleed editorial hero. Two states, both deliberately designed:
 *  • with photo → cinematic HeroImage, focal-point aware, scroll parallax.
 *  • without photo → a brand colour field (.editorial-hero-fallback) with a
 *    faint animated wind motif, so a missing image never reads as empty/broken.
 *
 * `children` is a top slot (e.g. a back pill) tucked below the floating header.
 * `title`, when given, renders as the page's single <h1> in Poppins display
 * size (not the wordmark face) — omit it when the <h1> lives elsewhere on the
 * page (the spot page's SpotHeaderCard owns it instead).
 */
export default function EditorialHero({
  image,
  focal,
  focalMobile,
  alt,
  kicker,
  title,
  meta,
  credit,
  delivery,
  children,
  parallax = true,
  frameClassName = "aspect-video sm:aspect-[21/9]",
  onImageClick,
}: {
  image?: string | null;
  focal?: { x: number; y: number } | null;
  focalMobile?: { x: number; y: number } | null;
  alt: string;
  kicker?: ReactNode;
  title?: string;
  meta?: ReactNode;
  /** Attribution source — a spot/region `image` object, a gallery row or a
   *  hand-built shape. Stock heroes, Commons imports and community photos with
   *  an Instagram tag all render through the same line; there is no per-source
   *  special case. */
  credit?: CreditSource | null;
  /** Passed through to HeroImage so a hotlinked photo is resized by its own
   *  provider CDN instead of downloading a 6000px original. */
  delivery?: "hotlinked" | "hosted";
  children?: ReactNode;
  /** Scroll parallax. Off inside the admin media picker, where the hero is a
   *  preview in a fixed frame and page scroll is locked — the drift would be
   *  meaningless there. */
  parallax?: boolean;
  /** Height of the hero frame. The page hero keeps the aspect-ratio default
   *  (21:9 desktop / 16:9 mobile); the picker passes fixed desktop/mobile
   *  crop ratios so an operator sees the real proportions before adopting. */
  frameClassName?: string;
  /** Picking a focal point in the admin preview. Absent on the public site,
   *  where the hero is not interactive. */
  onImageClick?: (event: React.MouseEvent<HTMLDivElement>) => void;
}) {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const still = reduce || !parallax;

  // Image parallax: the wrapper is pre-inflated by the max travel distance
  // (60px top + 60px bottom = the 120px range the spec calls for) so the
  // translate never uncovers the dark background at the top edge — a literal
  // [0,120] range would open exactly that gap, since the image sits flush
  // with the container at rest.
  const imageY = useTransform(scrollY, [0, 600], [-60, 60]);
  const titleY = useTransform(scrollY, [0, 400], [0, -40]);

  return (
    <section className={`${frameClassName} relative w-full overflow-hidden bg-ink`}>
      {image ? (
        <motion.div
          className={`absolute inset-x-0 ${onImageClick ? "cursor-crosshair" : ""}`}
          style={{ top: still ? 0 : -60, bottom: still ? 0 : -60, y: still ? 0 : imageY }}
          onClick={onImageClick}
        >
          <HeroImage
            src={image}
            alt={alt}
            focal={focal}
            focalMobile={focalMobile}
            delivery={delivery}
            provider={credit?.provider}
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

      {/* scrim: bottom layer only when a title/meta sits on the hero (region
          pages). The spot page moved the name into the column below, so the
          hero stays as bright as the original photo — no bottom darkening. */}
      {(title || meta || kicker) && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(to top, rgba(0,0,0,.72) 0%, rgba(0,0,0,.45) 22%, rgba(0,0,0,.12) 48%, transparent 70%)",
          }}
        />
      )}
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
          <motion.div style={{ y: still ? 0 : titleY }}>
            {title && <h1 className="text-display-1 font-bold text-white text-balance">{title}</h1>}
            {meta && <div className="mt-3 text-body font-medium text-white/90">{meta}</div>}
          </motion.div>
        </div>
      </div>

      {/* Attribution — same corner, same style, whatever the photo's origin. */}
      {hasCredit(credit ?? null) && (
        <div className="pointer-events-none absolute bottom-4 right-4 z-10 text-caption tracking-wide text-white/55 sm:bottom-6 sm:right-8">
          <ImageCredit source={credit ?? null} className="pointer-events-auto" />
        </div>
      )}
    </section>
  );
}
