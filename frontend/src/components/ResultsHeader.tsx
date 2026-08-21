import { useState } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "./ui";
import SearchBar from "./SearchBar";
import AccountMenu from "./AccountMenu";
import MobileSearchSheet from "./MobileSearchSheet";
import { SearchIcon } from "../lib/icons";

/**
 * Header for the search results page: logo left, search pill centred, account
 * menu right — all three visible at once (unlike LandingHeader, which docks
 * the pill in on scroll). Tapping the pill opens the same SearchBar overlay
 * used everywhere else.
 */
export default function ResultsHeader() {
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);

  return (
    <>
    <header className="pointer-events-none absolute inset-x-0 top-0 z-[1000]">
      <div className="mx-auto max-w-[1570px] px-4 pt-4 sm:px-8 sm:pt-6">
        <div className="pointer-events-auto relative grid grid-cols-[auto_1fr_auto] items-center gap-4">
          <Link
            to="/"
            aria-label="surfwind data · Startseite"
            className="inline-flex min-h-11 select-none items-center leading-none"
          >
            <Wordmark size="md" />
          </Link>

          <div className="hidden min-w-0 justify-center sm:flex">
            <SearchBar variant="pill" />
          </div>

          {/* Mobile: icon-only, centred on the header row itself (not the
              middle grid track, which is off-centre — logo and account menu
              aren't the same width). */}
          <button
            type="button"
            onClick={() => setMobileSearchOpen(true)}
            aria-label="Suche öffnen"
            className="absolute left-1/2 top-1/2 grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-teal text-white shadow-sm active:scale-[0.97] sm:hidden"
          >
            <SearchIcon className="text-[18px]" />
          </button>

          <div className="justify-self-end">
            <AccountMenu />
          </div>
        </div>
      </div>
    </header>
    <MobileSearchSheet open={mobileSearchOpen} onClose={() => setMobileSearchOpen(false)} />
    </>
  );
}
