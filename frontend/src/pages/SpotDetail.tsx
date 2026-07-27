import { useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import LandingHeader from "../components/LandingHeader";
import Facilities from "../components/Facilities";
import LocatorMap from "../components/LocatorMap";
import SpotFlowMap from "../components/SpotFlowMap";
import SpotTabs from "../components/SpotTabs";
import DatenSection from "../components/DatenSection";
import Forecast from "../components/Forecast";
import WindMonths from "../components/WindMonths";
import SpotGalleryTile from "../components/SpotGalleryTile";
import PhotoGalleryOverlay from "../components/PhotoGalleryOverlay";
import SpotCommentBox from "../components/SpotCommentBox";
import CommentsOverlay from "../components/CommentsOverlay";
import FavoriteButton from "../components/FavoriteButton";
import Footer from "../components/Footer";
import { EditorialHero, SectionBand } from "../components/editorial";
import { ErrorBanner, EmptyState } from "../components/AsyncStates";
import { ChevronDownIcon, CheckCircleIcon } from "../lib/icons";
import { sportLabel } from "../lib/labels";
import { sortFeed } from "../lib/communityFeed";
import { useSpot, useSpotLive, useSpotForecast, useCommunityFeed, useRatingScore } from "../lib/hooks";
import { facilitiesFromMap } from "../lib/spotView";
import { climatologyToMonths, waterTypeFromCharacter } from "../lib/seasonView";

export default function SpotDetail() {
  const { id } = useParams();
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

  const { data: spot, loading, error, reload } = useSpot(id);
  const { data: live } = useSpotLive(id);
  const { data: forecast, loading: forecastLoading, error: forecastError } =
    useSpotForecast(id);
  const { posts, photos, reload: reloadFeed } = useCommunityFeed(id);
  const score = useRatingScore(id);

  const [galleryOpen, setGalleryOpen] = useState(false);
  const galleryTriggerRef = useRef<HTMLButtonElement>(null);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const commentsTriggerRef = useRef<HTMLButtonElement>(null);

  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate("/map"));

  if (loading) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader />
        <div className="hero-h w-full animate-pulse bg-ink-soft" />
        <div className="mx-auto max-w-[1180px] px-4 pt-16 sm:px-8">
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
  const months = climatologyToMonths(spot.climatology);
  const waterType = waterTypeFromCharacter(spot.waterCharacter);
  const currentWind = live?.current.wind ?? undefined;
  const mapCoords = spot.coords ?? [41.18, 9.32];
  const windDir = live?.current.dir ?? spot.windDir ?? 320;
  const [regionPart, country] = spot.region.split(",").map((p) => p.trim());

  // Most recent posts first — the teaser tile shows the newest one, the
  // "mehr" overlay shows up to three.
  const sortedPosts = sortFeed(posts, "newest", {});
  // The teaser shows the newest post that actually has text — a photo-only
  // post isn't a "comment", and its absence triggers the write-first prompt.
  const featuredPost = sortedPosts.find((p) => p.text) ?? null;

  const tabs = id
    ? [
        { id: "info", label: "Info", href: `/spot/${id}` },
        { id: "daten", label: "Daten", href: `/spot/${id}/daten` },
      ]
    : [];

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader
        width="body"
        left={
          <button
            type="button"
            onClick={goBack}
            aria-label="Zurück"
            className="pointer-events-auto inline-flex items-center gap-1.5 rounded-full bg-teal py-2 pl-2.5 pr-4 text-ui font-medium text-white transition-colors hover:bg-teal-hover"
          >
            <ChevronDownIcon width={18} height={18} className="rotate-90" />
            Zurück
          </button>
        }
      />

      <main>
        {/* Clean hero image — the spot identity (name/region/score) now lives in
            the Info column below, not in an overlay on the photo (Figma Frame_9). */}
        <EditorialHero
          image={spot.hero}
          focal={spot.heroFocal}
          alt={spot.name}
          credit={spot.heroCredit}
          license={spot.heroLicense}
          sourceUrl={spot.heroSource}
        />

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
            <SectionBand tone="page" pad="md">
              <div className="grid gap-x-8 gap-y-10 lg:grid-cols-[5fr_6fr_5fr]">
                <div>
                  {/* Spot identity: breadcrumb, name + community score inline
                      (Figma Frame_9) — replaces the hero namebox. */}
                  {(regionPart || country) && (
                    <p className="text-label text-ink-soft/80">
                      {[regionPart, country].filter(Boolean).join(" › ")}
                    </p>
                  )}
                  <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h1 className="text-editorial-4 font-semibold text-balance text-ink">{spot.name}</h1>
                    {typeof score === "number" && (
                      <span className="flex items-baseline gap-1">
                        <span className="text-editorial-4 font-semibold tabular-nums text-ink-soft">
                          {(score * 2).toFixed(1)}
                        </span>
                        <span className="text-caption text-muted">Punkte</span>
                      </span>
                    )}
                  </div>

                  {/* Sports are plain label + teal check (Figma Frame_9), not
                      filled pills — datengetrieben aus spot.sports. */}
                  {spot.sports && spot.sports.length > 0 && (
                    <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2">
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
                  <p className="mt-8 max-w-[62ch] text-body text-ink-soft">
                    {spot.description || "Für diesen Spot gibt es noch keine Beschreibung."}
                  </p>

                  <div className="mt-10">
                    <FavoriteButton spot={spot} />
                  </div>
                </div>

                <div>
                  <SpotGalleryTile
                    photos={photos}
                    onOpenGallery={() => setGalleryOpen(true)}
                    galleryTriggerRef={galleryTriggerRef}
                  />
                </div>

                <div className="flex flex-col gap-6">
                  <Facilities items={facilities} variant="list" />
                  <SpotCommentBox
                    spotId={id}
                    comment={featuredPost}
                    onOpenMore={() => setCommentsOpen(true)}
                    onPosted={reloadFeed}
                    moreButtonRef={commentsTriggerRef}
                  />
                </div>
              </div>
            </SectionBand>

            {/* Lage: only ever shown with real coordinates */}
            {spot.coords && (
              <SectionBand tone="page" pad="md">
                <LocatorMap coords={spot.coords} />
              </SectionBand>
            )}

            <PhotoGalleryOverlay
              open={galleryOpen}
              onClose={() => setGalleryOpen(false)}
              triggerRef={galleryTriggerRef}
              photos={photos}
              spotId={id}
            />
            <CommentsOverlay
              open={commentsOpen}
              onClose={() => setCommentsOpen(false)}
              triggerRef={commentsTriggerRef}
              posts={sortedPosts}
              spotId={id}
              onReload={reloadFeed}
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
            {/* Wind & Wellen: the flow map (legend on the map itself covers
                what the lines mean, no explanatory sentence above it) */}
            <DatenSection label="Wind & Wellen">
              <div className="relative">
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
                />
                <div className="pointer-events-none absolute bottom-4 left-4 z-10 flex items-center gap-4 rounded-full border border-line bg-white px-4 py-2 text-caption text-ink">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-0.5 w-4 rounded-full bg-ink/60" />
                    Wind
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-0.5 w-4 rounded-full bg-[#2F6FB0]" />
                    Welle
                  </span>
                </div>
              </div>
            </DatenSection>

            {/* Die nächsten 7 Tage — Wochenüberblick + Stundentabelle */}
            {(forecastLoading || forecast?.days.length) && (
              <DatenSection label="Die nächsten 7 Tage">
                {forecastLoading && <div className="h-56 animate-pulse bg-line" />}
                {!forecastLoading && forecast && forecast.days.length > 0 && (
                  <Forecast forecast={forecast} coords={spot.coords} />
                )}
                {!forecastLoading && (!forecast || forecast.days.length === 0) && (
                  <EmptyState
                    message={
                      forecastError
                        ? "7-Tage-Vorhersage momentan nicht verfügbar."
                        : "Keine Vorhersage-Daten."
                    }
                  />
                )}
              </DatenSection>
            )}

            {/* Saison */}
            {months && (
              <DatenSection label="Wann hierher?">
                <WindMonths climatology={spot.climatology} />
              </DatenSection>
            )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <Footer />
    </div>
  );
}
