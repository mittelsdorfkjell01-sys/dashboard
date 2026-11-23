import { useEffect, useState } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { MapIcon } from "../lib/icons";

/**
 * The floating "Karte" pill, bottom-centre, that opens the one weather map from
 * the landing, the results page and a spot's Daten tab. One component instead
 * of three hand-copied links, so the fixes below hold everywhere:
 *
 *  - 44px tall (`min-h-11`): it was 37px, under the touch-target floor.
 *  - It rides above the footer once the footer scrolls into view. Pinned at
 *    `bottom-6` it otherwise sat on the last footer row (Impressum /
 *    Datenschutz), where it covered links that have no other way in. Until
 *    2026-11-23 it faded out there instead, which on a short page (a few
 *    results, footer in view from the start) left no way to the map at all.
 *
 * `className` carries the per-page differences (e.g. `lg:hidden` where a
 * desktop map is already on screen, or the ink colour on the dark Daten page).
 * `ground` picks the fill: `page` on the light pages, where the float shadow
 * lifts it; `band` on the dark Daten page, where that shadow is invisible and a
 * page-coloured pill showed only its label — one tone step lifts it instead.
 */
export default function MapPill({
  to,
  state,
  className = "",
  ground = "page",
}: {
  to: LinkProps["to"];
  state?: LinkProps["state"];
  className?: string;
  ground?: "page" | "band";
}) {
  // How far the footer reaches into the viewport. The pill rides that far
  // above its resting place instead of disappearing.
  const [lift, setLift] = useState(0);

  useEffect(() => {
    const footer = document.querySelector("footer");
    if (!footer) return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const reach = window.innerHeight - footer.getBoundingClientRect().top;
      setLift(reach > 0 ? Math.round(reach) : 0);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    const observer = "ResizeObserver" in window ? new ResizeObserver(schedule) : null;
    observer?.observe(document.body);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      observer?.disconnect();
    };
  }, []);

  return (
    <Link
      to={to}
      state={state}
      aria-label="Karte öffnen"
      style={{ bottom: `calc(1.5rem + ${lift}px)` }}
      className={`fixed left-1/2 z-sticky flex min-h-11 -translate-x-1/2 items-center gap-1.5 rounded-card px-4 py-2 text-ui font-normal shadow-float ${
        ground === "band" ? "bg-band" : "bg-page"
      } ${className}`}
    >
      Karte <MapIcon className="text-body" />
    </Link>
  );
}
