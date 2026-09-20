import { lazy, Suspense, useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { INCLUDE_ADMIN } from "../lib/target";
import { SearchIcon } from "../lib/icons";
import { Wordmark } from "./ui";
import AccountMenu from "./AccountMenu";
import { useDesktopViewport } from "../lib/useAutoHideHeader";

const SearchBar = lazy(() => import("./SearchBar"));

/**
 * Top bar for the hero pages. By default it's transparent and absolute over the
 * hero (spot/region pages keep this). With `sticky`, it's fixed and turns into a
 * solid, slightly smaller sticky bar once the hero is scrolled past (~half a
 * viewport) — a translucent surface appears and the padding tightens. On the
 * landing, once scrolled a compact search entry docks in where the wordmark was:
 * a full-screen sheet on mobile, the expanding SearchBar overlay on desktop.
 */
export default function LandingHeader({
  left,
  width = "wide",
  sticky = false,
  mobileSpotControls = false,
  onMobileSearch,
  onLight = false,
  showMenu = false,
}: {
  left?: ReactNode;
  /** `"body"` snaps the bar to the 1180px content column (spot page). */
  width?: "wide" | "body";
  /** Fixed bar that solidifies + shrinks on scroll (landing). */
  sticky?: boolean;
  /** Reduce the mobile spot hero chrome to back + menu only. */
  mobileSpotControls?: boolean;
  /** The account/burger menu lives on the landing page only. */
  showMenu?: boolean;
  /** Landing only: once scrolled, a compact search pill docks into the header
   *  (mobile), replacing the wordmark next to the menu. Tapping it fires this. */
  onMobileSearch?: (trigger: HTMLButtonElement) => void;
  /** The bar sits on the light page instead of the dark hero (legal, 404,
   *  error/not-found states). Switches the white hero tagline to a readable
   *  ink token so it doesn't vanish and fail colour contrast. */
  onLight?: boolean;
}) {
  // Mobile: the hardening is a *triggered, time-based* animation, not coupled to
  // scroll distance. An IntersectionObserver flips a single `docked` boolean at
  // one point; CSS transitions then play the whole change (wordmark glide,
  // surface, lupe) over their own fixed duration — so it looks identical whether
  // the visitor scrolls slowly or flicks fast, and never stutters with the
  // finger. Desktop keeps a continuous React `progress` (its search-pill grows
  // in, and the padding tightens, as the hero recedes).
  const [progress, setProgress] = useState(0);
  const [docked, setDocked] = useState(false);
  const desktop = useDesktopViewport();
  useEffect(() => {
    if (!sticky) return;
    const TRIGGER_Y = 84; // ≈ the header bar's bottom edge in viewport px
    const RANGE = 96;
    const sentinel = document.querySelector<HTMLElement>("[data-landing-header-sentinel]");
    const nativeTouch = window.matchMedia("(pointer: coarse) and (hover: none)").matches;

    // Touch: one trigger, then let CSS animate. No per-frame work at all.
    if (nativeTouch && sentinel && "IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        ([entry]) => setDocked(!entry.isIntersecting),
        { rootMargin: `-${TRIGGER_Y}px 0px 0px 0px`, threshold: 0 },
      );
      observer.observe(sentinel);
      return () => observer.disconnect();
    }

    // Desktop: continuous progress off scroll.
    let frame = 0;
    const update = () => {
      frame = 0;
      const top = sentinel?.getBoundingClientRect().top;
      const raw =
        top != null
          ? (TRIGGER_Y + RANGE - top) / RANGE
          : (window.scrollY - (window.innerHeight * 0.5 - RANGE)) / RANGE;
      setProgress(Math.min(1, Math.max(0, raw)));
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [sticky]);

  // The frosted surface: desktop ramps with `progress`; mobile is a 0/1 driven
  // by `docked` and eased by the touch-only CSS transition on the element.
  const surfaceOpacity = desktop ? Math.min(1, progress * 3) : docked ? 1 : 0;

  const innerWidth = width === "body" ? "max-w-[1570px] sm:px-8" : "max-w-[1570px] sm:px-10";

  return (
    <header
      className={`${sticky ? "fixed" : "absolute"} pointer-events-none inset-x-0 top-0 z-[1000] bg-transparent`}
      // Desktop uses the CSS var (from React `progress`) only for the padding
      // tightening; mobile doesn't need it.
      style={sticky && desktop ? ({ "--header-progress": progress } as CSSProperties) : undefined}
    >
      {/* The hero header hardens into the same opaque material as the results
          header. Desktop ramps its opacity/blur with scroll; on touch it is a
          0/1 that the CSS transition (see index.css `[data-mobile-solid-header]`)
          eases over its own duration when `docked` flips. */}
      {sticky && (
        <div
          aria-hidden
          className="absolute inset-0 bg-surface"
          style={{
            opacity: surfaceOpacity,
            backdropFilter: desktop ? `blur(${surfaceOpacity * 12}px)` : undefined,
            WebkitBackdropFilter: desktop ? `blur(${surfaceOpacity * 12}px)` : undefined,
          }}
          data-mobile-solid-header
        />
      )}

      <div
        className={`relative mx-auto px-4 ${innerWidth} ${
          sticky
            ? "py-5 sm:pt-[calc(2rem-var(--header-progress)*0.5rem)] sm:pb-[calc(2rem-var(--header-progress)*1.5rem)]"
            : "pt-9 sm:pt-12"
        }`}
      >
        <div className="pointer-events-auto relative grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-1 sm:gap-4">
          {/* Mobile only: ONE wordmark that glides from centred + large (hero
              top) to docked left + small when `docked` flips — a single
              transform-only motion (translate + scale) over a fixed duration,
              triggered at one scroll point (not coupled to scroll distance), so
              it plays the same whether you scroll slowly or flick fast. `50%` is
              the element's own half-width, `50vw` half the viewport, `1rem` the
              header's px-4 gutter: together they centre it when not docked.
              scale 1 → 0.54 ≈ xl(34px) → sm(18px). */}
          {sticky && (
            <Link
              to="/"
              aria-label="surfwind data"
              className="pointer-events-auto absolute left-0 top-1/2 z-10 flex origin-left items-center whitespace-nowrap leading-none will-change-transform sm:hidden"
              style={{
                transform: docked
                  ? "translateY(-50%) scale(0.54)"
                  : "translateY(-50%) translateX(calc(50vw - 1rem - 50%)) scale(1)",
                // Deliberately slow + eased so the glide reads as a calm settle
                // regardless of scroll speed (it is time-based, not scroll-linked).
                transition: "transform 820ms cubic-bezier(0.22, 1, 0.36, 1)",
              }}
            >
              <Wordmark size="xl" />
            </Link>
          )}

          <div className="min-w-0 justify-self-start">
            {left ?? (
              <div className="relative flex min-h-11 items-center">
                <span
                  className={`hidden select-none whitespace-nowrap text-caption font-medium uppercase tracking-[0.14em] sm:block ${
                    onLight ? "text-ink-soft" : "text-white/90"
                  }`}
                  style={sticky ? { opacity: 1 - progress } : undefined}
                >
                  Best collection of surfspots
                </span>
                {sticky && (
                  // Desktop only: the docked lockup crossfades in on the left.
                  // Mobile uses the single gliding wordmark below instead.
                  <Link
                    to="/"
                    className="absolute left-0 hidden min-h-11 select-none items-center leading-none sm:inline-flex"
                    style={{ opacity: progress, pointerEvents: progress > 0.5 ? "auto" : "none" }}
                  >
                    <Wordmark size="md" />
                  </Link>
                )}
              </div>
            )}
          </div>

          {/* Center — the wordmark, or (landing, scrolled) a docked search. On
              desktop a compact pill expands the SearchBar overlay. Mobile
              fades the wordmark out as `progress` rises, in step with the
              bar hardening and the search button fading in below. */}
          <div className="relative col-start-2 flex min-h-11 min-w-0 items-center justify-center justify-self-center">
            {/* On the sticky landing this is the desktop-only centre lockup;
                mobile uses the single gliding wordmark. Non-sticky pages (legal,
                404) keep it on mobile too, since there is no glider there. */}
            <Link
              to="/"
              style={sticky ? { opacity: 1 - progress, pointerEvents: progress > 0.5 ? "none" : "auto" } : undefined}
              className={`min-h-11 min-w-0 select-none items-center leading-none transition-opacity duration-150 ${
                sticky || mobileSpotControls ? "hidden sm:flex" : "flex"
              }`}
            >
              <Wordmark size="xl" />
            </Link>

            {/* Desktop: the compact search takes over continuously as the hero
                identity recedes, matching ResultsHeader at the hand-off. */}
            {sticky && desktop && progress > 0 && (
              <div
                className="absolute hidden sm:block"
                style={{ opacity: progress, pointerEvents: progress > 0.5 ? "auto" : "none" }}
              >
                <Suspense fallback={<div aria-hidden className="h-10 w-48 rounded-[14px] bg-surface shadow-card" />}>
                  <SearchBar variant="pill" />
                </Suspense>
              </div>
            )}
          </div>

          {/* Mobile: a bare magnifying-glass icon — same de-chromed treatment as
              ResultsHeader's (no teal fill/box), in the ink token so it stays
              readable on the hardened white bar — fades in where the wordmark
              was as the bar hardens. */}
          {onMobileSearch && (
            <button
              type="button"
              onClick={(event) => onMobileSearch(event.currentTarget)}
              aria-label="Suche öffnen"
              // Docking: fade in after a short delay, once the wordmark has
              // begun gliding clear of centre. Un-docking: disappear instantly,
              // so the slow wordmark returning to centre never passes over a
              // still-visible lupe (it sits behind the z-10 wordmark).
              style={{
                opacity: docked ? 1 : 0,
                pointerEvents: docked ? "auto" : "none",
                transition: docked ? "opacity 260ms ease 140ms" : "opacity 0s",
              }}
              className="absolute left-1/2 top-1/2 grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center text-ink active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink sm:hidden"
            >
              <SearchIcon className="text-sz-18" />
            </button>
          )}

          <div className="col-start-3 flex min-w-0 items-center justify-end gap-1 sm:gap-5">
            {INCLUDE_ADMIN && (
              <Link
                to="/admin/spot/new"
                className="hidden text-sz-16 font-medium text-ink transition-opacity hover:opacity-70 sm:block"
              >
                Füge Spots hinzu
              </Link>
            )}

            {showMenu && <AccountMenu bareOnMobile={mobileSpotControls} />}
          </div>
        </div>
      </div>
    </header>
  );
}
