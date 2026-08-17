import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { INCLUDE_ADMIN } from "../lib/target";
import { SearchIcon } from "../lib/icons";
import { Wordmark } from "./ui";
import SearchBar from "./SearchBar";
import AccountMenu from "./AccountMenu";

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
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    if (!sticky) return;
    // Solidify exactly when the search bar has scrolled up to meet the header —
    // i.e. the wordmark bar "catches" the search bar. Falls back to half-a-
    // viewport when the search bar isn't on the page (other hero pages).
    const TRIGGER_Y = 84; // ≈ the header bar's bottom edge in viewport px
    const onScroll = () => {
      const search = document.getElementById("landing-search");
      const rect = search?.getBoundingClientRect();
      // Only trust the search bar when it is actually visible (it is hidden on
      // mobile, where a display:none rect would otherwise read as top 0).
      if (rect && rect.width > 0) setSolid(rect.top <= TRIGGER_Y);
      else setSolid(window.scrollY > window.innerHeight * 0.5);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [sticky]);

  const innerWidth = width === "body" ? "max-w-[1570px] sm:px-8" : "max-w-[1570px] sm:px-10";

  return (
    <header
      className={`${sticky ? "fixed" : "absolute"} inset-x-0 top-0 z-[1000] transition-colors duration-200 ${
        solid
          ? "bg-page/90 backdrop-blur"
          : "pointer-events-none bg-transparent"
      }`}
    >
      <div
        className={`mx-auto px-4 transition-[padding] duration-200 ${innerWidth} ${
          solid ? "py-2.5" : sticky ? "py-6 sm:py-8" : "pt-9 sm:pt-12"
        }`}
      >
        <div className="pointer-events-auto relative grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-1 sm:gap-4">
          <div className="min-w-0 justify-self-start">
            {left ?? (
              <span
                className={`hidden select-none text-[12px] font-medium uppercase tracking-[0.14em] transition-colors sm:block ${
                  solid ? "text-teal" : "text-white/90"
                }`}
              >
                Best collection of surfspots
              </span>
            )}
          </div>

          {/* Center — the wordmark, or (landing, scrolled) a docked search. On
              desktop a compact pill expands the SearchBar overlay. */}
          <div className="col-start-2 flex min-w-0 items-center justify-center justify-self-center">
            {!solid && (
              <Link
                to="/"
                aria-label="surfwind data · Startseite"
                className={`min-h-11 min-w-0 select-none items-center leading-none ${
                  mobileSpotControls ? "hidden sm:flex" : "flex"
                }`}
              >
                <Wordmark size="xl" />
              </Link>
            )}

            {/* Desktop (sm+): a compact pill that opens the SearchBar overlay. */}
            {sticky && solid && (
              <div className="hidden sm:block">
                <SearchBar variant="pill" />
              </div>
            )}
          </div>

          {/* Mobile: a compact search pill docks in once scrolled, sitting where
              the wordmark was, beside the menu. Opens the full-screen sheet at
              the current scroll position (no jump to the top). */}
          {onMobileSearch && (
            <button
              type="button"
              onClick={onMobileSearch}
              aria-label="Suche öffnen"
              className={`absolute inset-y-0 left-0 right-12 my-auto flex h-11 items-center gap-2 rounded-full border border-line bg-surface px-4 text-[15px] font-medium text-ink shadow-sm transition-opacity duration-200 sm:hidden ${
                solid ? "opacity-100" : "pointer-events-none opacity-0"
              }`}
            >
              <SearchIcon className="text-[18px]" />
              Suchen
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
