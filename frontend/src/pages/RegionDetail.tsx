import { useMemo } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { cartoTileUrl, CARTO_VOYAGER } from "../lib/basemaps";
import LandingHeader from "../components/LandingHeader";
import SpotCard from "../components/SpotCard";
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
import {
  filterSpots,
  filtersToSearchParams,
  parseFilters,
  sortSpots,
  type FilterState,
} from "../lib/filters";

/** Navy teardrop pin — same look as the main map view. */
const pinIcon = L.divIcon({
  className: "swd-pin",
  html: `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
        fill="#241C17" stroke="#ffffff" stroke-width="1.4"/>
      <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
    </svg>`,
  iconSize: [30, 38],
  iconAnchor: [15, 38],
  popupAnchor: [0, -34],
});

export default function RegionDetail() {
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
  } = useSpots(
    backendRegion ? { region_id: backendRegion.id } : {}
  );
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
        <div className="mx-auto max-w-[1570px] px-4 pt-16 sm:px-8">
          <div className="mb-10 h-8 w-64 animate-pulse rounded bg-line" />
          <SpotGridSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="relative min-h-screen bg-page">
        <LandingHeader />
        <div className="mx-auto max-w-[1570px] px-4 pt-32 sm:px-8">
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
        <LandingHeader />
        <div className="grid min-h-screen place-items-center px-6 text-center">
          <div>
            <h1 className="text-2xl font-semibold text-ink">Region nicht gefunden</h1>
            <Link to="/" className="mt-4 inline-block text-body text-teal underline">
              Zurück zur Übersicht
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const description = backendRegion.description ?? "";

  // Hero source, in order: the region's own image → the first spot's image →
  // EditorialHero's designed fallback. Crop metadata and attribution always
  // travel with whichever photo is actually rendered.
  const regionImage = usableMediaUrl(backendRegion.image?.url);
  const heroImage = regionImage ?? usableMediaUrl(region.spots[0]?.image);
  const heroFocal = regionImage
    ? backendRegion.image?.focal ?? null
    : region.spots[0]?.heroFocal ?? null;
  const heroFocalMobile = regionImage
    ? backendRegion.image?.focal_mobile ?? null
    : region.spots[0]?.heroFocalMobile ?? null;
  const heroRotation = regionImage
    ? backendRegion.image?.rotation ?? 0
    : region.spots[0]?.heroRotation ?? 0;
  const heroWidth = regionImage
    ? backendRegion.image?.width ?? null
    : region.spots[0]?.heroWidth ?? null;
  // Until now region heroes rendered with no attribution at all, while the
  // stock-image route had been setting Unsplash photos on them for months —
  // which breaches Unsplash's attribution condition. When the hero falls back
  // to a spot photo, that spot's credit is used, because that is whose photo
  // is on screen.
  const fallbackSpot = regionImage ? undefined : region.spots[0];
  const heroCredit = regionImage
    ? fromImageRecord(backendRegion.image)
    : fallbackSpot?.heroCredit ?? null;
  const heroDelivery = regionImage
    ? backendRegion.image?.delivery
    : fallbackSpot?.heroDelivery;

  const withCoords = region.spots.filter((s) => s.coords);
  const gridSpots = sortSpots(filterSpots(region.spots, filters), filters.sort);
  const spotCount = `${region.spots.length} ${
    region.spots.length === 1 ? "Spot" : "Spots"
  } in der Region`;

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
            className="pointer-events-auto inline-flex min-h-11 items-center gap-1.5 rounded-2xl border border-line bg-surface py-2 pl-2.5 pr-4 text-ui font-medium text-teal transition-colors hover:bg-band"
          >
            <ChevronDownIcon className="rotate-90 text-sz-18" />
            Zurück
          </button>
        </EditorialHero>

        {/* Breadcrumb + region identity (moved off the hero) */}
        <div className="mx-auto max-w-[1570px] px-4 pt-6 sm:px-8">
          <nav className="text-label font-medium text-muted">
            <Link to="/" className="hover:underline">
              Übersicht
            </Link>
            {region.country && (
              <>
                <span className="mx-1.5 text-muted">›</span>
                <span>{region.country}</span>
              </>
            )}
            <span className="mx-1.5 text-muted">›</span>
            <span className="text-teal">{region.name}</span>
          </nav>
          <h1 className="mt-2 text-sz-28 font-semibold leading-tight text-balance text-ink sm:text-sz-32">
            {region.name}
          </h1>
          {spotCount && (
            <p className="mt-1 text-body font-medium text-ink-soft">{spotCount}</p>
          )}
        </div>

        {/* Lede */}
        <SectionBand tone="page" pad="md">
          <Lede>{description}</Lede>
        </SectionBand>

        {/* No region aggregation until a V2 product rule has been defined. */}
        <SectionBand tone="band" heading="Wann hinfahren" pad="md">
          <p className="text-body text-muted">Windverfügbarkeit für Regionen: Unbekannt</p>
        </SectionBand>

        {/* Die Spots — same body width as the spot detail page's content frame. */}
        <SectionBand tone="page" pad="md" width="spotBody">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line/70 pb-5">
            <h2 className="text-sz-28 font-semibold leading-tight text-ink text-balance sm:text-sz-32">
              Die Spots
            </h2>
            <SortDropdown value={filters} onChange={setFilters} />
          </div>
          {gridSpots.length === 0 ? (
            <div className="mt-8">
              <EmptyState message="Keine Spots für diese Auswahl." />
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
              {gridSpots.map((spot) => (
                <SpotCard key={spot.id} spot={spot} live={live?.get(spot.id)} />
              ))}
            </div>
          )}
        </SectionBand>

        {/* Auf der Karte */}
        {withCoords.length > 0 && (
          <SectionBand tone="band" heading="Auf der Karte">
            <div className="overflow-hidden rounded-3xl border border-line">
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
