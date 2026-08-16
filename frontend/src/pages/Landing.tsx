import { Link, useLocation } from "react-router-dom";
import { useState } from "react";
import LandingHeader from "../components/LandingHeader";
import LandingHero from "../components/LandingHero";
import SearchBar from "../components/SearchBar";
import MobileSearchTrigger from "../components/MobileSearchTrigger";
import MobileSearchSheet from "../components/MobileSearchSheet";
import TopSpotsRow from "../components/TopSpotsRow";
import SpotCard from "../components/SpotCard";
import Footer from "../components/Footer";
import { useSpots } from "../lib/hooks";
import { MapIcon } from "../lib/icons";

/**
 * "surfwind data" landing. Two parts that flow into each other on scroll:
 *  1. A full-screen hero photo carrying the header, the search bar and the
 *     "aktuelle Top Spots" row.
 *  2. An extended white section below (no hero photo) with all spots shown as
 *     Airbnb-style cards. A rounded white sheet rises over the hero's bottom for
 *     a seamless hand-off.
 */
export default function Landing() {
  const location = useLocation();
  // Remember where the map is opened from, so its close button can return here.
  const from = location.pathname + location.search;
  const [visibleSpotLimit, setVisibleSpotLimit] = useState(20);
  // Mobile search sheet (Airbnb-style full-screen flow); desktop keeps the
  // inline SearchBar dropdown. `searchOriginY` lets the sheet grow out of the
  // collapsed pill's position.
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchOriginY, setSearchOriginY] = useState<number | null>(null);
  const openSearch = () => {
    const rect = document.getElementById("landing-search")?.getBoundingClientRect();
    setSearchOriginY(rect ? rect.top + rect.height / 2 : null);
    setSearchOpen(true);
  };
  // Fetch the lightweight catalogue once. Changing the request key from 20 to
  // 100 used to temporarily unmount the entire grid while the second request
  // ran; the page height collapsed and clamped the visitor's scroll position
  // toward the top. Card images are still mounted only as they become visible
  // and remain native lazy-loaded, so this does not eagerly download 100 photos.
  const { data: allSpots, loading: spotsLoading } = useSpots({ limit: 100 });
  const spots = allSpots ?? [];
  const visibleSpots = spots.slice(0, visibleSpotLimit);

  return (
    <div className="relative bg-page">
      <LandingHeader sticky />

      {/* 1 — Hero screen. The hero image sits at z-0 (a positioned descendant, so
          it paints above the page's white background but below the search bar).
          No `isolate` here — an isolated stacking context would trap the search
          bar (z-1200) *below* the portal scrim (z-1100), so clicking "Wann" would
          hit the scrim and close instead of switching the panel. */}
      <section className="relative flex min-h-[100dvh] flex-col overflow-hidden">
        <LandingHero spots={spots} />

        <h1 className="sr-only">
          surfwind data · die beste Sammlung von Surfspots und Windspots
        </h1>

        <div className="flex-1" />

        {/* Search — sits high in the hero so the (compact) dropdown always fits
            above the fold and never reaches into the white spots section. */}
        <div className="flex justify-center px-4 pb-44 sm:px-6 sm:pb-56">
          <div id="landing-search" className="relative z-[1200] w-full max-w-[760px]">
            {/* Mobile: collapsed pill → full-screen sheet. From sm: inline bar.
                Hidden (but kept in layout) while the sheet is open so it does
                not show through the sheet's translucent backdrop. */}
            <div className={`sm:hidden ${searchOpen ? "invisible" : ""}`}>
              <MobileSearchTrigger onClick={openSearch} />
            </div>
            <div className="hidden sm:block">
              <SearchBar />
            </div>
          </div>
        </div>
      </section>

      <MobileSearchSheet
        open={searchOpen}
        originY={searchOriginY}
        onClose={() => setSearchOpen(false)}
      />

      {/* 2 — Extended white section: aktuelle Top Spots (moved here onto the
          white background) + all spots as Airbnb-style cards. The rounded sheet
          rises over the hero for a seamless transition. */}
      <section className="relative z-10 -mt-5 rounded-t-3xl bg-page">
        {/* aktuelle Top Spots — title left, map button right, now on white. */}
        <div className="mx-auto w-full max-w-[1570px] pt-10">
          <div className="mb-3 flex items-center justify-between gap-4 px-4 sm:px-10">
            <h2 className="text-[22px] font-semibold text-ink">aktuelle Top Spots</h2>
            <Link
              to="/map"
              state={{ from }}
              aria-label="Karte öffnen"
              className="inline-flex min-h-11 shrink-0 items-center gap-2 px-2 text-[15px] font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              <MapIcon className="text-[18px]" />
              <span className="hidden sm:inline">Karte</span>
            </Link>
          </div>
          <TopSpotsRow />
        </div>

        <div className="mx-auto max-w-[1570px] px-4 pb-16 pt-12 sm:px-8">
          <h2 className="text-[22px] font-semibold text-ink">Alle Spots entdecken</h2>
          <p className="mt-1 text-[15px] text-muted">
            Stöbere durch die ganze Sammlung · Regionen, Windspots und Wellenspots.
          </p>

          {spots.length > 0 && (
            <div className="mt-6 grid auto-rows-fr grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-8 sm:gap-y-10 lg:grid-cols-5">
              {visibleSpots.map((spot) => (
                <SpotCard key={spot.id} spot={spot} />
              ))}
            </div>
          )}

          {!spotsLoading && visibleSpotLimit < spots.length && (
            <div className="mt-10 flex justify-center">
              <button
                type="button"
                onClick={() => setVisibleSpotLimit(spots.length)}
                className="min-h-11 px-5 py-2.5 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
              >
                Alle Spots anzeigen
              </button>
            </div>
          )}
        </div>
      </section>

      <Footer />
    </div>
  );
}
