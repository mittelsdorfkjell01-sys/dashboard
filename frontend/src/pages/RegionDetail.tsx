import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "../map.css";
import { pinIcon } from "../lib/mapPin";
import { cartoTileUrl, CARTO_VOYAGER } from "../lib/basemaps";
import LandingHeader from "../components/LandingHeader";
import SpotCard from "../components/SpotCard";
import RecommendationRow from "../components/RecommendationRow";
import SimilarRegions from "../components/SimilarRegions";
import SortDropdown from "../components/SortDropdown";
import Footer from "../components/Footer";
import { EditorialHero, SectionBand, Lede } from "../components/editorial";
import { fromImageRecord } from "../lib/imageCredit";
import { EmptyState, ErrorBanner, SpotGridSkeleton } from "../components/AsyncStates";
import { ChevronDownIcon } from "../lib/icons";
import type { RegionInfo } from "../lib/types";
import { usableMediaUrl } from "../lib/api";
import { useRegionBySlug, useSpots, useSpotsLive } from "../lib/hooks";
import DataHelpLink from "../components/DataHelpLink";
import {
  filterSpots,
  filtersToSearchParams,
  parseFilters,
  sortSpots,
  type FilterState,
} from "../lib/filters";


export default function RegionDetail() {
  const { t, i18n } = useTranslation();
  const { slug } = useParams();
  const navigate = useNavigate();
  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate("/"));
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = parseFilters(searchParams);
  const setFilters = (next: FilterState) =>
    setSearchParams(filtersToSearchParams(next), { replace: true });

  const {
    data: backendRegion,
    loading: regionsLoading,
    error: regionsError,
    reload: reloadRegions,
  } = useRegionBySlug(slug);
  const {
    data: spots,
    loading: spotsLoading,
    error: spotsError,
    reload: reloadSpots,
  } = useSpots(backendRegion ? { region_id: backendRegion.id } : {});
  const { data: live } = useSpotsLive((spots ?? []).map((s) => s.id));

  const loading = regionsLoading || (backendRegion && spotsLoading);
  const error = regionsError || spotsError;

  const region: RegionInfo | undefined = useMemo(() => {
    if (!backendRegion) return undefined;
    const rSpots = spots ?? [];
    const withCoords = rSpots.filter((s) => s.coords);
    const center: [number, number] = backendRegion.center
      ? [backendRegion.center.lat, backendRegion.center.lon]
      : withCoords.length
      ? [
          withCoords.reduce((a, s) => a + s.coords![0], 0) / withCoords.length,
          withCoords.reduce((a, s) => a + s.coords![1], 0) / withCoords.length,
        ]
      : [46, 8];
    return {
      slug: backendRegion.slug,
      name: backendRegion.name,
      country: backendRegion.country ?? "",
      spots: rSpots,
      center,
    };
  }, [backendRegion, spots]);

  if (loading) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader />
        <div className="hero-h w-full animate-pulse bg-ink-soft" />
        <div className="mx-auto max-w-page px-4 pt-16 sm:px-8">
          <div className="mb-10 h-8 w-64 animate-pulse rounded-card bg-line" />
          <SpotGridSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader onLight />
        <div className="mx-auto max-w-page px-4 pt-32 sm:px-8">
          <ErrorBanner
            message={error}
            onRetry={() => {
              reloadRegions();
              reloadSpots();
            }}
          />
        </div>
      </div>
    );
  }

  if (!region || !backendRegion) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader onLight />
        <div className="grid min-h-screen place-items-center px-6 text-center">
          <div>
            <h1 className="text-title font-semibold text-ink">{t("region.notFound")}</h1>
            <Link to="/" className="mt-4 inline-block text-body text-ink underline">
              {t("region.backOverview")}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const description =
    (i18n.resolvedLanguage === "en" ? backendRegion.description_en : backendRegion.description) ?? "";
  const descriptionSource = backendRegion.content_sources?.find(
    (source) => source.field === "description" && source.url,
  );

  // A spot photo must not silently present itself as representative of a whole
  // region. Without a reviewed region image, use the designed fallback.
  const regionImage = usableMediaUrl(backendRegion.image?.url);
  const heroImage = regionImage;
  const heroFocal = backendRegion.image?.focal ?? null;
  const heroFocalMobile = backendRegion.image?.focal_mobile ?? null;
  const heroRotation = backendRegion.image?.rotation ?? 0;
  const heroWidth = backendRegion.image?.width ?? null;
  const heroCredit = regionImage ? fromImageRecord(backendRegion.image) : null;
  const heroDelivery = backendRegion.image?.delivery;

  const withCoords = region.spots.filter((s) => s.coords);
  const gridSpots = sortSpots(filterSpots(region.spots, filters), filters.sort);
  const spotCount = t("region.spotCount", { count: region.spots.length });

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader />

      <main>
        <EditorialHero
          image={heroImage}
          focal={heroFocal}
          focalMobile={heroFocalMobile}
          rotation={heroRotation}
          imageWidth={heroWidth}
          alt={region.name}
          credit={heroCredit}
          delivery={heroDelivery}
        >
          <button
            type="button"
            onClick={goBack}
            aria-label="Zurück"
            className="pointer-events-auto inline-flex min-h-11 items-center gap-1.5 rounded-card border border-line bg-surface py-2 pl-2.5 pr-4 text-ui font-medium text-accent transition-colors hover:bg-band"
          >
            <ChevronDownIcon className="rotate-90 text-lead" />
            Zurück
          </button>
        </EditorialHero>

        {/* Breadcrumb + region identity (moved off the hero) */}
        <div className="mx-auto max-w-page px-4 pt-6 sm:px-8">
          <nav className="text-ui font-medium text-muted">
            <Link to="/" className="hover:underline">
              {t("region.overview")}
            </Link>
            {region.country && (
              <>
                <span className="mx-1.5 text-muted">›</span>
                <span>{region.country}</span>
              </>
            )}
            <span className="mx-1.5 text-muted">›</span>
            <span className="text-ink">{region.name}</span>
          </nav>
          <h1 className="mt-2 text-heading font-semibold leading-tight text-balance text-ink sm:text-heading-lg">
            {region.name}
          </h1>
          {spotCount && (
            <p className="mt-1 text-body font-medium text-ink-soft">{spotCount}</p>
          )}
        </div>

        {/* Lede */}
        <SectionBand tone="page" pad="md">
          <Lede>{description || t("region.descriptionPending")}</Lede>
          {backendRegion.content_status === "verified" && (
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-ui text-muted">
              <span>{t("region.verified")}</span>
              {descriptionSource && (
                <a href={descriptionSource.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-ink underline underline-offset-4">
                  {descriptionSource.title || t("region.source")} ↗
                </a>
              )}
            </div>
          )}
        </SectionBand>

        <SectionBand tone="page" pad="md" width="spotBody">
          <RecommendationRow
            title={t("region.top", { name: region.name })}
            surface="region"
            regionId={backendRegion.id}
          />
        </SectionBand>

        {/* No region aggregation until a V2 product rule has been defined. */}
        <SectionBand tone="band" heading={t("region.when")} pad="md" id="season">
          <p className="text-body text-muted">{t("region.windUnknown")}</p>
          <DataHelpLink anchor="forecast-climate">{t("region.windHelp")}</DataHelpLink>
        </SectionBand>

        {/* Die Spots — same body width as the spot detail page's content frame. */}
        <SectionBand tone="page" pad="md" width="spotBody">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line/70 pb-5">
            <h2 className="text-heading font-semibold leading-tight text-ink text-balance sm:text-heading-lg">
              {t("region.spots")}
            </h2>
            <SortDropdown value={filters} onChange={setFilters} />
          </div>
          {gridSpots.length === 0 ? (
            <div className="mt-8">
              <EmptyState message={t("region.noSpots")} />
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
              {gridSpots.map((spot) => (
                <SpotCard
                  key={spot.id}
                  spot={spot}
                  live={live?.get(spot.id)}
                  surface="region"
                />
              ))}
            </div>
          )}
        </SectionBand>

        {/* Auf der Karte */}
        {withCoords.length > 0 && (
          <SectionBand tone="band" heading={t("region.map")}>
            <div className="overflow-hidden rounded-card border border-line">
              <MapContainer
                center={region.center}
                zoom={7}
                zoomControl={false}
                scrollWheelZoom
                className="h-[300px] w-full sm:h-[420px]"
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                  url={cartoTileUrl(CARTO_VOYAGER)}
                  subdomains="abcd"
                />
                {withCoords.map((spot) => (
                  <Marker key={spot.id} position={spot.coords!} icon={pinIcon}>
                    <Popup className="spot-popup" closeButton={false}>
                      <div className="w-[200px]">
                        <SpotCard spot={spot} compact />
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
            </div>
          </SectionBand>
        )}

        {/* Ähnliche Regionen */}
        <SectionBand tone="white">
          <SimilarRegions region={region} />
        </SectionBand>
      </main>

      <Footer />
    </div>
  );
}
