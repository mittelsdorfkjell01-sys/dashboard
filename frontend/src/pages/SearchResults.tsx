import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "../map.css";
import L, { type Map as LeafletMap } from "leaflet";
import { cartoTileUrl, CARTO_VOYAGER } from "../lib/basemaps";
import ResultsHeader from "../components/ResultsHeader";
import Footer from "../components/Footer";
import SpotCard from "../components/SpotCard";
import RegionTile from "../components/RegionTile";
import { ErrorBanner, EmptyState, SpotGridSkeleton } from "../components/AsyncStates";
import { ChevronLeftIcon, MapIcon, MinusIcon, PlusIcon } from "../lib/icons";
import { countryName } from "../lib/flags";
import * as api from "../lib/api";
import { API_BASE, resolveMediaUrl } from "../lib/api";
import { useSpots, useSpotsLive, useTopSpots, useRegions } from "../lib/hooks";
import type { Spot } from "../lib/types";

const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

/** Navy teardrop pin — identical to the map + region-page marker. */
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

// --- shared bits -----------------------------------------------------------

/** Breadcrumb + heading — shared by every axis so it can sit either above the
 *  content (loading/error/best-weeks) or inside the split-view grid (so its
 *  row lines up with the map). */
function ResultHead({ heading }: { heading: string }) {
  return (
    <>
      <nav className="text-sz-11 font-medium text-muted">
        <Link to="/" className="hover:underline">Übersicht</Link>
        <span className="mx-1.5 text-muted">›</span>
        <span className="text-ink">Suche</span>
      </nav>
      <h1 className="mt-2 text-sz-32 font-semibold leading-tight text-balance text-ink">{heading}</h1>
    </>
  );
}

/** One tile row: a heading + a grid of spot cards, sized for the narrow left
 *  column of the split view (2 cols on phones, 3 from lg). */
function SpotRow({
  title,
  subtitle,
  spots,
  live,
}: {
  title: string;
  subtitle?: string;
  spots: Spot[];
  live?: Map<string, api.LiveConditionsRead>;
}) {
  if (spots.length === 0) return null;
  return (
    <section className="pt-2">
      <div>
        <h2 className="text-title font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-1 text-caption text-muted">{subtitle}</p>}
      </div>
      <div className="mt-5 grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-3">
        {spots.map((spot, i) => (
          <div key={spot.id} className="animate-fade-up" style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}>
            <SpotCard spot={spot} live={live?.get(spot.id)} />
          </div>
        ))}
      </div>
    </section>
  );
}

/** One tile row of region tiles. */
function RegionRow({
  title,
  subtitle,
  regions,
}: {
  title: string;
  subtitle?: string;
  regions: { slug: string; name: string; country?: string | null; image?: string | api.ImageRecord | null; spotCount?: number | null; sports?: string[] | null }[];
}) {
  if (regions.length === 0) return null;
  return (
    <section className="pt-2">
      <div>
        <h2 className="text-title font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-1 text-caption text-muted">{subtitle}</p>}
      </div>
      <div className="mt-5 grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-2">
        {regions.map((r, i) => (
          <div key={r.slug || i} className="animate-fade-up" style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}>
            <RegionTile slug={r.slug} name={r.name} country={r.country} image={r.image} spotCount={r.spotCount} sports={r.sports} />
          </div>
        ))}
      </div>
    </section>
  );
}

// --- map -------------------------------------------------------------------

/** Recentre the map imperatively when the result set (and thus the anchor)
 *  changes, without remounting the Leaflet instance. */
function Recenter({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom, { animate: false });
  }, [map, center, zoom]);
  return null;
}

function ResultsMap({
  spots,
  center,
  zoom = 7,
  live,
  /** Leaves the top-right corner free for the mobile full-screen back button. */
  topInset = false,
}: {
  spots: Spot[];
  center: [number, number];
  zoom?: number;
  live?: Map<string, api.LiveConditionsRead>;
  topInset?: boolean;
}) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const withCoords = spots.filter((s) => s.coords);
  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={center}
        zoom={zoom}
        zoomControl={false}
        scrollWheelZoom={false}
        ref={setMap}
        className="h-full w-full"
      >
        <Recenter center={center} zoom={zoom} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url={cartoTileUrl(CARTO_VOYAGER)}
          subdomains="abcd"
        />
        {withCoords.map((spot) => (
          <Marker key={spot.id} position={spot.coords!} icon={pinIcon}>
            <Popup className="spot-popup" closeButton={false}>
              <div className="w-[200px]">
                <SpotCard spot={spot} compact live={live?.get(spot.id)} />
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Zoom controls (scroll-wheel zoom is off so the page keeps scrolling
          past the sticky map). */}
      <div className={`pointer-events-none absolute right-3 z-[600] flex flex-col overflow-hidden rounded-2xl border border-line bg-white ${topInset ? "top-20" : "top-3"}`}>
        <button type="button" aria-label="Vergrößern" onClick={() => map?.zoomIn()} className="pointer-events-auto grid h-10 w-10 place-items-center text-teal transition-colors hover:bg-line/40">
          <PlusIcon className="text-sz-18" />
        </button>
        <span className="mx-2 h-px bg-line" />
        <button type="button" aria-label="Verkleinern" onClick={() => map?.zoomOut()} className="pointer-events-auto grid h-10 w-10 place-items-center text-teal transition-colors hover:bg-line/40">
          <MinusIcon className="text-sz-18" />
        </button>
      </div>
    </div>
  );
}

const EUROPE_CENTER: [number, number] = [43.5, 6.5];

function centerFor(primary: Spot[], fallback: Spot[]): [number, number] {
  const anchor = primary.find((s) => s.coords) ?? fallback.find((s) => s.coords);
  return anchor?.coords ?? EUROPE_CENTER;
}

/**
 * Split view: tiles left, a companion map right (Airbnb-style). The map is
 * sticky on desktop; on mobile it opens full-screen from a floating button.
 */
function SplitView({
  children,
  head,
  mapSpots,
  center,
  zoom,
  live,
}: {
  children: React.ReactNode;
  /** Rendered atop the left column, in the same grid row as the map. */
  head?: React.ReactNode;
  mapSpots: Spot[];
  center: [number, number];
  zoom?: number;
  live?: Map<string, api.LiveConditionsRead>;
}) {
  const [showMap, setShowMap] = useState(false);
  const hasMap = mapSpots.some((s) => s.coords);

  return (
    <div className="mx-auto w-full max-w-[1570px] px-4 pt-2 pb-16 sm:px-8">
      <div className="lg:grid lg:grid-cols-[1fr_minmax(360px,40%)] lg:gap-8">
        <div className="min-w-0">
          {head}
          <div className="mt-8 space-y-10">{children}</div>
        </div>

        {hasMap && (
          <div className="hidden lg:block">
            {/* The map enters already docked beneath the persistent header and
                remains there while the independent result column scrolls. */}
            <div className="sticky top-24 h-[calc(100vh-7.5rem)] min-h-[420px] max-h-[720px] overflow-hidden rounded-3xl border border-line" data-lenis-prevent>
              <ResultsMap spots={mapSpots} center={center} zoom={zoom} live={live} />
            </div>
          </div>
        )}
      </div>

      {/* Mobile: floating toggle → full-screen map. */}
      {hasMap && (
        <>
          <button
            type="button"
            onClick={() => setShowMap(true)}
            className="fixed bottom-6 left-1/2 z-[700] flex -translate-x-1/2 items-center gap-1.5 rounded-xl bg-teal px-4 py-2 text-ui font-semibold text-white shadow-float lg:hidden"
          >
            Karte <MapIcon className="text-body" />
          </button>

          {showMap && (
            <div className="fixed inset-0 z-[1400] bg-page lg:hidden" data-lenis-prevent>
              <ResultsMap spots={mapSpots} center={center} zoom={zoom} live={live} topInset />
              <button
                type="button"
                onClick={() => setShowMap(false)}
                aria-label="Zurück"
                className="absolute right-4 top-4 z-[1100] grid h-11 w-11 place-items-center rounded-2xl border border-line bg-white text-teal shadow-card"
              >
                <ChevronLeftIcon className="text-sz-20" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// --- similar-profile fetch (reuses /spots/{id}/similar?mode=charakter) ------

interface SimilarSpotApi {
  id: string;
  name: string;
  sports?: string[];
  region?: string | null;
  region_country?: string | null;
  image?: api.ImageRecord | null;
  wind?: number | null;
  wave_height?: number | null;
}

function similarToSpot(item: SimilarSpotApi): Spot {
  return {
    id: item.id,
    name: item.name,
    region: [item.region, countryName(item.region_country ?? undefined)].filter(Boolean).join(", "),
    regionName: item.region ?? undefined,
    regionCountry: item.region_country ?? null,
    wind: item.wind ?? 0,
    typicalWindKt: item.wind ?? null,
    typicalWaveHeightM: item.wave_height ?? null,
    tags: [],
    image: resolveMediaUrl(item.image?.url) ?? "",
    hero: resolveMediaUrl(item.image?.url),
    heroFocal: item.image?.focal ?? null,
    heroFocalMobile: item.image?.focal_mobile ?? null,
    heroRotation: item.image?.rotation ?? 0,
    heroWidth: item.image?.width ?? null,
    sports: item.sports,
  };
}

/** Spots with a comparable profile to the anchor spot. */
function useSimilarSpots(spotId: string | undefined, sport?: string): Spot[] {
  const [spots, setSpots] = useState<Spot[]>([]);
  useEffect(() => {
    if (!spotId) {
      setSpots([]);
      return;
    }
    const ctrl = new AbortController();
    const query = new URLSearchParams({ mode: "charakter", limit: "6" });
    if (sport) query.set("sport", sport);
    fetch(`${API_BASE}/spots/${encodeURIComponent(spotId)}/similar?${query}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("similar unavailable"))))
      .then((body: { results?: SimilarSpotApi[] }) => setSpots((body.results ?? []).map(similarToSpot)))
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setSpots([]);
      });
    return () => ctrl.abort();
  }, [spotId, sport]);
  return spots;
}

/** Resolve light search hits to full catalogue Spots (image/region/meta). */
function enrichSpots(hits: api.SearchSpot[], catalogue: Spot[]): Spot[] {
  const bySlug = new Map<string, Spot>();
  const byId = new Map<string, Spot>();
  for (const s of catalogue) {
    if (s.slug) bySlug.set(s.slug, s);
    byId.set(s.id, s);
    if (s.uuid) byId.set(s.uuid, s);
  }
  return hits.map((h) => bySlug.get(h.slug) ?? byId.get(h.id)).filter((s): s is Spot => Boolean(s));
}

// --- page ------------------------------------------------------------------

/**
 * Search results in an Airbnb-style split: tiles on the left, a companion map
 * on the right. Three tile rows top-to-bottom — direct hits, spots with a
 * comparable profile, and what's performing right now — plus the region
 * rankings for the open-axis queries. Everything renders in the landing's own
 * grammar (SpotCard / RegionTile) so a result reads as the same product.
 *
 * Routing by open axes (place × time):
 *  • place present (spot/region/free text) → GET /search → direct hits + similar + performing.
 *  • place open + a month → GET /search/best-regions → region ranking + performing.
 *  • place open + time open ("nur Suchen") → discovery: performing + a map around the visitor.
 *  • ?mode=weeks + an entity → GET /areas/best-weeks → the temporal "best weeks" list.
 */
export default function SearchResults() {
  const [params] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const sport = params.get("sport") ?? undefined;
  const week = params.get("week");
  const month = params.get("month");
  const spotId = params.get("spot_id") ?? undefined;
  const regionId = params.get("region_id") ?? undefined;
  const mode = params.get("mode"); // "weeks" → the temporal best-weeks list

  const placeOpen = !q && !spotId && !regionId;
  const timeOpen = !week && !month;
  const placeEntity = spotId ?? regionId;

  const showWeeks = mode === "weeks" && Boolean(placeEntity);
  const discovery = placeOpen && timeOpen && !showWeeks;
  const showBestRegions = placeOpen && !timeOpen && !showWeeks; // a month, place open
  const showSearch = !placeOpen && !showWeeks; // a place is present

  // Shared data.
  const { data: catalogue } = useSpots({ limit: 100 });
  const { data: topSpots } = useTopSpots(6);
  const performing = useMemo(() => (topSpots ?? []).slice(0, 6), [topSpots]);
  // Region catalogue (SWR-cached under the "regions" key — every consumer on
  // this page, including DiscoveryRegions below, shares the one fetch) so
  // direct-hit region tiles can carry image/country/spot_count/sports
  // without an extra request per tile.
  const { data: regionsCatalogue } = useRegions();
  const regionById = useMemo(
    () => new Map((regionsCatalogue ?? []).map((r) => [r.id, r])),
    [regionsCatalogue],
  );

  const [result, setResult] = useState<api.SearchResult | null>(null);
  const [bestRegions, setBestRegions] = useState<api.BestRegionsResponse | null>(null);
  const [regionMeta, setRegionMeta] = useState<Map<string, api.Region>>(new Map());
  const [bestWeeks, setBestWeeks] = useState<api.BestWeeksResponse | null>(null);
  const [loading, setLoading] = useState(!discovery);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (discovery) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    setResult(null);
    setBestRegions(null);
    setRegionMeta(new Map());
    setBestWeeks(null);

    let run: Promise<unknown>;
    if (showWeeks) {
      run = api.getBestWeeks({ spot_id: spotId, region_id: regionId, sport }).then((r) => alive && setBestWeeks(r));
    } else if (showBestRegions) {
      run = Promise.all([
        api.getBestRegions({ sport, month: month ? Number(month) : undefined }),
        api.getRegions(),
      ]).then(([r, regions]) => {
        if (!alive) return;
        setBestRegions(r);
        setRegionMeta(new Map(regions.map((x) => [x.id, x])));
      });
    } else {
      // A place is present (spot / region / free text, incl. the geocoded
      // "nearby" fallback). Always resolve to spots so picking a spot shows
      // that spot — not the best-weeks list.
      run = api.getSearch({ q, sport, week: week ? Number(week) : undefined }).then((r) => alive && setResult(r));
    }

    run
      .catch((e) => alive && setError(e instanceof api.ApiError ? e.message : "Suche fehlgeschlagen."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [q, sport, week, month, spotId, regionId, discovery, showWeeks, showBestRegions, retry]);

  const monthName = month ? MONTHS[Number(month) - 1] : null;
  const geocodeName = result?.geocode?.name;
  const nearby = result?.resolved === "point" || result?.resolved === "area";

  const heading = showWeeks
    ? `Beste Wochen für „${q}“`
    : discovery
    ? "Entdecken"
    : showBestRegions
    ? monthName ? `Beste Reviere im ${monthName}` : "Beste Reviere"
    : nearby && geocodeName
    ? result?.resolved === "area" ? `Spots in ${geocodeName}` : `Spots in der Nähe von ${geocodeName}`
    : q ? `Ergebnisse für „${q}“` : "Suche";

  // Direct-hit spots (enriched) + the anchor for the "comparable profile" row.
  const directSpots = useMemo(
    () => (result ? enrichSpots(result.spots, catalogue ?? []) : []),
    [result, catalogue],
  );
  const anchorSpotId = spotId ?? directSpots[0]?.uuid ?? directSpots[0]?.id;
  const similar = useSimilarSpots(showSearch ? anchorSpotId : undefined, sport);

  // Live conditions for everything shown on tiles/map.
  const liveIds = useMemo(
    () => Array.from(new Set([...directSpots, ...similar, ...performing].map((s) => s.id))),
    [directSpots, similar, performing],
  );
  const { data: liveData } = useSpotsLive(liveIds);
  const live = liveData ?? undefined;

  const mapSpots = useMemo(() => {
    const seen = new Set<string>();
    const out: Spot[] = [];
    for (const s of [...directSpots, ...similar, ...performing]) {
      if (s.coords && !seen.has(s.id)) {
        seen.add(s.id);
        out.push(s);
      }
    }
    return out;
  }, [directSpots, similar, performing]);
  const center = centerFor(directSpots, performing);

  const directRegions = useMemo(
    () =>
      (result?.regionen ?? []).map((r) => {
        const meta = regionById.get(r.id);
        return {
          slug: r.slug,
          name: r.name,
          country: meta?.country ?? null,
          image: meta?.image,
          spotCount: meta?.spot_count ?? null,
          sports: meta?.sports ?? null,
        };
      }),
    [result, regionById],
  );

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <ResultsHeader />

      <main className="flex-1 pt-20 sm:pt-24">
        {loading && (
          <div className="mx-auto w-full max-w-[1570px] px-4 pt-2 sm:px-8">
            <ResultHead heading={heading} />
            <div className="mt-8">
              <SpotGridSkeleton />
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="mx-auto w-full max-w-[1570px] px-4 pt-2 sm:px-8">
            <ResultHead heading={heading} />
            <div className="mt-8">
              <ErrorBanner message={error} onRetry={() => setRetry((n) => n + 1)} />
            </div>
          </div>
        )}

        {!loading && !error && showWeeks && bestWeeks && (
          <div className="mx-auto w-full max-w-[1180px] px-4 pt-2 pb-16 sm:px-8">
            <ResultHead heading={heading} />
            <div className="mt-8">
              <BestWeeksList data={bestWeeks} place={q} />
            </div>
          </div>
        )}

        {!loading && !error && (discovery || showBestRegions || showSearch) && (
          <SplitView
            head={<ResultHead heading={heading} />}
            mapSpots={discovery ? (catalogue ?? []).filter((s) => s.coords) : mapSpots}
            center={center}
            live={live}
          >
            {showSearch && (
              <>
                <RegionRow title="Direkte Treffer" subtitle="Regionen zu deiner Suche" regions={directRegions} />
                <SpotRow
                  title={directRegions.length ? "Spots" : "Direkte Treffer"}
                  subtitle={nearby && geocodeName ? `In der Nähe von ${geocodeName}` : "Passend zu deiner Suche"}
                  spots={directSpots}
                  live={live}
                />
                {directSpots.length === 0 && directRegions.length === 0 && (
                  <EmptyState message="Keine direkten Treffer. Versuche einen anderen Ort oder Spotnamen." />
                )}
                <SpotRow title="Vergleichbares Profil" subtitle="Spots mit ähnlichem Charakter" spots={similar} live={live} />
              </>
            )}

            {showBestRegions && (
              <BestRegionsRow data={bestRegions} monthName={monthName} meta={regionMeta} />
            )}

            <SpotRow title="Gerade gut" subtitle="Spots mit aktuell guten Bedingungen" spots={performing} live={live} />

            {discovery && <DiscoveryRegions />}
          </SplitView>
        )}
      </main>

      <Footer />
    </div>
  );
}

// --- open-axis pieces ------------------------------------------------------

function BestRegionsRow({
  data,
  monthName,
  meta,
}: {
  data: api.BestRegionsResponse | null;
  monthName: string | null;
  meta: Map<string, api.Region>;
}) {
  const ranking = (data?.regions ?? []).filter((r) => (r.coverage ?? 0) > 0 || (r.intensity ?? 0) > 0);
  if (ranking.length === 0) {
    return <EmptyState message="Noch keine Saisondaten (Klimatologie fehlt für die veröffentlichten Spots)." />;
  }
  return (
    <RegionRow
      title="Direkte Treffer"
      subtitle={`Beste Reviere ${monthName ? `im ${monthName}` : "über die Saison"} · nach Abdeckung`}
      regions={ranking.map((r) => {
        const m = r.id ? meta.get(r.id) : undefined;
        return {
          slug: r.slug ?? m?.slug ?? "",
          name: r.name ?? m?.name ?? r.slug ?? "",
          country: m?.country ?? null,
          image: m?.image,
          spotCount: m?.spot_count ?? null,
          sports: m?.sports ?? null,
        };
      })}
    />
  );
}

/** Season ranking of regions for the discovery view ("gerade gut performen"). */
function DiscoveryRegions() {
  const [data, setData] = useState<api.BestRegionsResponse | null>(null);
  const [meta, setMeta] = useState<Map<string, api.Region>>(new Map());
  const { data: regions } = useRegions();

  useEffect(() => {
    let alive = true;
    api.getBestRegions({}).then((r) => alive && setData(r)).catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (regions) setMeta(new Map(regions.map((x) => [x.id, x])));
  }, [regions]);

  const ranking = (data?.regions ?? [])
    .filter((r) => (r.coverage ?? 0) > 0 || (r.intensity ?? 0) > 0)
    .slice(0, 4);
  if (ranking.length === 0) return null;
  return (
    <RegionRow
      title="Top-Regionen"
      subtitle="Reviere, die gerade gut laufen"
      regions={ranking.map((r) => {
        const m = r.id ? meta.get(r.id) : undefined;
        return {
          slug: r.slug ?? m?.slug ?? "",
          name: r.name ?? m?.name ?? r.slug ?? "",
          country: m?.country ?? null,
          image: m?.image,
          spotCount: m?.spot_count ?? null,
          sports: m?.sports ?? null,
        };
      })}
    />
  );
}

/** The temporal "best weeks" answer — a bar list, reached via ?mode=weeks. */
function BestWeeksList({ data, place }: { data: api.BestWeeksResponse; place: string }) {
  const weeks = (data.weeks ?? []).filter((w) => (w.score ?? 0) > 0).slice(0, 12);
  if (weeks.length === 0) {
    return <EmptyState message="Noch keine Saisondaten für diesen Ort (Klimatologie fehlt)." />;
  }
  const max = Math.max(...weeks.map((w) => w.score ?? 0), 0.01);
  const best = weeks[0]?.week;
  return (
    <section>
      <p className="mb-4 max-w-[62ch] text-body text-muted">Die besten Wochen für {place || "diesen Ort"} — nach nutzbaren Stunden.</p>
      <ul className="space-y-2">
        {weeks.map((w) => {
          const isBest = w.week === best;
          return (
            <li key={w.week} className="flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3">
              <span className="w-16 shrink-0 font-medium text-ink">KW {w.week}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-line">
                <span className={`block h-full rounded-full ${isBest ? "bg-orange" : "bg-teal"}`} style={{ width: `${Math.round(((w.score ?? 0) / max) * 100)}%` }} />
              </span>
              {typeof w.score === "number" && (
                <span className="w-24 shrink-0 text-right text-label text-muted" title="Anteil der Zeit mit fahrbaren Bedingungen in dieser Woche">
                  <span className="data-accent">{Math.round(w.score * 100)}%</span> nutzbar
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
