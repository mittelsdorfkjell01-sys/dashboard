import { lazy, Suspense, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "./ui";
import AccountMenu from "./AccountMenu";
import { SearchIcon } from "../lib/icons";
import { useDesktopViewport } from "../lib/useAutoHideHeader";

const SearchBar = lazy(() => import("./SearchBar"));
const MobileSearchSheet = lazy(() => import("./MobileSearchSheet"));

/**
 * Header for the search results page: logo left, search pill centred, account
 * menu right — all three visible at once (unlike LandingHeader, which docks
 * the pill in on scroll). Tapping the pill opens the same SearchBar overlay
 * used everywhere else. The opaque bar stays visible while the page scrolls,
 * on desktop and mobile alike, so navigation, search and account access remain
 * in one predictable place.
 */
export default function ResultsHeader() {
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [mobileSearchLoaded, setMobileSearchLoaded] = useState(false);
  const mobileSearchTriggerRef = useRef<HTMLButtonElement | null>(null);
  const desktop = useDesktopViewport();
  const openMobileSearch = (trigger: HTMLButtonElement) => {
    mobileSearchTriggerRef.current = trigger;
    setMobileSearchLoaded(true);
    setMobileSearchOpen(true);
  };

  return (
    <>
    <header
      className="pointer-events-none fixed inset-x-0 top-0 z-[1000] bg-surface"
    >
      <div className="mx-auto max-w-[1570px] px-4 py-5 sm:px-8 sm:pt-6 sm:pb-2">
        <div className="pointer-events-auto relative grid grid-cols-[auto_1fr_auto] items-center gap-4">
          <Link
            to="/"
            className="inline-flex min-h-11 select-none items-center leading-none"
          >
            <Wordmark size="md" />
          </Link>

          <div className="hidden min-w-0 justify-center sm:flex">
            {desktop && (
              <Suspense fallback={<div aria-hidden className="h-11 w-48 rounded-[14px] bg-surface shadow-card" />}>
                <SearchBar variant="pill" />
              </Suspense>
            )}
          </div>

          {/* Mobile: icon-only, centred on the header row itself (not the
              middle grid track, which is off-centre — logo and account menu
              aren't the same width). */}
          <button
            type="button"
            onClick={(event) => openMobileSearch(event.currentTarget)}
            aria-label="Suche öffnen"
            className="absolute left-1/2 top-1/2 grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center text-ink active:scale-[0.97] sm:hidden"
          >
            <SearchIcon className="text-sz-18" />
          </button>

          <div className="justify-self-end">
            <AccountMenu />
          </div>
        </div>
      </div>
    </header>
    {mobileSearchLoaded && (
      <Suspense fallback={null}>
        <MobileSearchSheet
          open={mobileSearchOpen}
          onClose={() => setMobileSearchOpen(false)}
          returnFocusRef={mobileSearchTriggerRef}
        />
      </Suspense>
    )}
    </>
  );
}
