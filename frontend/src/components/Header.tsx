import { useState } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "./ui";
import SearchBar from "./SearchBar";
import MobileSearchTrigger from "./MobileSearchTrigger";
import MobileSearchSheet from "./MobileSearchSheet";

/**
 * The /map page's own top bar: wordmark (same size as the results page)
 * left, search centred — the same search entry used everywhere else, no
 * second search implementation. The back control now lives with the other
 * floating map controls (see MapView's `.swd-map-controls-left`), not in
 * this bar, so it isn't accounted for here.
 */
export default function Header() {
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);

  return (
    <>
      {/* Left/right padding on `sm+` clears the floating back+zoom (left)
          and list (right) control stacks, which are pinned to the viewport
          edge independently of this centred, max-width bar. */}
      <header className="pointer-events-none absolute inset-x-0 top-0 z-[1000]">
        <div className="mx-auto max-w-[1400px] px-4 pt-4 sm:pl-20 sm:pr-16 sm:pt-6">
          {/* Search is absolutely centred on the row itself (not balanced
              against the wordmark via a grid) — a grid's `1fr` centre
              column shifts off-centre by the wordmark's own width, which
              reads as "not actually centred". The row stays
              pointer-events-none: a `flex` box is full-width even with
              off-centre content, so making the *row* clickable would swallow
              clicks over its empty right-hand slack — including the list
              button floating on top of it in that exact spot. */}
          <div className="relative flex min-h-[44px] items-center sm:min-h-[48px]">
            <Link
              to="/"
              aria-label="surfwind data · Startseite"
              className="pointer-events-auto hidden shrink-0 select-none items-center leading-none sm:inline-flex"
            >
              <Wordmark size="md" />
            </Link>

            <div className="pointer-events-auto absolute inset-y-0 left-1/2 flex -translate-x-1/2 items-center">
              {/* Width-capped (not just centered) on mobile: clears the
                  floating back+zoom stack on the left and the list button
                  on the right, both pinned to the viewport edge outside
                  this bar's own layout. */}
              <div className="w-[calc(100vw-176px)] sm:hidden">
                <MobileSearchTrigger onClick={() => setMobileSearchOpen(true)} label="Ort, Region oder Spot" compact />
              </div>
              <div className="hidden sm:block">
                <SearchBar variant="pill" />
              </div>
            </div>
          </div>
        </div>
      </header>
      <MobileSearchSheet open={mobileSearchOpen} onClose={() => setMobileSearchOpen(false)} />
    </>
  );
}
