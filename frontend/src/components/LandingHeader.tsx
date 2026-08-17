import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { INCLUDE_ADMIN } from "../lib/target";
import { Wordmark } from "./ui";
import AccountMenu from "./AccountMenu";

/**
 * Top bar for the hero pages. By default it's transparent and absolute over the
 * hero (spot/region pages keep this). With `sticky`, it's fixed and turns into a
 * solid, slightly smaller sticky bar once the hero is scrolled past (~half a
 * viewport) — a translucent surface appears, the padding tightens and the
 * wordmark steps down to its compact size. Used on the landing.
 */
export default function LandingHeader({
  left,
  width = "wide",
  sticky = false,
  mobileSpotControls = false,
}: {
  left?: ReactNode;
  /** `"body"` snaps the bar to the 1180px content column (spot page). */
  width?: "wide" | "body";
  /** Fixed bar that solidifies + shrinks on scroll (landing). */
  sticky?: boolean;
  /** Reduce the mobile spot hero chrome to back + menu only. */
  mobileSpotControls?: boolean;
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
        <div className="pointer-events-auto grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-1 sm:gap-4">
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

          <Link
            to="/"
            aria-label="surfwind data · Startseite"
            className={`col-start-2 min-h-11 min-w-0 select-none items-center justify-self-center leading-none ${mobileSpotControls ? "hidden sm:flex" : "flex"}`}
          >
            <Wordmark size={solid ? "md" : "xl"} />
          </Link>

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
