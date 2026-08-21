import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { INCLUDE_ADMIN } from "../lib/target";
import { SearchIcon } from "../lib/icons";
import { Wordmark } from "./ui";
import SearchBar from "./SearchBar";
import AccountMenu from "./AccountMenu";
import ResultsHeader from "./ResultsHeader";

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
}: {
  left?: ReactNode;
  /** `"body"` snaps the bar to the 1180px content column (spot page). */
  width?: "wide" | "body";
  /** Fixed bar that solidifies + shrinks on scroll (landing). */
  sticky?: boolean;
  /** Reduce the mobile spot hero chrome to back + menu only. */
  mobileSpotControls?: boolean;
  /** Landing only: once scrolled, a compact search pill docks into the header
   *  (mobile), replacing the wordmark next to the menu. Tapping it fires this. */
  onMobileSearch?: () => void;
}) {
  // 0 (top of hero) → 1 (fully solid). Driven continuously off scroll, not a
  // single on/off flip, so the mobile bar hardens gradually over the last
  // RANGE px before the trigger — by the time it hits 1 and swaps over to
  // ResultsHeader, it already looks identical, so the swap itself is invisible.
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (!sticky) return;
    const TRIGGER_Y = 84; // ≈ the header bar's bottom edge in viewport px
    const RANGE = 20; // px over which the bar hardens — short, so the
    // in-between state (two logos, hero bleeding through) is barely visible
    const sentinel = document.querySelector<HTMLElement>("[data-landing-header-sentinel]");

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

  const solid = progress >= 1;
  // The bar itself goes opaque well before the content crossfade finishes, so
  // the hero (incl. its own search bar) never shows through mid-transition.
  const bgOpacity = Math.min(1, progress * 3);

  // Landing only: once scrolled past the hero, swap wholesale to the results
  // page's header (logo left, pill centred, account right, scroll-aware).
  if (sticky && solid) return <ResultsHeader />;

  const innerWidth = width === "body" ? "max-w-[1570px] sm:px-8" : "max-w-[1570px] sm:px-10";

  return (
    <header
      className={`${sticky ? "fixed" : "absolute"} inset-x-0 top-0 z-[1000] bg-transparent ${
        solid ? "" : "pointer-events-none"
      }`}
    >
      {/* The hero header hardens continuously into the same opaque material as
          ResultsHeader. At progress=1 the component swap is visually inert. */}
      {sticky && (
        <div
          aria-hidden
          className="absolute inset-0 bg-surface"
          style={{
            opacity: bgOpacity,
            backdropFilter: `blur(${bgOpacity * 12}px)`,
            WebkitBackdropFilter: `blur(${bgOpacity * 12}px)`,
          }}
        />
      )}

      <div
        className={`relative mx-auto px-4 transition-[padding] duration-200 ${innerWidth} ${
          sticky ? `py-5 ${solid ? "sm:py-2.5" : "sm:py-6 sm:py-8"}` : "pt-9 sm:pt-12"
        }`}
      >
        <div className="pointer-events-auto relative grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-1 sm:gap-4">
          <div className="min-w-0 justify-self-start">
            {left ?? (
              <span
                className="hidden select-none text-[12px] font-medium uppercase tracking-[0.14em] text-white/90 sm:block"
                style={sticky ? { opacity: 1 - progress } : undefined}
              >
                Best collection of surfspots
              </span>
            )}
          </div>

          {/* Center — the wordmark, or (landing, scrolled) a docked search. On
              desktop a compact pill expands the SearchBar overlay. Mobile
              fades the wordmark out as `progress` rises, in step with the
              bar hardening and the search button fading in below. */}
          <div className="relative col-start-2 flex min-h-11 min-w-0 items-center justify-center justify-self-center">
            <Link
              to="/"
              aria-label="surfwind data · Startseite"
              style={sticky ? { opacity: 1 - progress, pointerEvents: progress > 0.5 ? "none" : "auto" } : undefined}
              className={`min-h-11 min-w-0 select-none items-center leading-none transition-opacity duration-150 ${
                mobileSpotControls ? "hidden sm:flex" : "flex"
              } ${solid ? "sm:hidden" : "sm:flex"}`}
            >
              <Wordmark size="xl" />
            </Link>

            {/* Desktop: the compact search takes over continuously as the hero
                identity recedes, matching ResultsHeader at the hand-off. */}
            {sticky && (
              <div
                className="absolute hidden sm:block"
                style={{ opacity: progress, pointerEvents: progress > 0.5 ? "auto" : "none" }}
              >
                <SearchBar variant="pill" />
              </div>
            )}
          </div>

          {/* Mobile: a square icon button — same shape as ResultsHeader's —
              fades in as the bar hardens, sitting where the wordmark was. */}
          {onMobileSearch && (
            <button
              type="button"
              onClick={onMobileSearch}
              aria-label="Suche öffnen"
              style={{ opacity: progress, pointerEvents: progress > 0.5 ? "auto" : "none" }}
              className="absolute left-1/2 top-1/2 grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-xl bg-teal text-white shadow-sm transition-opacity duration-150 sm:hidden"
            >
              <SearchIcon className="text-[18px]" />
            </button>
          )}

          <div className="col-start-3 flex min-w-0 items-center justify-end gap-1 sm:gap-5">
            {INCLUDE_ADMIN && (
              <Link
                to="/admin/spot/new"
                className="hidden text-[16px] font-medium text-teal transition-colors hover:text-teal-hover sm:block"
              >
                Füge Spots hinzu
              </Link>
            )}

            <AccountMenu bareOnMobile={mobileSpotControls} />
          </div>
        </div>
      </div>
    </header>
  );
}
