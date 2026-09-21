import {
  lazy,
  Suspense,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
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
  // The hardening is a *triggered, time-based* animation, not coupled to scroll
  // distance. A single `docked` boolean flips at one point (IntersectionObserver
  // on touch, a scroll threshold on desktop); CSS transitions then play the whole
  // change — the wordmark glide and the search hand-off (mobile lupe / desktop
  // pill) — over their own fixed duration, so it looks identical whether the
  // visitor scrolls slowly or flicks fast, and the wordmark motion is now the
  // same on mobile and desktop. Desktop additionally keeps a continuous React
  // `progress` for the surface/tagline fade and the padding tightening.
  const [progress, setProgress] = useState(0);
  const [docked, setDocked] = useState(false);
  const desktop = useDesktopViewport();
  // The gliding wordmark is one element pinned to the header's left edge that
  // translates right to sit centred, then glides back on dock. `glideCenterX` is
  // the exact distance to centre it — measured from the header row and the
  // wordmark's own width, so it lands dead-centre on every viewport (mobile and
  // desktop, max-width column included) instead of relying on a `50vw` formula
  // that only holds when the content spans the whole width.
  const rowRef = useRef<HTMLDivElement>(null);
  const gliderRef = useRef<HTMLAnchorElement>(null);
  const [glideCenterX, setGlideCenterX] = useState(0);
  // The transform carries an 820ms transition for the dock/undock glide. But the
  // measured centre also updates once the webfont finishes loading, and we must
  // NOT let that one-time correction animate (the wordmark would visibly drift on
  // a cold load). So the transition stays off until the first measurement has
  // settled, then turns on together with the corrected value in the same commit
  // — a value change made while `transition:none` does not animate.
  const [glideReady, setGlideReady] = useState(false);
  useLayoutEffect(() => {
    if (!sticky) return;
    const measure = () => {
      const row = rowRef.current;
      const glider = gliderRef.current;
      if (!row || !glider) return;
      // offsetWidth ignores the CSS transform, so the base (scale 1) width is
      // read correctly even while the wordmark is docked and scaled down.
      setGlideCenterX(Math.max(0, (row.clientWidth - glider.offsetWidth) / 2));
    };
    measure();
    window.addEventListener("resize", measure);
    // Re-measure once the wordmark's webfont loads, then arm the glide. Fall back
    // to a timer so the glide still works if `document.fonts` is unavailable.
    const arm = () => {
      measure();
      setGlideReady(true);
    };
    const timer = window.setTimeout(arm, 400);
    document.fonts?.ready.then(arm).catch(arm);
    return () => {
      window.removeEventListener("resize", measure);
      window.clearTimeout(timer);
    };
  }, [sticky, desktop]);
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

    // Desktop: continuous `progress` drives the surface, tagline and padding.
    // `docked` still flips at the same single point mobile uses, so the wordmark
    // plays the *identical* triggered glide (and the search pill fades in) on
    // desktop rather than the old cross-fade between two wordmarks.
    let frame = 0;
    const update = () => {
      frame = 0;
      const top = sentinel?.getBoundingClientRect().top;
      const raw =
        top != null
          ? (TRIGGER_Y + RANGE - top) / RANGE
          : (window.scrollY - (window.innerHeight * 0.5 - RANGE)) / RANGE;
      setProgress(Math.min(1, Math.max(0, raw)));
      setDocked(top != null ? top <= TRIGGER_Y : window.scrollY > window.innerHeight * 0.5);
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
        <div
          ref={rowRef}
          className="pointer-events-auto relative grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-1 sm:gap-4"
        >
          {/* ONE wordmark that glides from centred + large (hero top) to docked
              left + small when `docked` flips — a single transform-only motion
              (translate + scale) over a fixed duration, triggered at one scroll
              point (not coupled to scroll distance), so it plays the same whether
              you scroll slowly or flick fast. This is now the *only* wordmark on
              the sticky landing on both mobile and desktop (desktop dropped the
              old cross-fade between two lockups), so the animation is identical.
              `glideCenterX` (measured) is the translate that centres it; the dock
              scale 0.54 takes xl → ≈18px on mobile and ≈31px (≈ md) on desktop. */}
          {sticky && (
            <Link
              ref={gliderRef}
              to="/"
              aria-label="surfwind data"
              className="pointer-events-auto absolute left-0 top-1/2 z-10 flex origin-left items-center whitespace-nowrap leading-none will-change-transform"
              style={{
                transform: docked
                  ? "translateY(-50%) scale(0.54)"
                  : `translateY(-50%) translateX(${glideCenterX}px) scale(1)`,
                // Deliberately slow + eased so the glide reads as a calm settle
                // regardless of scroll speed (it is time-based, not scroll-linked).
                // Off until the first measurement settles (see `glideReady`).
                transition: glideReady ? "transform 820ms cubic-bezier(0.22, 1, 0.36, 1)" : "none",
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
                {/* No docked lockup here any more: the single gliding wordmark
                    above settles into this left slot on both mobile and desktop. */}
              </div>
            )}
          </div>

          {/* Center — on the sticky landing the gliding wordmark (above) owns
              this slot and glides out of it on dock; desktop then fades a compact
              search pill in here (mobile fades the lupe in on the right). Only
              non-sticky pages (legal, 404) render a static centre lockup. */}
          <div className="relative col-start-2 flex min-h-11 min-w-0 items-center justify-center justify-self-center">
            {!sticky && (
              <Link
                to="/"
                className={`min-h-11 min-w-0 select-none items-center leading-none ${
                  mobileSpotControls ? "hidden sm:flex" : "flex"
                }`}
              >
                <Wordmark size="xl" />
              </Link>
            )}

            {/* Desktop: the compact search fades into the centre once docked,
                after the wordmark has glided clear — the same triggered, time-
                based hand-off the mobile lupe uses (see below), so the desktop
                and mobile motion match. */}
            {sticky && desktop && (
              <div
                className="absolute hidden sm:block"
                style={{
                  opacity: docked ? 1 : 0,
                  pointerEvents: docked ? "auto" : "none",
                  transition: docked ? "opacity 260ms ease 140ms" : "opacity 0s",
                }}
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
