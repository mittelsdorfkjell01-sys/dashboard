import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useReducedMotion } from "framer-motion";
import HeroImage from "./HeroImage";
import { spotPath } from "../lib/spotRoutes";
import { ChevronRightIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

const ADVANCE_MS = 6000;
const SWIPE_THRESHOLD = 48; // px of horizontal travel before a swipe counts

/**
 * Landing hero. Instead of one static photo, this rotates through real spot
 * heroes: each fills the whole hero screen with the same full-bleed
 * `object-cover` crop the page always used (never a 21:9 letterbox), so the
 * background reads as a live window into the catalogue. Auto-advances, can be
 * swiped left/right, and carries a bottom-right CTA that jumps to whichever
 * spot is currently on screen.
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
  const [paused, setPaused] = useState(false);

  // Keep the index valid if the slide set shrinks between renders.
  useEffect(() => {
    if (index >= count && count > 0) setIndex(0);
  }, [count, index]);

  const go = (delta: number) => {
    if (count === 0) return;
    setIndex((i) => (i + delta + count) % count);
  };

  // Auto-advance — paused while the visitor is interacting, and off entirely
  // for reduced-motion or a single slide.
  useEffect(() => {
    if (paused || reduce || count <= 1) return;
    const timer = window.setInterval(
      () => setIndex((i) => (i + 1) % count),
      ADVANCE_MS,
    );
    return () => window.clearInterval(timer);
  }, [paused, reduce, count]);

  // Pointer swipe. A baseline gesture only — the visual motion is a crossfade;
  // richer transitions can layer on top of this index model later.
  const startX = useRef<number | null>(null);
  const endSwipe = (clientX: number | null) => {
    if (startX.current != null && clientX != null) {
      const dx = clientX - startX.current;
      if (Math.abs(dx) > SWIPE_THRESHOLD) go(dx < 0 ? 1 : -1);
    }
    startX.current = null;
    setPaused(false);
  };

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
      {/* Background reel — decorative (aria-hidden); the CTA carries the link. */}
      <div
        className="absolute inset-0 z-0 touch-pan-y select-none"
        aria-hidden
        onPointerDown={(e) => {
          startX.current = e.clientX;
          setPaused(true);
        }}
        onPointerUp={(e) => endSwipe(e.clientX)}
        onPointerCancel={() => endSwipe(null)}
      >
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

      {/* Progress dots — also a direct jump to any slide. */}
      {count > 1 && (
        <div className="absolute bottom-6 left-1/2 z-20 flex -translate-x-1/2 gap-1.5 sm:bottom-8">
          {slides.map((s, i) => (
            <button
              key={s.id}
              type="button"
              aria-label={`Zu Bild ${i + 1}`}
              aria-current={i === index}
              onClick={() => setIndex(i)}
              className={`h-1.5 rounded-full transition-all ${
                i === index ? "w-5 bg-white" : "w-1.5 bg-white/50 hover:bg-white/80"
              }`}
            />
          ))}
        </div>
      )}

      {/* CTA — jumps to whichever spot is on screen. */}
      <Link
        to={spotPath(current)}
        className="group absolute bottom-5 right-4 z-20 inline-flex items-center gap-1.5 rounded-full bg-white/90 px-4 py-2.5 text-[14px] font-semibold text-ink shadow-lg ring-1 ring-black/5 backdrop-blur transition-colors hover:bg-white sm:bottom-8 sm:right-8"
      >
        Spot herausfinden
        <ChevronRightIcon className="text-[16px] transition-transform group-hover:translate-x-0.5" />
      </Link>
    </>
  );
}
