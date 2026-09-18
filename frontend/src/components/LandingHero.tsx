import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import HeroImage from "./HeroImage";
import { spotPath } from "../lib/spotRoutes";
import { PinIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

const ADVANCE_MS = 60000;
const MAX_SLIDES = 12;

/** The admin selection is authoritative: unselected hero images must never
 * leak into the landing reel, including when the selection is empty. */
export function selectLandingHeroSlides(spots: Spot[]): Spot[] {
  return spots
    .filter((spot) => Boolean(spot.hero && spot.heroReel))
    .slice(0, MAX_SLIDES);
}

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
 * Falls back to the static brand hero when no selected spot carries a usable
 * image (e.g. a fresh seed database or an intentionally empty selection).
 */
export default function LandingHero({ spots }: { spots: Spot[] }) {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduce(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  // Only real hero photos explicitly curated in the admin Hero tab may enter
  // the reel. An empty selection deliberately uses the static brand hero.
  const slides = useMemo(() => selectLandingHeroSlides(spots), [spots]);
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
    // While the catalogue loads (and for a deliberately empty selection) show a
    // calm brand-dark field — never the old /hero-surfwind stock photo, which is
    // not part of the admin-curated rotation and used to flash in on reload.
    return (
      <div
        className="absolute inset-0 z-0 bg-gradient-to-b from-[#2A2420] via-[#241C17] to-[#161210]"
        aria-hidden
      />
    );
  }

  const current = slides[Math.min(index, count - 1)];

  return (
    <>
      {/* Background reel — decorative and non-interactive (pointer-events-none),
          so there's nothing to swipe or click; the CTA carries the only link.
          A brand-dark base sits under it so nothing white shows through in the
          instant before the first selected hero decodes. */}
      <div className="pointer-events-none absolute inset-0 z-0 select-none bg-[#161210]" aria-hidden>
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
            // Static background: only a cross-fade between slides, no motion
            // on the image itself (no Ken Burns zoom/pan).
            <div
              key={s.id}
              className={`absolute inset-0 transition-opacity ease-in-out ${
                active ? "opacity-100" : "opacity-0"
              } ${reduce ? "duration-200" : "duration-[1200ms]"}`}
            >
              <HeroImage
                src={s.hero!}
                alt=""
                delivery={s.heroDelivery}
                provider={s.heroCredit?.provider}
                focal={s.heroFocal}
                focalMobile={s.heroFocalMobile}
                rotation={s.heroRotation}
                width={s.heroWidth}
                priority={active}
                className="absolute inset-0 h-full w-full object-cover"
              />
            </div>
          );
        })}
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-[rgba(36,28,23,0.35)]" />
      </div>

      {/* CTA — a small frosted map-pin button that links to the spot on screen.
          No visible name (the spot name stays as the accessible label); just the
          pin, aligned to the same content column as the header. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-12 z-20 sm:bottom-16">
        <div className="mx-auto flex max-w-[1570px] px-4 sm:px-10">
          <Link
            to={spotPath(current)}
            aria-label={`Zum Spot ${current.name}`}
            className="pointer-events-auto grid h-8 w-8 place-items-center rounded-full border border-white/25 bg-black/55 text-white shadow-float transition-colors hover:bg-black/65 active:scale-[0.97] sm:bg-black/25 sm:backdrop-blur-md sm:hover:bg-black/35"
          >
            <PinIcon className="text-label" />
          </Link>
        </div>
      </div>
    </>
  );
}
