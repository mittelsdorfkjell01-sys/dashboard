import { useState } from "react";
import SearchBar from "./SearchBar";
import MobileSearchTrigger from "./MobileSearchTrigger";
import MobileSearchSheet from "./MobileSearchSheet";

/**
 * The /map page's own top bar: just the centred search — the same search
 * entry used everywhere else, no second search implementation. No wordmark
 * here (2026-08-23 feedback: the map is a full-bleed tool, not a branded
 * page). The back control lives with the other floating map controls (see
 * MapView's `.swd-map-controls-left`), not in this bar.
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
          <div className="relative flex min-h-[44px] items-center justify-center sm:min-h-[48px]">
            <div className="pointer-events-auto flex items-center">
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
