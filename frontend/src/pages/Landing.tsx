import { Link, useLocation } from "react-router-dom";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
import LandingHeader from "../components/LandingHeader";
import LandingHero from "../components/LandingHero";
import MobileSearchTrigger from "../components/MobileSearchTrigger";
import RecommendationRow from "../components/RecommendationRow";
import SpotCard from "../components/SpotCard";
import Footer from "../components/Footer";
import { ErrorBanner } from "../components/AsyncStates";
import LandingFilters from "../components/LandingFilters";
import { useLandingSpots, useSpots } from "../lib/hooks";
import { countryName } from "../lib/flags";
import { MapIcon } from "../lib/icons";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import { useAuth } from "../context/AuthContext";

type SortMode = "recommended" | "az";

// The recommendation surfaces serve every sport plus the cross-sport aggregate;
// "all" (no sport filter) ranks each spot by the single sport it is best for.
const AGGREGATE_SPORT = "all";

/** ISO week (1-53) for a date, used to build the climatology "next weeks" window. */
function isoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

const SearchBar = lazy(() => import("../components/SearchBar"));
const MobileSearchSheet = lazy(() => import("../components/MobileSearchSheet"));
// "Alle Spots anzeigen" used to jump the grid from 20 to the full catalogue
// (up to 500 cards) in a single render — a long synchronous mount/layout that
// froze the tap for a second or more. Reveal one screen's worth at a time
// instead and let the rest stream in on scroll, so each step stays cheap.
const SPOT_REVEAL_STEP = 40;

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
  const { user } = useAuth();
  // Global landing filters (opened from the "Filter" panel, top-right). "" = no
  // constraint on that axis; sort defaults to "recommended".
  const [filterSport, setFilterSport] = useState<string>("");
  const [filterCountry, setFilterCountry] = useState<string>("");
  const [filterLevel, setFilterLevel] = useState<string>("");
  const [sortMode, setSortMode] = useState<SortMode>("recommended");
  // Signed-in only: rank like a logged-out visitor (ignore the rider profile).
  const [ignorePersonalization, setIgnorePersonalization] = useState(false);
  // Climatology "next ~2 months" window for the last recommendation row.
  const nextWeeks = useMemo(() => {
    const start = isoWeek(new Date());
    return `${start}-${Math.min(52, start + 8)}`;
  }, []);
  // A chosen sport feeds the rows directly; "Alle Sportarten" ranks the
  // cross-sport aggregate. Only kitesurf is truly personalized (rider band);
  // other sports use level offsets, and the aggregate is always anonymous.
  const rowSport = filterSport || AGGREGATE_SPORT;
  const personalized = Boolean(user) && !ignorePersonalization;
  const personalizedTitle = personalized && rowSport !== AGGREGATE_SPORT;
  // The three recommendation rows only make sense in "recommended" order.
  const showRows = sortMode === "recommended";
  // Remember where the map is opened from, so its close button can return here.
  const from = location.pathname + location.search;
  const [visibleSpotLimit, setVisibleSpotLimit] = useState(20);
  // Once the visitor opts into the full catalogue, further batches stream in as
  // they scroll toward the end (see the sentinel effect below).
  const [browseAll, setBrowseAll] = useState(false);
  const [, startRevealTransition] = useTransition();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  // Mobile search sheet (Airbnb-style full-screen flow); desktop keeps the
  // inline SearchBar dropdown. The sheet is a full-screen overlay that locks
  // body scroll while open, so we deliberately do NOT scroll to the top when
  // opening: the visitor stays exactly where they were and, on close, keeps
  // scrolling from that same point.
  const [searchOpen, setSearchOpen] = useState(false);
  // Mobile: once the hero search pill reaches the header line it must vanish —
  // the docked header lupe takes over — instead of scrolling up over the fixed
  // bar. Triggered at the same sentinel/point as the header hardening.
  const [heroSearchDocked, setHeroSearchDocked] = useState(false);
  const [mobileSearchLoaded, setMobileSearchLoaded] = useState(false);
  const mobileSearchTriggerRef = useRef<HTMLButtonElement | null>(null);
  const desktopSearch = useDesktopViewport();
  const openSearch = (trigger: HTMLButtonElement) => {
    mobileSearchTriggerRef.current = trigger;
    setMobileSearchLoaded(true);
    setSearchOpen(true);
  };

  // Warm the search-sheet chunk on idle so the first tap — from the hero pill or
  // the docked header lupe — opens instantly, with no lazy-chunk stall before
  // the slide-up begins.
  useEffect(() => {
    const preload = () => void import("../components/MobileSearchSheet");
    const idle = window as typeof window & {
      requestIdleCallback?: (cb: () => void) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (idle.requestIdleCallback) {
      const id = idle.requestIdleCallback(preload);
      return () => idle.cancelIdleCallback?.(id);
    }
    const timer = window.setTimeout(preload, 1200);
    return () => window.clearTimeout(timer);
  }, []);

  // Mobile only: watch the same header sentinel and fade the hero search pill
  // out the moment it reaches the header line, so it disappears into the
  // hardening bar (which shows the lupe) instead of scrolling up over it.
  useEffect(() => {
    const nativeTouch = window.matchMedia("(pointer: coarse) and (hover: none)").matches;
    if (!nativeTouch || !("IntersectionObserver" in window)) return;
    const sentinel = document.querySelector<HTMLElement>("[data-landing-header-sentinel]");
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      ([entry]) => setHeroSearchDocked(!entry.isIntersecting),
      { rootMargin: "-84px 0px 0px 0px", threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);
  // First paint is a bounded bundle: 24 alphabetic cards plus any curated hero
  // records. The 500-row catalogue is fetched only after the visitor asks to
  // browse/filter/sort it, keeping payload, DB serialization and React work off
  // the critical path.
  const landing = useLandingSpots();
  const anyFilterActive = Boolean(filterSport) || Boolean(filterCountry) || Boolean(filterLevel);
  const fullCatalogueEnabled = browseAll || anyFilterActive || sortMode === "az";
  const fullCatalogue = useSpots({ limit: 500 }, fullCatalogueEnabled);
  const spots = useMemo(
    () => fullCatalogue.data ?? landing.data?.spots ?? [],
    [fullCatalogue.data, landing.data],
  );
  const catalogueTotal = landing.data?.total ?? spots.length;
  const spotsLoading = landing.loading || (fullCatalogueEnabled && fullCatalogue.loading && !fullCatalogue.data);
  const spotsError = spots.length === 0 ? (landing.error ?? fullCatalogue.error) : undefined;
  const reloadSpots = fullCatalogueEnabled ? fullCatalogue.reload : landing.reload;
  // Land options for the filter panel: distinct countries present in the loaded
  // catalogue, sorted by their display name.
  const countryOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const spot of spots) {
      const code = spot.regionCountry;
      if (code && !seen.has(code)) seen.set(code, countryName(code) ?? code);
    }
    return [...seen.entries()]
      .map(([code, name]) => ({ code, name }))
      .sort((a, b) => a.name.localeCompare(b.name, "de"));
  }, [spots]);

  // "Alle Spots" grid honours the global filters: sport membership + land +
  // level, then sort (recommended = catalogue order, or A–Z by name).
  const gridSpots = useMemo(() => {
    let list = spots;
    if (filterSport) list = list.filter((spot) => (spot.sports ?? []).includes(filterSport));
    if (filterCountry) list = list.filter((spot) => spot.regionCountry === filterCountry);
    if (filterLevel) list = list.filter((spot) => (spot.level ?? []).includes(filterLevel));
    if (sortMode === "az") list = [...list].sort((a, b) => a.name.localeCompare(b.name, "de"));
    return list;
  }, [spots, filterSport, filterCountry, filterLevel, sortMode]);
  const visibleSpots = gridSpots.slice(0, visibleSpotLimit);

  // Reveal the next batch off the main thread so the tap (and each subsequent
  // scroll step) stays responsive even while dozens of cards mount.
  const revealMore = useCallback(() => {
    startRevealTransition(() =>
      setVisibleSpotLimit((n) => Math.min(n + SPOT_REVEAL_STEP, gridSpots.length)),
    );
  }, [gridSpots.length]);

  // While browsing the full catalogue, load more as the end of the grid nears —
  // a wide rootMargin means the next batch is ready before the visitor reaches
  // the bottom, so scrolling never stalls waiting on a render.
  useEffect(() => {
    if (!browseAll || visibleSpotLimit >= gridSpots.length) return;
    const sentinel = loadMoreRef.current;
    if (!sentinel || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) revealMore();
      },
      { rootMargin: "800px 0px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [browseAll, visibleSpotLimit, gridSpots.length, revealMore]);

  return (
    <div className="relative bg-page">
      <LandingHeader sticky showMenu onMobileSearch={openSearch} />

      {/* 1 — Hero screen. The hero image sits at z-0 (a positioned descendant, so
          it paints above the page's white background but below the search bar).
          No `isolate` here — an isolated stacking context would trap the search
          bar (z-modal) *below* the portal scrim (z-scrim), so clicking "Wann" would
          hit the scrim and close instead of switching the panel. */}
      {/* `svh`, not `dvh`: the small-viewport height is fixed, so when iOS
          Safari's URL bar collapses on scroll the hero does NOT grow and its
          object-cover crop does NOT rescale — the photo stays steady (no
          zoom-in) and the page stops reflowing every scroll frame (no stutter).
          The old `dvh` recalculated continuously as the chrome animated. */}
      <section className="relative flex min-h-[92svh] flex-col overflow-hidden sm:min-h-[100svh]">
        <LandingHero spots={spots} />

        <h1 className="sr-only">
          surfwind data · die beste Sammlung von Surfspots und Windspots
        </h1>

        <div className="flex-1" />

        {/* Search — vertically centered in the desktop hero. On mobile it is the search
            entry and docks into the header once scrolled (see LandingHeader);
            the inline SearchBar dropdown takes over from sm. */}
        <div className="flex justify-center px-4 pb-32 sm:absolute sm:inset-0 sm:items-center sm:px-6 sm:pb-0">
          <div id="landing-search" className="relative z-modal w-full max-w-content">
            <span data-landing-header-sentinel aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px" />
            {/* Mobile pill; hidden (kept in layout) while the sheet is open. It
                disappears immediately at the header line so it cannot overlap it. */}
            <div
              className={`sm:hidden ${searchOpen ? "invisible" : ""} ${
                heroSearchDocked
                  ? "invisible pointer-events-none opacity-0"
                  : "opacity-100 transition-opacity duration-base"
              }`}
            >
              <MobileSearchTrigger onClick={openSearch} />
            </div>
            <div className="hidden sm:block">
              {desktopSearch && (
                <Suspense fallback={<div aria-hidden className="h-14 w-full rounded-card bg-surface/90 shadow-float" />}>
                  <SearchBar />
                </Suspense>
              )}
            </div>
          </div>
        </div>
      </section>

      {mobileSearchLoaded && (
        <Suspense fallback={null}>
          <MobileSearchSheet
            open={searchOpen}
            onClose={() => setSearchOpen(false)}
            returnFocusRef={mobileSearchTriggerRef}
          />
        </Suspense>
      )}

      {/* 2 — Extended white section: aktuelle Top Spots (moved here onto the
          white background) + all spots as Airbnb-style cards. The rounded sheet
          rises over the hero for a seamless transition. */}
      <section className="relative z-10 -mt-5 rounded-t-card bg-page">
        <div className="mx-auto w-full max-w-page px-4 pt-10 sm:px-10">
          {/* Header row: the first-row heading (recommended mode) on the left
              and the filter icon on the right, on the same line. In A–Z mode the
              ranked rows are hidden, so only the filter icon remains. The single
              "Filter" button opens a panel with sort + sport + land + level (+ a
              personalization toggle when signed in). Sport applies to the rows
              and the "Alle Spots" grid; land/level narrow the grid. */}
          <div className="mb-6 flex min-h-11 items-center justify-between gap-4">
            {showRows ? (
              <h2 className="text-lead font-semibold text-ink">
                {personalizedTitle ? "Deine aktuellen Topspots" : "Aktuelle Topspots"}
              </h2>
            ) : (
              <span aria-hidden />
            )}
            <div className="flex items-center gap-2">
              {showRows && (
                <Link
                  to="/map"
                  state={{ from }}
                  aria-label="Karte öffnen"
                  className="hidden min-h-11 shrink-0 items-center gap-2 px-2 text-body font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70 lg:inline-flex"
                >
                  <MapIcon className="text-lead" />
                  <span className="hidden sm:inline">Karte</span>
                </Link>
              )}
              <LandingFilters
                sort={sortMode}
                onSort={setSortMode}
                sport={filterSport}
                onSport={setFilterSport}
                country={filterCountry}
                onCountry={setFilterCountry}
                countries={countryOptions}
                level={filterLevel}
                onLevel={setFilterLevel}
                showPersonalization={Boolean(user)}
                ignorePersonalization={ignorePersonalization}
                onIgnorePersonalization={setIgnorePersonalization}
                onReset={() => {
                  setSortMode("recommended");
                  setFilterSport("");
                  setFilterCountry("");
                  setFilterLevel("");
                }}
              />
            </div>
          </div>

          {showRows && (
            <>
              <RecommendationRow
                title={personalizedTitle ? "Deine aktuellen Topspots" : "Aktuelle Topspots"}
                surface="now"
                sport={rowSport}
                personalized={personalized}
                defer
                hideHeader
              />
              <RecommendationRow
                title="Topspots in der nächsten Woche"
                surface="next_week"
                sport={rowSport}
                personalized={personalized}
                defer
                className="mt-12"
              />
              <RecommendationRow
                title="Topspots in der nächsten Zeit"
                surface="season"
                sport={rowSport}
                personalized={personalized}
                defer
                weeks={nextWeeks}
                className="mt-12"
              />
            </>
          )}
        </div>

        <div className="mx-auto max-w-page px-4 pb-16 pt-12 sm:px-8">
          <h2 className="text-lead font-semibold text-ink">Alle Spots entdecken</h2>

          {spotsError && spots.length === 0 && (
            <div className="mt-6 max-w-2xl">
              <ErrorBanner
                title="Die Spots sind gerade nicht erreichbar."
                message={spotsError}
                onRetry={reloadSpots}
              />
            </div>
          )}

          {gridSpots.length > 0 && (
            <div className="mt-6 grid auto-rows-fr grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-8 sm:gap-y-10 lg:grid-cols-5">
              {visibleSpots.map((spot) => (
                <SpotCard key={spot.id} spot={spot} eager={false} />
              ))}
            </div>
          )}

          {anyFilterActive && gridSpots.length === 0 && spots.length > 0 && (
            <p className="mt-6 text-body text-muted">Keine Spots für diese Auswahl.</p>
          )}

          {!spotsLoading && !browseAll && catalogueTotal > visibleSpotLimit && (
            <div className="mt-10 flex justify-center">
              <button
                type="button"
                onClick={() => {
                  setBrowseAll(true);
                  revealMore();
                }}
                className="min-h-11 px-5 py-2.5 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
              >
                Alle Spots anzeigen
              </button>
            </div>
          )}

          {/* Streaming sentinel — once "Alle Spots anzeigen" is pressed, this
              marker below the grid pulls the next batch in as it nears view. */}
          {browseAll && visibleSpotLimit < gridSpots.length && (
            <div ref={loadMoreRef} aria-hidden className="h-px w-full" />
          )}
        </div>
      </section>

      {/* Mobile: floating map access, bottom-centre — mirrors the results page's
          "Karte" pill instead of a fixed icon in the topspots row header. Its
          semantic page colours follow the surrounding background in both
          themes; elevation keeps the control distinct from the content. */}
      <Link
        to="/map"
        state={{ from }}
        aria-label="Karte öffnen"
        className="fixed bottom-6 left-1/2 z-sticky flex -translate-x-1/2 items-center gap-1.5 rounded-card bg-page px-4 py-2 text-ui font-normal text-ink shadow-float lg:hidden"
      >
        Karte <MapIcon className="text-body" />
      </Link>

      <Footer />
    </div>
  );
}
