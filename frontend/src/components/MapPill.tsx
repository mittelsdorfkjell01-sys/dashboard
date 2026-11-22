import { useEffect, useState } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { MapIcon } from "../lib/icons";

/**
 * The floating "Karte" pill, bottom-centre, that opens the one weather map from
 * the landing, the results page and a spot's Daten tab. One component instead
 * of three hand-copied links, so the fixes below hold everywhere:
 *
 *  - 44px tall (`min-h-11`): it was 37px, under the touch-target floor.
 *  - It steps aside once the footer scrolls into view. Pinned at `bottom-6` it
 *    otherwise sat on the last footer row (Impressum / Datenschutz) at the end
 *    of every page, where it covered links that have no other way in.
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
  const [footerVisible, setFooterVisible] = useState(false);

  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const footer = document.querySelector("footer");
    if (!footer) return;
    const observer = new IntersectionObserver(([entry]) => setFooterVisible(entry.isIntersecting));
    observer.observe(footer);
    return () => observer.disconnect();
  }, []);

  return (
    <Link
      to={to}
      state={state}
      aria-label="Karte öffnen"
      aria-hidden={footerVisible || undefined}
      tabIndex={footerVisible ? -1 : undefined}
      className={`fixed bottom-6 left-1/2 z-sticky flex min-h-11 -translate-x-1/2 items-center gap-1.5 rounded-card px-4 py-2 text-ui font-normal shadow-float transition-opacity duration-base ${
        ground === "band" ? "bg-band" : "bg-page"
      } ${footerVisible ? "pointer-events-none opacity-0" : "opacity-100"} ${className}`}
    >
      Karte <MapIcon className="text-body" />
    </Link>
  );
}
