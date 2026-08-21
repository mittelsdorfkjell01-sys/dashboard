import { Link } from "react-router-dom";
import { Wordmark } from "./ui";
import SearchBar from "./SearchBar";
import AccountMenu from "./AccountMenu";

/**
 * Header for the search results page: logo left, search pill centred, account
 * menu right — all three visible at once (unlike LandingHeader, which docks
 * the pill in on scroll). Tapping the pill opens the same SearchBar overlay
 * used everywhere else.
 */
export default function ResultsHeader() {
  return (
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
            <div className="w-full max-w-[420px]">
              <SearchBar variant="pill" />
            </div>
          </div>

          <div className="justify-self-end">
            <AccountMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
