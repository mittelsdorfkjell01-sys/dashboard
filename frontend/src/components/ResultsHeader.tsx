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
        <div className="pointer-events-auto grid grid-cols-[auto_1fr_auto] items-center gap-4">
          <Link
            to="/"
            aria-label="surfwind data · Startseite"
            className="inline-flex min-h-11 select-none items-center leading-none"
          >
            <Wordmark size="md" />
          </Link>

          <div className="flex min-w-0 justify-center">
            <div className="hidden sm:block">
              <SearchBar variant="pill" />
            </div>
            <button
              type="button"
              onClick={() => setMobileSearchOpen(true)}
              aria-label="Suche öffnen"
              className="flex min-h-11 max-w-full items-center gap-2 rounded-2xl border border-line bg-surface py-1 pl-4 pr-1 text-[14px] font-medium text-ink shadow-sm active:scale-[0.99] sm:hidden"
            >
              <span className="truncate">Suchen</span>
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-teal text-white">
                <SearchIcon className="text-[15px]" />
              </span>
            </button>
          </div>

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
