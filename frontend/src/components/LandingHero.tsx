import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import HeroImage from "./HeroImage";
import { spotPath } from "../lib/spotRoutes";
import { countryName } from "../lib/flags";
import { ChevronRightIcon, PinIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

const ADVANCE_MS = 10000;

/**
 * Landing hero. Instead of one static photo, this rotates on its own through
 * real spot heroes: each fills the whole hero screen with the same full-bleed
 * `object-cover` crop the page always used (never a 21:9 letterbox), so the
 * background reads as a live window into the catalogue.
 *
 * The reel runs automatically and is deliberately non-interactive — it can't be
 * swiped or clicked. The only control is a small text CTA at the bottom-right
 * that jumps to whichever spot is currently on screen.
 *
 * Falls back to the static brand hero when no spot carries a usable image
 * (e.g. a fresh seed database).
 */
export default function LandingHero({ spots }: { spots: Spot[] }) {
  const reduce = useReducedMotion();
  // Only spots with a real uploaded hero make good full-screen backgrounds;
  // the branded fallback field is for tiles, not a 100vh photo. Prefer the
  // photos an operator curated into the reel (admin Hero tab, image.hero_reel);
  // until any are picked, fall back to every spot with a hero so the reel is
  // never empty. Cap it so we never cycle the entire catalogue.
  const slides = useMemo(() => {
    const withHero = spots.filter((s) => s.hero);
    const curated = withHero.filter((s) => s.heroReel);
    return (curated.length ? curated : withHero).slice(0, 12);
  }, [spots]);
  const count = slides.length;
  const [index, setIndex] = useState(0);

  // Keep the index valid if the slide set shrinks between renders.
  useEffect(() => {
    if (index >= count && count > 0) setIndex(0);
  }, [count, index]);

  // Auto-advance — always on; off only for reduced-motion or a single slide.
  useEffect(() => {
    if (reduce || count <= 1) return;
    const timer = window.setInterval(
      () => setIndex((i) => (i + 1) % count),
      ADVANCE_MS,
    );
    return () => window.clearInterval(timer);
  }, [reduce, count]);

  if (count === 0) {
    return (
      <div className="absolute inset-0 z-0" aria-hidden>
        <HeroImage
          src="/hero-surfwind.jpg"
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-[rgba(30,110,126,0.35)]" />
      </div>
    );
  }

  const current = slides[Math.min(index, count - 1)];
  // Desktop pill carries the region too; mobile shows only the spot name.
  const region = countryName(current.regionCountry ?? undefined) || current.regionName || "";

  return (
    <>
      {/* Background reel — decorative and non-interactive (pointer-events-none),
          so there's nothing to swipe or click; the CTA carries the only link. */}
      <div className="pointer-events-none absolute inset-0 z-0 select-none" aria-hidden>
        {slides.map((s, i) => {
          const active = i === index;
          // Mount only the active slide and its two neighbours (wrap-aware), so
          // the browser preloads what's next without holding 12 full-screen
          // photos in the DOM at once.
          const near =
            active ||
            i === (index + 1) % count ||
            i === (index - 1 + count) % count;
          if (!near) return null;
          return (
            // Ken Burns: the active slide zooms very slowly (1 → 1.08) across its
            // whole dwell while cross-fading to the next — a calm, living window.
            <motion.div
              key={s.id}
              className="absolute inset-0"
              initial={false}
              animate={{ opacity: active ? 1 : 0, scale: active && !reduce ? 1.08 : 1 }}
              transition={{
                opacity: { duration: reduce ? 0.2 : 1.2, ease: "easeInOut" },
                scale: active
                  ? { duration: ADVANCE_MS / 1000, ease: "linear" }
                  : { duration: 1.4, ease: "easeOut" },
              }}
              style={{ transformOrigin: "center" }}
            >
              <HeroImage
                src={s.hero!}
                alt=""
                delivery={s.heroDelivery}
                provider={s.heroCredit?.provider}
                focal={s.heroFocal}
                focalMobile={s.heroFocalMobile}
                className="absolute inset-0 h-full w-full object-cover"
              />
            </motion.div>
          );
        })}
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-[rgba(30,110,126,0.35)]" />
      </div>

      {/* CTA — a compact frosted "location" pill. Names the spot on screen and
          links to it; doubles as the photo's caption. Sits in the same centred
          content column as the header, so its left edge lines up with the
          "Best collection" tagline on desktop. Desktop adds the region; mobile
          keeps just the name. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-8 z-20 sm:bottom-12">
        <div className="mx-auto flex max-w-[1570px] px-4 sm:px-10">
          <Link
            to={spotPath(current)}
            aria-label={`Zum Spot ${current.name}`}
            className="group pointer-events-auto inline-flex max-w-[70vw] items-center gap-2 rounded-2xl border border-white/25 bg-black/25 py-2 pl-3 pr-2.5 text-white shadow-lg backdrop-blur-md transition-colors hover:bg-black/35"
          >
            <PinIcon className="shrink-0 text-[16px]" />
            <span className="min-w-0 truncate text-[13px] font-medium">
              {current.name}
              {region && <span className="hidden font-normal text-white/75 sm:inline"> · {region}</span>}
            </span>
            <ChevronRightIcon className="shrink-0 text-[15px] transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </>
  );
}
