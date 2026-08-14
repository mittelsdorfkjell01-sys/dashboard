import { Component, lazy, Suspense, useEffect, useRef, useState, type CSSProperties, type ErrorInfo, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import LandingHeader from "../components/LandingHeader";
import Facilities from "../components/Facilities";
import SpotTabs from "../components/SpotTabs";
import TidePanel from "../components/TidePanel";
import WindRose from "../components/WindRose";
import SpotDataHeader from "../components/data/SpotDataHeader";
import LiveRow from "../components/data/LiveRow";
import TimeScrubber from "../components/data/TimeScrubber";
import SpotGalleryTile from "../components/SpotGalleryTile";
import PhotoGalleryOverlay from "../components/PhotoGalleryOverlay";
import SpotCommentBox from "../components/SpotCommentBox";
import FavoriteButton from "../components/FavoriteButton";
import Footer from "../components/Footer";
import SimilarSpots from "../components/SimilarSpots";
import SpotMetaGrid from "../components/SpotMetaGrid";
import { EditorialHero, SectionBand } from "../components/editorial";
import { ErrorBanner, EmptyState } from "../components/AsyncStates";
import { ChevronDownIcon, CheckCircleIcon } from "../lib/icons";
import { sportLabel } from "../lib/labels";
import { regionSlug } from "../lib/types";
import { sortFeed } from "../lib/communityFeed";
import { useSpot, useSpotLive, useSpotForecast, useCommunityFeed } from "../lib/hooks";
import { facilitiesFromMap } from "../lib/spotView";
import { waterTypeFromCharacter } from "../lib/seasonView";
import { mapLinkProps } from "../lib/mapLinks";
import { SpotDataScopeProvider } from "../state/SpotDataScope";
import { spotPath } from "../lib/spotRoutes";

const SPOT_INFO_GRID = "lg:grid-cols-[minmax(320px,1fr)_minmax(420px,560px)_minmax(320px,1fr)]";
const LocatorMap = lazy(() => import("../components/LocatorMap"));
const SpotFlowMap = lazy(() => import("../components/SpotFlowMap"));
const Meteogram = lazy(() => import("../components/data/Meteogram"));
const WeatherDetailsTable = lazy(() => import("../components/data/WeatherDetailsTable"));
const Climatology = lazy(() => import("../components/data/Climatology"));

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

  const { data: spot, loading, error, reload } = useSpot(spotName);
  const spotId = spot?.uuid;
  const { data: live } = useSpotLive(activeTab === "daten" ? spotId : undefined);
  const { data: forecast, loading: forecastLoading, error: forecastError } =
    useSpotForecast(activeTab === "daten" ? spotId : undefined);
  const { posts, photos, loading: commentsLoading, error: commentsError, reload: reloadFeed, addTip } =
    useCommunityFeed(activeTab === "info" ? spotId : undefined);

  useEffect(() => {
    if (!spot) return;
    const canonical = spotPath(spot, activeTab);
    if (location.pathname !== canonical) navigate(canonical, { replace: true });
  }, [activeTab, location.pathname, navigate, spot]);

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

  const goBack = () => (location.key !== "default" ? navigate(-1) : navigate("/map"));

  if (loading) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader />
        <div className="hero-h w-full animate-pulse bg-ink-soft" />
        <div className="mx-auto max-w-[1570px] px-4 pt-16 sm:px-8">
          <div className="h-8 w-2/3 animate-pulse rounded bg-line" />
          <div className="mt-4 h-4 w-full animate-pulse rounded bg-line" />
        </div>
      </div>
    );
  }

  if (error || !spot) {
    return (
      <div className="grid min-h-screen place-items-center bg-white px-6 text-center">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Spot nicht gefunden</h1>
          {error && (
            <div className="mt-4 max-w-md">
              <ErrorBanner message={error} onRetry={reload} />
            </div>
          )}
          <Link to="/" className="mt-4 inline-block text-body text-teal underline">
            Zurück zur Übersicht
          </Link>
        </div>
      </div>
    );
  }

  // All from the backend record — no synthetic data.
  const facilities = facilitiesFromMap(spot.facilities);
  // waterCharacter is multi-select; the flow-map animation takes one cue — use
  // the first (primary) character.
  const waterType = waterTypeFromCharacter(spot.waterCharacter?.[0]);
  const currentWind = live?.current.wind ?? undefined;
  const mapCoords = spot.coords ?? [41.18, 9.32];
  const windDir = live?.current.dir ?? spot.windDir ?? 320;
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
            className="pointer-events-auto inline-flex h-11 w-11 items-center justify-center gap-1.5 bg-transparent p-0 text-ui font-medium text-white transition-colors hover:text-white/80 sm:h-auto sm:w-auto sm:justify-start sm:rounded-2xl sm:bg-teal sm:py-2 sm:pl-2.5 sm:pr-4 sm:hover:bg-teal-hover sm:hover:text-white"
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
          alt={spot.name}
          credit={spot.heroCredit}
          delivery={spot.heroDelivery}
          frameClassName="h-[clamp(220px,62vw,260px)] sm:aspect-[21/9] sm:h-auto"
        />

        {/* Mobile remains at native scale for readable type and reliable 44px
            touch targets. The established compact desktop composition starts
            at lg; the full-bleed hero remains outside this wrapper. */}
        <div className="[zoom:1] lg:[zoom:0.85]">
        {tabs.length > 0 && <SpotTabs tabs={tabs} />}

        <AnimatePresence initial={false} custom={tabDirection}>
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
              {/* gap-x-8/gap-y-8 (32px) inflated by 1/0.85 so the zoom above renders them at their original size. */}
              <div
                className={`spot-detail-content-grid grid min-w-0 gap-x-8 gap-y-8 lg:gap-x-[37.65px] lg:gap-y-[58px] ${SPOT_INFO_GRID}`}
                style={{
                  "--spot-gallery-height": galleryHeight ? `${galleryHeight}px` : undefined,
                  "--spot-gallery-right-inset": `${galleryRightInset}px`,
                } as CSSProperties}
              >
                <div className="order-1 flex min-w-0 flex-col self-stretch">
                  {/* Spot identity: breadcrumb, name + community score inline
                      (Figma Frame_9) — replaces the hero namebox. */}
                  {(regionPart || country) && (
                    <p className="text-label leading-tight text-ink-soft/80">
                      {regionPart && (
                        <Link
                          to={`/region/${regionSlug(spot.region)}`}
                          className="font-medium text-teal transition-colors hover:text-teal-hover hover:underline"
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
                  <h1 className="mt-3 text-[28px] font-semibold leading-[1.12] text-balance text-ink sm:text-[30px]">{spot.name}</h1>

                  {/* Sports are plain label + teal check (Figma Frame_9), not
                      filled pills — datengetrieben aus spot.sports. */}
                  {spot.sports && spot.sports.length > 0 && (
                    <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2">
                      {spot.sports.map((s) => (
                        <span
                          key={s}
                          className="inline-flex items-center gap-1 text-label font-medium text-ink"
                        >
                          {sportLabel(s)}
                          <CheckCircleIcon width={16} height={16} className="text-teal" />
                        </span>
                      ))}
                    </div>
                  )}

                  {/* The real spot description (editorial.description from the DB);
                      falls back to a gentle note when a spot has none yet. */}
                  <p className="mt-8 max-w-[65ch] text-body leading-relaxed text-ink-soft">
                    {spot.description || "Für diesen Spot gibt es noch keine Beschreibung."}
                  </p>

                  <div className="mt-auto pt-10">
                    <FavoriteButton spot={spot} />
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
                  <SpotMetaGrid spot={spot} />
                  {facilities.length > 0 && (
                    <div className="mt-10 lg:mt-12">
                      <h2 className="text-ui font-semibold text-ink">Ausstattung</h2>
                      <div className="mt-6">
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
                            <LocatorMap coords={spot.coords} />
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
                <div className="mt-24 lg:mt-[112.94px]">
                  <SimilarSpots spotId={spotId} sport={spot.sports?.[0]} />
                </div>
              )}
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
            <SpotDataScopeProvider>
              <div className="mx-auto max-w-[1727px] px-4 pb-8 pt-10 sm:px-8">
                <SpotDataHeader spot={spot} />

                <section aria-label="Forecast-Information" className="mt-3 flex flex-wrap items-center justify-between gap-3 border-y border-line py-3 text-label text-muted">
                  <div><strong className="font-semibold text-ink">{forecast?.product ?? "Surfwinddata Forecast"}</strong>{forecast?.updated_at && <span> · Aktualisiert {new Date(forecast.updated_at).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}</span>}{forecast?.stale && <span> · Letzter verfügbarer Stand</span>}</div>
                  {forecast?.attributions && forecast.attributions.length > 0 && <details className="relative"><summary className="cursor-pointer font-medium text-teal">Quellen</summary><div className="mt-2 max-w-prose space-y-1 sm:absolute sm:right-0 sm:z-10 sm:w-80 sm:rounded-lg sm:border sm:border-line sm:bg-surface sm:p-3">{forecast.attributions.map((source) => <p key={source.provider}><a className="underline" href={source.url} target="_blank" rel="noreferrer">{source.text}</a> · {source.licence}</p>)}</div></details>}
                </section>

                <div className="mt-6 overflow-hidden rounded-lg border border-line bg-surface">
                  <LiveRow spot={spot} forecast={forecast} live={live} />
                </div>

                <div className="mt-6 overflow-hidden rounded-lg border border-line bg-surface">
                  <div className="px-4 py-2.5"><p className="text-caption font-medium uppercase tracking-wider text-muted">Meteogramm · 10 Tage</p></div>
                  {forecastLoading && <div className="h-[280px] animate-pulse bg-band" />}
                  {!forecastLoading && forecast && forecast.days.length > 0 && (
                    <Suspense fallback={<DataModulePlaceholder height="h-[280px]" />}>
                      <Meteogram forecast={forecast} />
                    </Suspense>
                  )}
                  {!forecastLoading && (!forecast || forecast.days.length === 0) && <EmptyState message={forecastError ? "Vorhersage momentan nicht verfügbar." : "Keine Vorhersage-Daten."} />}
                </div>

                <div className="mt-6 overflow-hidden rounded-lg border border-line bg-surface">
                  <div className="px-4 py-2.5"><p className="text-caption font-medium uppercase tracking-wider text-muted">Wind + Welle · Karte</p></div>
                <Suspense fallback={<DataModulePlaceholder height="h-[420px]" />}>
                  <SpotFlowMap
                    coords={mapCoords}
                    windDir={windDir}
                    windKts={currentWind ?? spot.wind}
                    waveDir={spot.waveDir ?? windDir}
                    coast={spot.coast ?? ((spot.waveDir ?? windDir) + 180) % 360}
                    period={live?.current.period ?? 5}
                    waterType={waterType}
                    zoom={spot.mapView?.zoom}
                    mapCenter={spot.mapView?.center}
                    live={live}
                    forecast={forecast}
                    showLayerSwitcher
                    rounded={false}
                  />
                </Suspense>
                  <TimeScrubber />
                </div>

                <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
                  <div className="rounded-lg border border-line bg-surface p-4">
                    <p className="text-caption font-medium uppercase tracking-wider text-muted">Windrichtung · 52 W</p>
                    <WindRose windDir={windDir} waveDir={spot.waveDir ?? live?.current.swell_dir ?? undefined} className="mx-auto mt-2 h-52 max-w-full" />
                  </div>
                  <TidePanel spotId={spotId!} />
                </div>

                {forecast && forecast.days.length > 0 && (
                  <div className="mt-6 overflow-hidden rounded-lg border border-line bg-surface">
                    <div className="px-4 py-2.5"><p className="text-caption font-medium uppercase tracking-wider text-muted">Wetter-Details · 10 Tage</p></div>
                    <Suspense fallback={<DataModulePlaceholder height="h-64" />}>
                      <WeatherDetailsTable forecast={forecast} />
                    </Suspense>
                  </div>
                )}

                {spot.climatology && (
                  <div className="mt-6 overflow-hidden rounded-lg border border-line bg-surface">
                    <div className="px-4 py-2.5"><p className="text-caption font-medium uppercase tracking-wider text-muted">Klimatologie · Wann hierher</p></div>
                    <Suspense fallback={<DataModulePlaceholder height="h-40" />}>
                      <Climatology spot={spot} />
                    </Suspense>
                  </div>
                )}
              </div>
            </SpotDataScopeProvider>
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
  return <div role="status" aria-label="Karte wird geladen" className="h-[360px] w-full animate-pulse bg-band sm:h-[440px] lg:h-full" />;
}

function DataModulePlaceholder({ height }: { height: string }) {
  return <div role="status" aria-label="Datenansicht wird geladen" className={`${height} animate-pulse bg-band`} />;
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
          <p className="mt-2 text-label text-muted">Die übrigen Spotinformationen funktionieren weiterhin.</p>
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
