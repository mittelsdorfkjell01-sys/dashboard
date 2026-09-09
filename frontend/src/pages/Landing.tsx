import { Link, useLocation } from "react-router-dom";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import LandingHeader from "../components/LandingHeader";
import LandingHero from "../components/LandingHero";
import MobileSearchTrigger from "../components/MobileSearchTrigger";
import TopSpotsRow from "../components/TopSpotsRow";
import SpotCard from "../components/SpotCard";
import Footer from "../components/Footer";
import { EmptyState, ErrorBanner, SpotGridSkeleton } from "../components/AsyncStates";
import { useSpots } from "../lib/hooks";
import { getSpotCatalogVersion } from "../lib/api";
import { MapIcon } from "../lib/icons";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import { usePageMeta } from "../lib/pageMeta";

const SearchBar = lazy(() => import("../components/SearchBar"));
const MobileSearchSheet = lazy(() => import("../components/MobileSearchSheet"));
const CATALOG_POLL_MS = 60_000;

/**
 * "surfwind data" landing. Two parts that flow into each other on scroll:
 *  1. A full-screen hero photo carrying the header, the search bar and the
 *     "aktuelle Top Spots" row.
 *  2. An extended white section below (no hero photo) with all spots shown as
 *     Airbnb-style cards. A rounded white sheet rises over the hero's bottom for
 *     a seamless hand-off.
 */
export default function Landing() {
  usePageMeta({
    title: "Surfspots finden: Wind, Wellen & Vorhersage | surfwind data",
    description: "Entdecke Surf-, Kite-, Wing- und Windsurfspots, vergleiche aktuelle Bedingungen und finde die passende Reisezeit.",
    canonicalPath: "/",
  });
  const location = useLocation();
  // Remember where the map is opened from, so its close button can return here.
  const from = location.pathname + location.search;
  const [visibleSpotLimit, setVisibleSpotLimit] = useState(20);
  // Mobile search sheet (Airbnb-style full-screen flow); desktop keeps the
  // inline SearchBar dropdown. The sheet is a full-screen overlay that locks
  // body scroll while open, so we deliberately do NOT scroll to the top when
  // opening: the visitor stays exactly where they were and, on close, keeps
  // scrolling from that same point.
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileSearchLoaded, setMobileSearchLoaded] = useState(false);
  const mobileSearchTriggerRef = useRef<HTMLButtonElement | null>(null);
  const knownCatalogVersion = useRef<string>();
  const [catalogVersion, setCatalogVersion] = useState<string>();
  const [catalogReady, setCatalogReady] = useState(false);
  const desktopSearch = useDesktopViewport();
  const openSearch = (trigger: HTMLButtonElement) => {
    mobileSearchTriggerRef.current = trigger;
    setMobileSearchLoaded(true);
    setSearchOpen(true);
  };
  // Hero curation is editorial state, so the seven-day persisted catalogue and
  // the unversioned edge response must not decide which photos rotate. Resolve
  // the current catalogue version first and keep checking it while the landing
  // page is open. A changed hero_reel flag updates Spot.updated_at, producing a
  // new immutable request URL and replacing the reel without a hard refresh.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let versionRequest: Promise<void> | null = null;

    const checkVersion = async () => {
      if (document.visibilityState === "hidden" || versionRequest) return versionRequest;
      versionRequest = (async () => {
        try {
          const { version } = await getSpotCatalogVersion();
          if (!cancelled && version !== knownCatalogVersion.current) {
            knownCatalogVersion.current = version;
            setCatalogVersion(version);
          }
        } catch {
          // If the lightweight version lookup alone fails, still try the list
          // through a unique URL instead of reviving a stale persisted reel.
          if (!cancelled && !knownCatalogVersion.current) {
            const fallbackVersion = `landing-${Date.now()}`;
            knownCatalogVersion.current = fallbackVersion;
            setCatalogVersion(fallbackVersion);
          }
        } finally {
          if (!cancelled) setCatalogReady(true);
          versionRequest = null;
        }
      })();
      return versionRequest;
    };

    const schedule = () => {
      if (cancelled) return;
      timer = window.setTimeout(async () => {
        await checkVersion();
        schedule();
      }, CATALOG_POLL_MS);
    };
    const refreshNow = () => {
      if (document.visibilityState !== "hidden") void checkVersion();
    };

    void checkVersion();
    schedule();
    document.addEventListener("visibilitychange", refreshNow);
    window.addEventListener("online", refreshNow);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", refreshNow);
      window.removeEventListener("online", refreshNow);
    };
  }, []);

  // Fetch all published records so a curated photo beyond the first 100 spots
  // cannot disappear from the reel. Only the first 20 cards mount initially,
  // keeping their immediate image requests bounded.
  const {
    data: allSpots,
    loading: spotsLoading,
    error: spotsError,
    reload: reloadSpots,
  } = useSpots(
    { limit: 500, catalog_version: catalogVersion },
    catalogReady,
  );
  const spots = allSpots ?? [];
  const visibleSpots = spots.slice(0, visibleSpotLimit);

  return (
    <div className="relative bg-page">
      <LandingHeader sticky onMobileSearch={openSearch} />

      {/* 1 — Hero screen. The hero image sits at z-0 (a positioned descendant, so
          it paints above the page's white background but below the search bar).
          No `isolate` here — an isolated stacking context would trap the search
          bar (z-1200) *below* the portal scrim (z-1100), so clicking "Wann" would
          hit the scrim and close instead of switching the panel. */}
      <section className="relative flex min-h-[92dvh] flex-col overflow-hidden sm:min-h-[100dvh]">
        <LandingHero spots={spots} />

        <div className="flex-1" />

        {/* The visible promise gives first-time visitors enough context before
            the primary search action. It remains concise so the hero still
            reads as a calm entry rather than a marketing page. */}
        <div className="relative z-10 flex flex-col items-center px-4 pb-32 text-center sm:px-6 sm:pb-40">
          <div className="max-w-[900px] text-white [text-shadow:0_2px_24px_rgba(0,0,0,0.45)]">
            <h1 className="text-display-1 font-semibold text-balance">
              Finde den Spot, der zu Wind, Welle und dir passt.
            </h1>
            <p className="mx-auto mt-3 max-w-[62ch] text-body text-white/90 sm:text-sz-18">
              Aktuelle Bedingungen, Vorhersage und Saisonwissen für Surf-, Kite-, Wing- und Windsurfspots.
            </p>
          </div>

          {/* Search — sits below the promise. On mobile it is the search entry
              and docks into the header once scrolled (see LandingHeader); the
              inline SearchBar dropdown takes over from sm. */}
          <div id="landing-search" className="relative z-[1200] mt-6 w-full max-w-[760px]">
            <span data-landing-header-sentinel aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px" />
            {/* Mobile pill; hidden (kept in layout) while the sheet is open. */}
            <div className={`sm:hidden ${searchOpen ? "invisible" : ""}`}>
              <MobileSearchTrigger onClick={openSearch} />
            </div>
            <div className="hidden sm:block">
              {desktopSearch && (
                <Suspense fallback={<div aria-hidden className="h-14 w-full rounded-[14px] bg-surface/90 shadow-float" />}>
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
      <section className="relative z-10 -mt-5 rounded-t-3xl bg-page">
        {/* aktuelle Top Spots — title left, map button right, now on white. */}
        <div className="mx-auto w-full max-w-[1570px] pt-10">
          <div className="mb-3 flex items-center justify-between gap-4 px-4 sm:px-10">
            <div>
              <h2 className="text-sz-22 font-semibold text-ink">Aktuelle Top-Spots</h2>
              <p className="mt-1 max-w-[64ch] text-caption text-muted">
                Täglich neu gewichtet nach 7-Tage-Windvorhersage, heutigen Bedingungen und Community-Signalen.
              </p>
            </div>
            <Link
              to="/map"
              state={{ from }}
              aria-label="Karte öffnen"
              className="inline-flex min-h-11 shrink-0 items-center gap-2 px-2 text-body font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              <MapIcon className="text-sz-18" />
              <span className="hidden sm:inline">Karte</span>
            </Link>
          </div>
          <TopSpotsRow />
        </div>

        <div className="mx-auto w-full max-w-[1570px] px-4 pt-14 sm:px-8">
          <div className="border-y border-line py-10 sm:py-12">
            <p className="label-caps">Einfach entscheiden</p>
            <div className="mt-3 grid gap-8 lg:grid-cols-[1.15fr_2fr] lg:gap-16">
              <div>
                <h2 className="text-display-2 font-semibold text-balance text-ink">
                  Von der Idee zur passenden Session.
                </h2>
                <p className="mt-4 max-w-[52ch] text-body leading-relaxed text-ink-soft">
                  Suche einen Ort, vergleiche die Bedingungen und prüfe, wann ein Spot typischerweise funktioniert.
                </p>
              </div>
              <ol className="grid gap-6 sm:grid-cols-3">
                {[
                  ["01", "Ort wählen", "Suche nach Spot oder Region – oder starte bewusst ohne festes Ziel."],
                  ["02", "Bedingungen vergleichen", "Ordne Wind, Wellen und Vorhersage ein, ohne zwischen Diensten zu springen."],
                  ["03", "Zeitraum verstehen", "Nutze aktuelle Daten für die nächste Session und Saisonwerte für die Reiseplanung."],
                ].map(([number, title, copy]) => (
                  <li key={number}>
                    <span className="text-caption font-semibold text-orange">{number}</span>
                    <h3 className="mt-2 text-body font-semibold text-ink">{title}</h3>
                    <p className="mt-2 text-caption leading-relaxed text-muted">{copy}</p>
                  </li>
                ))}
              </ol>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-ui font-semibold">
              <Link to="/search" className="text-ink hover:underline hover:underline-offset-4">Spots vergleichen</Link>
              <Link to="/map" state={{ from }} className="text-ink hover:underline hover:underline-offset-4">Auf der Karte entdecken</Link>
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-[1570px] px-4 pb-16 pt-12 sm:px-8">
          <h2 className="text-sz-22 font-semibold text-ink">Surf- und Windspots entdecken</h2>
          <p className="mt-1 text-body text-muted">
            Stöbere durch die Sammlung und öffne einen Spot für Details, Vorhersage und Saisonwerte.
          </p>

          {spotsLoading && spots.length === 0 && (
            <div className="mt-6" role="status" aria-label="Spots werden geladen">
              <SpotGridSkeleton count={10} />
            </div>
          )}

          {spotsError && spots.length === 0 && (
            <div className="mt-6">
              <ErrorBanner message={spotsError} onRetry={reloadSpots} />
            </div>
          )}

          {spots.length > 0 && (
            <div className="mt-6 grid auto-rows-fr grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-8 sm:gap-y-10 lg:grid-cols-5">
              {visibleSpots.map((spot, index) => (
                <SpotCard key={spot.id} spot={spot} eager={index < 20} />
              ))}
            </div>
          )}

          {!spotsLoading && !spotsError && spots.length === 0 && (
            <div className="mt-6">
              <EmptyState message="Noch sind keine veröffentlichten Spots verfügbar." />
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
