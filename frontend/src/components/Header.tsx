import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Wordmark } from "./ui";
import SearchBar from "./SearchBar";
import MobileSearchTrigger from "./MobileSearchTrigger";
import MobileSearchSheet from "./MobileSearchSheet";
import { ChevronLeftIcon } from "../lib/icons";

/**
 * The /map page's own top bar: a back control (with a real fallback, not an
 * isolated "close") plus the same search entry used everywhere else — no
 * second search implementation. The wordmark rides along next to the back
 * arrow instead of floating centred, since centring it here had no
 * functional purpose. Desktop keeps the inline `SearchBar` pill; mobile
 * reuses `MobileSearchTrigger` + `MobileSearchSheet` (the Landing/Results
 * pattern) as one wide capsule.
 */
export default function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  // `location.key === "default"` means this tab has no entry to go back to
  // (deep link, reload, new tab) — fall back to the homepage instead of
  // leaving the visitor stuck or navigating outside the app.
  const goBack = () => { if (location.key !== "default") navigate(-1); else navigate("/"); };

  return (
    <>
      <header className="pointer-events-none absolute inset-x-0 top-0 z-[1000]">
        {/* Right padding is wider than the left on `sm+` — it clears the
            top-right zoom/list control stack, which is pinned to the
            viewport edge independently of this (centred, max-width) bar and
            would otherwise sit under the search pill at laptop widths. */}
        <div className="mx-auto max-w-[1400px] px-4 pt-4 sm:pl-8 sm:pr-24 sm:pt-6">
          {/* The row itself stays pointer-events-none — only real controls
              opt back in — so nothing here can sit on top of (and steal
              clicks from) the top-right zoom/list stack. The mobile search
              capsule is additionally width-capped (not padded: padding
              would still capture hit-testing) to stop short of that
              stack's reserved column. */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={goBack}
              aria-label="Zurück"
              className="swd-map-control pointer-events-auto inline-flex h-11 w-11 shrink-0 items-center justify-center gap-1.5 sm:w-auto sm:px-3.5"
            >
              <ChevronLeftIcon className="text-[18px]" />
              <span className="hidden text-[13px] font-semibold sm:inline">Zurück</span>
            </button>

            <Link
              to="/"
              aria-label="surfwind data · Startseite"
              className="pointer-events-auto hidden shrink-0 select-none items-center leading-none md:inline-flex"
            >
              <Wordmark size="sm" />
            </Link>

            <div className="pointer-events-auto min-w-0 w-[calc(100vw-168px)] sm:ml-auto sm:w-auto">
              <div className="sm:hidden">
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
