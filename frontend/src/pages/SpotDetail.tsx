import { useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import LandingHeader from "../components/LandingHeader";
import Facilities from "../components/Facilities";
import LocatorMap from "../components/LocatorMap";
import SpotFlowMap from "../components/SpotFlowMap";
import SpotTabs from "../components/SpotTabs";
import DatenSection from "../components/DatenSection";
import TidePanel from "../components/TidePanel";
import Forecast from "../components/Forecast";
import WindMonths from "../components/WindMonths";
import SpotGalleryTile from "../components/SpotGalleryTile";
import PhotoGalleryOverlay from "../components/PhotoGalleryOverlay";
import SpotCommentBox from "../components/SpotCommentBox";
import CommentsOverlay from "../components/CommentsOverlay";
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
  const months = climatologyToMonths(spot.climatology);
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
  const featuredPost = sortedPosts.find((p) => p.text) ?? null;

  const tabs = id
    ? [
        { id: "info", label: "Info", href: `/spot/${id}` },
        { id: "daten", label: "Daten", href: `/spot/${id}/daten` },
      ]
    : [];

  return (
    <div className="relative min-h-screen min-w-0 max-w-full overflow-x-clip bg-page">
      <LandingHeader
        width="body"
        left={
          <button
            type="button"
            onClick={goBack}
            aria-label="Zurück"
            className="pointer-events-auto inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-2xl bg-teal p-2 text-ui font-medium text-white transition-colors hover:bg-teal-hover sm:min-h-0 sm:min-w-0 sm:justify-start sm:py-2 sm:pl-2.5 sm:pr-4"
          >
            <ChevronDownIcon width={18} height={18} className="rotate-90" />
            <span className="hidden sm:inline">Zurück</span>
          </button>
        }
      />

      <main className={`min-w-0 max-w-full ${activeTab === "daten" ? "pt-24 sm:pt-28" : ""}`}>
        {/* Clean hero image — the spot identity (name/region/score) now lives in
            the Info column below, not in an overlay on the photo (Figma Frame_9). */}
        {activeTab === "info" && (
          <EditorialHero
            image={spot.hero}
            focal={spot.heroFocal}
            focalMobile={spot.heroFocalMobile}
            alt={spot.name}
            credit={spot.heroCredit}
            delivery={spot.heroDelivery}
          />
        )}

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
            <SectionBand tone="page" pad="md" width="content">
              <div className="grid min-w-0 gap-x-8 gap-y-8 lg:grid-cols-[minmax(320px,380px)_minmax(420px,1fr)_minmax(320px,380px)]">
                <div className="min-w-0">
                  {/* Spot identity: breadcrumb, name + community score inline
                      (Figma Frame_9) — replaces the hero namebox. */}
                  {(regionPart || country) && (
                    <p className="text-label text-ink-soft/80">
                      {country && <span>{country}</span>}
                      {country && regionPart && (
                        <span className="mx-1.5 text-ink-soft/50">›</span>
                      )}
                      {regionPart && (
                        <Link
                          to={`/region/${regionSlug(spot.region)}`}
                          className="font-medium text-teal transition-colors hover:text-teal-hover hover:underline"
                        >
                          {regionPart}
                        </Link>
                      )}
                    </p>
                  )}
                  <h1 className="mt-1 text-[28px] font-semibold leading-[1.12] text-balance text-ink sm:text-[30px]">{spot.name}</h1>

                  {/* Sports are plain label + teal check (Figma Frame_9), not
                      filled pills — datengetrieben aus spot.sports. */}
                  {spot.sports && spot.sports.length > 0 && (
                    <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2">
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
                  <p className="mt-6 max-w-[65ch] text-body leading-relaxed text-ink-soft">
                    {spot.description || "Für diesen Spot gibt es noch keine Beschreibung."}
                  </p>

                  <div className="mt-7">
                    <FavoriteButton spot={spot} />
                  </div>
                </div>

                <div className="spot-gallery-compact min-w-0">
                  <SpotGalleryTile
                    photos={photos}
                    onOpenGallery={() => setGalleryOpen(true)}
                    galleryTriggerRef={galleryTriggerRef}
                  />
                </div>

                <div className="flex min-w-0 flex-col gap-5">
                  <SpotMetaGrid spot={spot} />
                  <h2 className="text-label font-semibold uppercase tracking-[0.08em] text-muted">Ausstattung</h2>
                  <Facilities items={facilities} variant="list" />
                </div>
              </div>

              {/* Lage + Kommentare: Karte 2/3, offene Kommentarspalte 1/3. */}
              <div className={`mt-10 grid min-w-0 gap-8 ${spot.coords ? "lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]" : "lg:grid-cols-[2fr_1fr]"}`}>
                {spot.coords ? (
                  <div className="spot-locator-compact min-w-0"><LocatorMap coords={spot.coords} /></div>
                ) : (
                  <div aria-hidden />
                )}
                <div className="min-h-[320px] lg:min-h-[400px]">
                  <SpotCommentBox
                    variant="plain"
                    spotId={id}
                    comment={featuredPost}
                    onOpenMore={() => setCommentsOpen(true)}
                    onPosted={reloadFeed}
                    moreButtonRef={commentsTriggerRef}
                  />
                </div>
              </div>

              {id && (
                <div className="mt-14">
                  <SimilarSpots spotId={id} sport={spot.sports?.[0]} />
                </div>
              )}
            </SectionBand>

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
                <div className="pointer-events-none absolute bottom-4 left-4 z-10 flex items-center gap-4 rounded-2xl border border-line bg-white px-4 py-2 text-caption text-ink">
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

            <DatenSection label="Gezeiten">
              <TidePanel spotId={id!} />
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
