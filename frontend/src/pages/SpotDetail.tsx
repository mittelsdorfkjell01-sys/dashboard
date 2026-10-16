import { Component, lazy, Suspense, useEffect, useRef, useState, type CSSProperties, type ErrorInfo, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import LandingHeader from "../components/LandingHeader";
import Facilities from "../components/Facilities";
import SpotTabs from "../components/SpotTabs";
import DatenPage from "../components/data/daten/DatenPage";
import SpotGalleryTile from "../components/SpotGalleryTile";
import PhotoGalleryOverlay from "../components/PhotoGalleryOverlay";
import SpotCommentBox from "../components/SpotCommentBox";
import FavoriteButton from "../components/FavoriteButton";
import ShareButton from "../components/ShareButton";
import SuggestEditButton from "../components/SuggestEditButton";
import VisitedButton from "../components/VisitedButton";
import Footer from "../components/Footer";
import SimilarSpots from "../components/SimilarSpots";
import SpotOriginMark, { SpotOriginLine } from "../components/SpotOriginMark";
import SpotMetaGrid from "../components/SpotMetaGrid";
import SpotDescription from "../components/SpotDescription";
import { EditorialHero, SectionBand } from "../components/editorial";
import { ErrorBanner } from "../components/AsyncStates";
import { ChevronDownIcon, CheckCircleIcon } from "../lib/icons";
import { sportLabel } from "../lib/labels";
import { regionSlug } from "../lib/types";
import { sortFeed } from "../lib/communityFeed";
import { useSpot, useSpotLive, useSpotForecast, useCommunityFeed, useSpotBestSeason } from "../lib/hooks";
import { facilitiesFromMap } from "../lib/spotView";
import { mapLinkProps } from "../lib/mapLinks";
import { spotPath } from "../lib/spotRoutes";

const SPOT_INFO_GRID = "lg:grid-cols-[minmax(320px,1fr)_minmax(420px,560px)_minmax(320px,1fr)]";
const LocatorMap = lazy(() => import("../components/LocatorMap"));

export default function SpotDetail() {
  const { spotName } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const activeTab = location.pathname.endsWith("/daten") ? "daten" : "info";
  const reduceMotion = useReducedMotion();

  // Direction for the tab-content swap: which side the new content slides in
  // from. Comparing against the previous tab index (kept in a ref) each
  // render is the standard way to derive this without lagging a render
  // behind, the way computing it in an effect would.
  const TAB_ORDER = ["info", "daten"];
  const tabIndex = TAB_ORDER.indexOf(activeTab);
  const prevTabIndexRef = useRef(tabIndex);
  const tabDirection = tabIndex - prevTabIndexRef.current >= 0 ? 1 : -1;
  prevTabIndexRef.current = tabIndex;

  // Old content slides 12px toward the side it came from and fades out; new
  // content slides in from the side it's headed toward — direction is what
  // makes the swap read as "moving" instead of every switch looking the same.
  const tabContentVariants = {
    enter: (dir: number) => (reduceMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: dir >= 0 ? 12 : -12 }),
    center: { opacity: 1, x: 0 },
    exit: (dir: number) => (reduceMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: dir >= 0 ? -12 : 12 }),
  };

  const { data: spot, loading, error, errorStatus, reload } = useSpot(spotName);
  const spotId = spot?.uuid;
  const {
    data: live,
    loading: liveLoading,
    error: liveError,
    stale: liveStale,
    reload: reloadLive,
  } = useSpotLive(activeTab === "daten" ? spotId : undefined);
  const { data: forecast, loading: forecastLoading, error: forecastError } =
    useSpotForecast(activeTab === "daten" ? spotId : undefined);
  const { posts, photos, loading: commentsLoading, error: commentsError, reload: reloadFeed, addTip } =
    useCommunityFeed(activeTab === "info" ? spotId : undefined);
  // Best travel season — surfaced on both tabs (a line in the Info identity
  // column, a jump link in the Daten header). Best-effort; null hides it.
  const bestSeason = useSpotBestSeason(spot?.id);
  useEffect(() => {
    if (!spot) return;
    const canonical = spotPath(spot, activeTab);
    if (location.pathname !== canonical) {
      const preserveScroll = typeof location.state?.preserveScroll === "number";
      navigate(canonical, {
        replace: true,
        state: location.state,
        preventScrollReset: preserveScroll,
      });
    }
  }, [activeTab, location.pathname, location.state, navigate, spot]);

  const [galleryOpen, setGalleryOpen] = useState(false);
  const galleryTriggerRef = useRef<HTMLButtonElement>(null);
  const galleryFrameRef = useRef<HTMLDivElement>(null);
  const [galleryHeight, setGalleryHeight] = useState<number>();
  const [galleryRightInset, setGalleryRightInset] = useState(0);
  const mapSlotRef = useRef<HTMLDivElement>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const frame = galleryFrameRef.current;
    if (!frame) return;
    const measure = () => {
      const tile = frame.firstElementChild as HTMLElement | null;
      setGalleryHeight(tile?.offsetHeight ?? frame.offsetHeight);
      setGalleryRightInset(Math.max(0, frame.offsetWidth - (tile?.offsetWidth ?? frame.offsetWidth)));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(frame);
    return () => observer.disconnect();
  }, [activeTab, loading, photos.length]);

  useEffect(() => {
    if (activeTab !== "info" || loading || mapReady) return;
    const slot = mapSlotRef.current;
    if (!slot) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setMapReady(true);
        observer.disconnect();
      },
      { rootMargin: "500px 0px" },
    );
    observer.observe(slot);
    return () => observer.disconnect();
  }, [activeTab, loading, mapReady]);

  // From a spot page the back arrow always returns to the landing page,
  // regardless of the active tab (Info/Daten) or how the visitor arrived.
  const goBack = () => navigate("/");

  if (loading) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader />
        <div className="hero-h w-full animate-pulse bg-ink-soft" />
        <div className="mx-auto max-w-page px-4 pt-16 sm:px-8">
          <div className="h-8 w-2/3 animate-pulse rounded-card bg-line" />
          <div className="mt-4 h-4 w-full animate-pulse rounded-card bg-line" />
        </div>
      </div>
    );
  }

  if (error || !spot) {
    const notFound = errorStatus === 404 || (!error && !spot);
    return (
      <div className="grid min-h-screen place-items-center bg-page px-6 text-center">
        <div>
          <h1 className="text-title font-semibold text-ink">
            {notFound ? "Spot nicht gefunden" : "Spot momentan nicht verfügbar"}
          </h1>
          {error && (
            <div className="mt-4 max-w-md">
              <ErrorBanner
                title={notFound ? "Prüfe den Namen oder kehre zur Übersicht zurück." : "Die Spotdaten konnten nicht geladen werden."}
                message={error}
                onRetry={reload}
              />
            </div>
          )}
          <Link to="/" className="mt-4 inline-flex min-h-11 items-center text-body text-ink underline underline-offset-4">
            Zurück zur Übersicht
          </Link>
        </div>
      </div>
    );
  }

  // All from the backend record — no synthetic data.
  const facilities = facilitiesFromMap(spot.facilities);
  const [regionPart, country] = spot.region.split(",").map((p) => p.trim());

  // Most recent posts first — the teaser tile shows the newest one, the
  // "mehr" overlay shows up to three.
  const sortedPosts = sortFeed(posts, "newest", {});
  // The teaser shows the newest post that actually has text — a photo-only
  // post isn't a "comment", and its absence triggers the write-first prompt.

  const tabs = [
    { id: "info", label: "Info", href: spotPath(spot, "info") },
    { id: "daten", label: "Daten", href: spotPath(spot, "daten") },
  ];

  return (
    <div className="spot-detail-page relative min-h-screen min-w-0 max-w-full overflow-x-clip bg-page">
      <LandingHeader
        width="body"
        mobileSpotControls
        left={
          <button
            type="button"
            onClick={goBack}
            aria-label="Zurück"
            className="pointer-events-auto inline-flex h-11 w-11 items-center justify-center gap-1.5 bg-transparent p-0 text-ui font-medium text-white transition-colors hover:text-on-photo sm:h-auto sm:w-auto sm:justify-start sm:rounded-card sm:bg-teal sm:py-2 sm:pl-2.5 sm:pr-4 sm:hover:bg-teal-hover sm:hover:text-white"
          >
            <ChevronDownIcon width={18} height={18} className="rotate-90" />
            <span className="hidden sm:inline">Zurück</span>
          </button>
        }
      />

      <main className="min-w-0 max-w-full">
        {/* Clean hero image — the spot identity (name/region/score) now lives in
            the Info column below, not in an overlay on the photo (Figma Frame_9). */}
        <EditorialHero
          image={spot.hero}
          focal={spot.heroFocal}
          focalMobile={spot.heroFocalMobile}
          rotation={spot.heroRotation}
          imageWidth={spot.heroWidth}
          alt={spot.name}
          credit={spot.heroCredit}
          delivery={spot.heroDelivery}
          frameClassName="h-[clamp(220px,62vw,260px)] sm:aspect-[21/9] sm:h-auto"
        />

        {/* Rendered at native scale at every width. The page used to shrink its
            desktop body with CSS zoom (0.85); the type scale and container
            tokens now size it directly, in whole pixels. */}
        <div className="relative [overflow-anchor:none]">
        {/* On the Daten tab the shared tab strip is scoped dark so it meets the
            dark instrument page below with no light seam (Figma Frame 67). */}
        {tabs.length > 0 && (
          <div className={activeTab === "daten" ? "daten-dark" : undefined}>
            <SpotTabs tabs={tabs} />
          </div>
        )}

        <AnimatePresence
          initial={false}
          custom={tabDirection}
          mode="popLayout"
        >
          {activeTab === "info" && (
            <motion.div
              key="info"
              custom={tabDirection}
              variants={tabContentVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: reduceMotion ? 0 : 0.22, ease: "easeOut" }}
            >
            {/* Text / Galerie-Kachel / Facilities+Kommentar — drei Spalten */}
            <SectionBand tone="page" pad="md" width="spotBody">
              <div
                className={`spot-detail-content-grid grid min-w-0 gap-x-8 gap-y-6 sm:gap-y-8 lg:gap-y-12 ${SPOT_INFO_GRID}`}
                style={{
                  "--spot-gallery-height": galleryHeight ? `${galleryHeight}px` : undefined,
                  "--spot-gallery-right-inset": `${galleryRightInset}px`,
                } as CSSProperties}
              >
                <div className="order-1 flex min-w-0 flex-col self-stretch">
                  {/* Spot identity: breadcrumb, name + community score inline
                      (Figma Frame_9) — replaces the hero namebox. */}
                  {(regionPart || country) && (
                    <p className="text-ui leading-tight text-ink-soft/80">
                      {regionPart && (
                        <Link
                          to={`/region/${regionSlug(spot.region)}`}
                          className="font-medium text-ink transition-opacity hover:opacity-70 hover:underline"
                        >
                          {regionPart}
                        </Link>
                      )}
                      {country && regionPart && (
                        <span className="mx-1.5 text-ink-soft/50">·</span>
                      )}
                      {country && <span>{country}</span>}
                    </p>
                  )}
                  {/* Page title: `heading` on phones, `heading-lg` from sm. */}
                  <h1 className="mt-3 text-heading font-semibold text-balance text-ink sm:text-heading-lg">
                    {spot.name}
                    {/* Origin mark trails the title on the same baseline; the
                        written-out sentence sits at the foot of this tab. */}
                    <SpotOriginMark origin={spot.origin} className="ml-2 align-baseline" />
                  </h1>

                  {/* Sports are plain label + white check, not
                      filled pills — datengetrieben aus spot.sports. */}
                  {spot.sports && spot.sports.length > 0 && (
                    <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 sm:mt-8">
                      {spot.sports.map((s) => (
                        <span
                          key={s}
                          className="inline-flex items-center gap-1 text-ui font-medium text-ink"
                        >
                          {sportLabel(s)}
                          <CheckCircleIcon checkOnly width={16} height={16} className="text-ink" />
                        </span>
                      ))}
                    </div>
                  )}

                  {/* The real spot description (editorial.description from the DB);
                      falls back to a gentle note when a spot has none yet. On
                      mobile it starts collapsed with a "Mehr anzeigen" toggle. */}
                  <SpotDescription text={spot.description || "Für diesen Spot gibt es noch keine Beschreibung."} />

                  <div className="mt-auto flex w-full items-center justify-center gap-4 pt-6 sm:pt-10">
                    <FavoriteButton spot={spot} />
                    <ShareButton spot={spot} />
                    {spotId && <VisitedButton spotId={spotId} />}
                    <SuggestEditButton spot={spot} />
                  </div>
                </div>

                <div ref={galleryFrameRef} className="spot-gallery-compact order-4 w-full min-w-0 justify-self-center lg:order-2">
                  <SpotGalleryTile
                    photos={photos}
                    onOpenGallery={() => setGalleryOpen(true)}
                    galleryTriggerRef={galleryTriggerRef}
                  />
                </div>

                <aside aria-label="Spotprofil und Ausstattung" className="order-2 flex min-w-0 flex-col lg:order-3">
                  <SpotMetaGrid spot={spot} bestSeason={bestSeason} />
                  {facilities.length > 0 && (
                    <div className="mt-8 lg:mt-12">
                      <h2 className="text-ui font-semibold text-ink">Ausstattung</h2>
                      <div className="mt-4 sm:mt-6">
                        <Facilities items={facilities} variant="list" />
                      </div>
                    </div>
                  )}
                </aside>
                  {spot.coords ? (
                    <section ref={mapSlotRef} aria-label="Lage" className="spot-locator-compact order-3 min-w-0 lg:order-4 lg:col-span-2">
                      {mapReady ? (
                        <LocatorMapBoundary coords={spot.coords}>
                          <Suspense fallback={<MapPlaceholder />}>
                            <LocatorMap coords={spot.coords} origin={spot.origin} />
                          </Suspense>
                        </LocatorMapBoundary>
                      ) : (
                        <MapPlaceholder />
                      )}
                    </section>
                  ) : (
                    <div aria-hidden className="order-3 lg:order-4 lg:col-span-2" />
                  )}
                  <div className="order-5 min-w-0">
                    <SpotCommentBox
                      spotId={spotId}
                      posts={sortedPosts}
                      onPosted={(tip) => {
                        if (tip) addTip(tip);
                        reloadFeed();
                      }}
                      loading={commentsLoading}
                      error={commentsError}
                    />
                  </div>
              </div>

              {spotId && (
                // 96px visible separation after the location/community group.
                <div className="mt-16 sm:mt-24">
                  <SimilarSpots spotId={spotId} sport={spot.sports?.[0]} />
                </div>
              )}

              {/* Provenance, spelled out: who entered this spot. Sits with the
                  other quiet credits at the foot of the Info tab. */}
              <SpotOriginLine spot={spot} className="mt-12 sm:mt-16" />
            </SectionBand>

            <PhotoGalleryOverlay
              open={galleryOpen}
              onClose={() => setGalleryOpen(false)}
              triggerRef={galleryTriggerRef}
              photos={photos}
              spotId={spotId}
            />
            </motion.div>
          )}

          {activeTab === "daten" && (
            <motion.div
              key="daten"
              custom={tabDirection}
              variants={tabContentVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: reduceMotion ? 0 : 0.22, ease: "easeOut" }}
            >
            <DatenPage
              spot={spot}
              live={live}
              liveLoading={liveLoading}
              liveError={liveError}
              liveStale={liveStale}
              onRetryLive={reloadLive}
              forecast={forecast}
              forecastLoading={forecastLoading}
              forecastError={forecastError}
              bestSeason={bestSeason}
            />
            </motion.div>
          )}
        </AnimatePresence>
        </div>
      </main>

      <Footer />
    </div>
  );
}

function MapPlaceholder() {
  return <div role="status" aria-label="Karte wird geladen" className="h-[360px] w-full animate-pulse rounded-card bg-band sm:h-[440px] lg:h-full" />;
}

class LocatorMapBoundary extends Component<
  { children: ReactNode; coords: [number, number] },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Locator map unavailable:", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const [lat, lng] = this.props.coords;
    const link = mapLinkProps(lat, lng);
    return (
      <div className="grid h-[360px] place-items-center bg-band px-6 text-center sm:h-[440px] lg:h-full lg:min-h-[360px]">
        <div>
          <p className="text-ui font-semibold text-ink">Karte momentan nicht verfügbar</p>
          <p className="mt-2 text-ui text-muted">Die übrigen Spotinformationen funktionieren weiterhin.</p>
          <a
            href={link.href}
            target={link.target}
            rel={link.rel}
            className="mt-4 inline-flex min-h-11 items-center px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            In externer Karte öffnen
          </a>
        </div>
      </div>
    );
  }
}
