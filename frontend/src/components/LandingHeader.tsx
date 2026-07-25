import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { INCLUDE_ADMIN } from "../lib/target";
import { Wordmark } from "./ui";
import AccountMenu from "./AccountMenu";

/**
 * Landing-only top bar for the "surfwind data" design (Frame_1 / Frame_5).
 * Transparent over the hero: caps tagline (left), wordmark (centre), the "Füge
 * Spots hinzu" link (admin build) and the shared account menu. The map button
 * lives down by the "aktuelle Top Spots" title (see Landing), not up here.
 *
 * Deliberately separate from the shared `Header.tsx` (which the map and search
 * pages reuse with a centred brand).
 */
export default function LandingHeader({ left }: { left?: ReactNode }) {
  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-[1000]">
      <div className="mx-auto max-w-[1500px] px-4 pt-9 sm:px-10 sm:pt-12">
        <div className="pointer-events-auto grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          {/* Left — caps tagline, or a page-specific slot (e.g. the spot
              page's "Zurück" pill) */}
          {left ?? (
            <span className="hidden select-none text-[12px] font-medium uppercase tracking-[0.14em] text-white/90 sm:block">
              Best collection of surfspots
            </span>
          )}

          {/* Centre — wordmark */}
          <Link
            to="/"
            aria-label="surfwind data — Startseite"
            className="col-start-2 select-none justify-self-center leading-none"
          >
            <Wordmark size="xl" />
          </Link>

          {/* Right — add-spot link + account menu */}
          <div className="col-start-3 flex items-center justify-end gap-3 sm:gap-5">
            {INCLUDE_ADMIN && (
              <Link
                to="/admin/spot/new"
                className="hidden text-[16px] font-medium text-teal transition-colors hover:text-teal-hover sm:block"
              >
                Füge Spots hinzu
              </Link>
            )}

            <AccountMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
