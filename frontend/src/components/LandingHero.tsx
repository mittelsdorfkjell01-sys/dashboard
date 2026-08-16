import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useReducedMotion } from "framer-motion";
import HeroImage from "./HeroImage";
import { spotPath } from "../lib/spotRoutes";
import { ChevronRightIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

const ADVANCE_MS = 6000;

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
  // the branded fallback field is for tiles, not a 100vh photo. Cap the reel so
  // we never cycle through the entire catalogue.
  const slides = useMemo(() => spots.filter((s) => s.hero).slice(0, 12), [spots]);
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
            <div
              key={s.id}
              className={`absolute inset-0 transition-opacity duration-700 ease-out ${
                active ? "opacity-100" : "opacity-0"
              }`}
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
            </div>
          );
        })}
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-[rgba(30,110,126,0.35)]" />
      </div>

      {/* CTA — a small text link (no button chrome), jumps to the spot on screen. */}
      <Link
        to={spotPath(current)}
        className="group absolute bottom-4 right-4 z-20 inline-flex items-center gap-0.5 text-[13px] font-medium text-white/90 [text-shadow:0_1px_3px_rgba(0,0,0,0.5)] transition-colors hover:text-white sm:bottom-6 sm:right-6"
      >
        Spot herausfinden
        <ChevronRightIcon className="text-[14px] transition-transform group-hover:translate-x-0.5" />
      </Link>
    </>
  );
}
