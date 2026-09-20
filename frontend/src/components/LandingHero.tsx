import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import HeroImage from "./HeroImage";
import { spotPath } from "../lib/spotRoutes";
import { PinIcon } from "../lib/icons";
import type { Spot } from "../lib/types";

const ADVANCE_MS = 60000;
const MAX_SLIDES = 12;

// The landing spot list is fetched with a catalogue-version token, which forces
// the non-persistent SWR path (see useSpots). That means the reel would sit on
// the dark fallback until a full 500-record fetch returns on *every* reload —
// the "hero takes especially long" report. Persist just the curated reel here
// so a returning visitor paints a real hero the instant the component mounts,
// exactly like the rest of the app hydrates from its cache; the fresh list then
// corrects it in the background.
const REEL_CACHE_KEY = "swd.hero-reel.v1";

function loadCachedReel(): Spot[] {
  try {
    const raw = localStorage.getItem(REEL_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Spot[]) : [];
  } catch {
    return [];
  }
}

function saveCachedReel(slides: Spot[]): void {
  try {
    localStorage.setItem(REEL_CACHE_KEY, JSON.stringify(slides));
  } catch {
    /* private browsing / quota — the reel still works for this session */
  }
}

/** Deterministic Fisher–Yates shuffle. A fixed per-mount seed gives a fresh
 * order on each page load while staying stable across re-renders — and, because
 * it depends only on the seed and the input order, the swap from the cached reel
 * to the freshly fetched one (same spots, same order) keeps the same sequence,
 * so the hero on screen never jumps when the live list arrives. */
function shuffleWithSeed<T>(items: readonly T[], seed: number): T[] {
  const result = [...items];
  let state = seed >>> 0;
  const random = () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

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
  // A fresh order every load (see shuffleWithSeed), fixed for this mount so the
  // reel never reshuffles under the auto-advance.
  const [seed] = useState(() => Math.floor(Math.random() * 0x100000000));

  // Only real hero photos explicitly curated in the admin Hero tab may enter
  // the reel. An empty selection deliberately uses the static brand hero.
  const liveSlides = useMemo(() => selectLandingHeroSlides(spots), [spots]);

  // Read the persisted reel once at mount, as an instant fallback while the live
  // catalogue is still in flight.
  const cachedSlidesRef = useRef<Spot[] | null>(null);
  if (cachedSlidesRef.current === null) {
    cachedSlidesRef.current = selectLandingHeroSlides(loadCachedReel());
  }

  // Persist the curated reel (in catalogue order, before shuffling) so the next
  // load can paint it immediately.
  useEffect(() => {
    if (liveSlides.length > 0) saveCachedReel(liveSlides);
  }, [liveSlides]);

  const slides = useMemo(() => {
    const source = liveSlides.length > 0 ? liveSlides : cachedSlidesRef.current!;
    return shuffleWithSeed(source, seed);
  }, [liveSlides, seed]);
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
