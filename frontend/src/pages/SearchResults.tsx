import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import ResultsHeader from "../components/ResultsHeader";
import Footer from "../components/Footer";
import SpotCard from "../components/SpotCard";
import RegionTile from "../components/RegionTile";
import { ErrorBanner, EmptyState, SpotGridSkeleton } from "../components/AsyncStates";
import { MapIcon } from "../lib/icons";
import { countryName } from "../lib/flags";
import { framingFor, REGION_FOCUS_ZOOM } from "../weather-map/camera";
import { windMapHref } from "../weather-map/fieldUrlState";
import { sportLabel } from "../lib/labels";
import * as api from "../lib/api";
import { API_BASE, resolveMediaUrl } from "../lib/api";
import { useSpots, useSpotsLive, useTopSpots, useRegions } from "../lib/hooks";
import { useSpotOriginsMixed } from "../context/SpotOriginContext";
import Chip from "../components/ui/Chip";
import type { Spot } from "../lib/types";
import { trackEvent } from "../lib/events";

// The one weather map, docked beside the results. Lazily imported: a result
// column read on a phone never pays for MapLibre.
const WindExplorer = lazy(() => import("../weather-map/WindExplorer"));

const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];


// --- shared bits -----------------------------------------------------------

/** Breadcrumb + heading — shared by every axis so it can sit either above the
 *  content (loading/error/best-weeks) or inside the split-view grid (so its
 *  row lines up with the map). */
function ResultHead({ heading, summary }: { heading: string; summary?: string }) {
  return (
    <>
      <nav className="text-caption font-medium text-muted">
        <Link to="/" className="hover:underline">Übersicht</Link>
        <span className="mx-1.5 text-muted">›</span>
        <span className="text-ink">Suche</span>
      </nav>
      <h1 className="mt-2 text-heading-lg font-semibold leading-tight text-balance text-ink">{heading}</h1>
      {summary && <p role="status" className="mt-2 text-body text-muted">Aktive Suche: {summary}</p>}
    </>
  );
}

/** One tile row: a heading + a grid of spot cards. The column runs the full
 *  page now that the companion map is gone, so the grid widens with it
 *  (2 on phones, 3 from sm, 4 from lg) instead of stretching three cards. */
function SpotRow({
  title,
  subtitle,
  spots,
  live,
  surface = "search",
}: {
  title: string;
  subtitle?: string;
  spots: Spot[];
  live?: Map<string, api.LiveConditionsRead>;
  surface?: string;
}) {
  if (spots.length === 0) return null;
  return (
    <section className="pt-2">
      <div>
        <h2 className="text-title font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-1 text-caption text-muted">{subtitle}</p>}
      </div>
      <div className="mt-5 grid grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-4">
        {spots.map((spot) => (
          <div key={spot.id}>
            <SpotCard spot={spot} live={live?.get(spot.id)} surface={surface} />
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
      <div className="mt-5 grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-3">
        {regions.map((r, i) => (
          <div key={r.slug || i}>
            <RegionTile slug={r.slug} name={r.name} country={r.country} image={r.image} spotCount={r.spotCount} sports={r.sports} />
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * The results layout: tiles in the reading column, the weather map docked
 * beside it from lg up. The map is the site's one map (the page's own Leaflet
 * copy was deleted 2026-10-10) — the wind field, framed on whatever the search
 * resolved to and locked to wind: there is nothing to toggle to beside a list
 * of results. Below lg the column runs full width and the map is one tap away
 * through the floating "Karte" pill.
 */
export const RESULTS_COLUMN = "mx-auto w-full max-w-[1180px] px-4 pt-2 pb-16 sm:px-8";

function ResultsLayout({
  children,
  head,
  frame,
}: {
  children: React.ReactNode;
  /** Rendered atop the column, above the results. */
  head?: React.ReactNode;
  /** Camera for the companion map; null → no map (nothing resolved yet). */
  frame: { center: [number, number]; zoom: number } | null;
}) {
  return (
    <div className="mx-auto w-full max-w-[1570px] px-4 pt-2 pb-16 sm:px-8">
      <div className={frame ? "lg:grid lg:grid-cols-[1fr_minmax(360px,40%)] lg:gap-8" : undefined}>
        <div className="min-w-0">
          {head}
          <div className="mt-8 space-y-10">{children}</div>
        </div>

        {frame && (
          <div className="hidden lg:block">
            {/* Docked beneath the persistent header and held there while the
                result column scrolls independently. */}
            <div
              className="sticky top-24 h-[calc(100vh-7.5rem)] min-h-[420px] max-h-[720px] overflow-hidden rounded-card border border-line"
              data-lenis-prevent
            >
              <Suspense fallback={<div className="h-full w-full animate-pulse bg-band" />}>
                <WindExplorer embedded focus={frame} />
              </Suspense>
            </div>
          </div>
        )}
      </div>

      {/* Below lg the map opens as the full page it is, already framed. */}
      {frame && (
        <Link
          to={windMapHref(frame.center, frame.zoom, { toggle: false })}
          aria-label="Karte öffnen"
          className="fixed bottom-6 left-1/2 z-sticky flex -translate-x-1/2 items-center gap-1.5 rounded-card bg-page px-4 py-2 text-ui font-normal text-white shadow-float lg:hidden"
        >
          Karte <MapIcon className="text-body" />
        </Link>
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
  origin?: api.SpotOrigin;
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
    origin: item.origin ?? "editorial",
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
  const [params, setParams] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const sport = params.get("sport") ?? undefined;
  const week = params.get("week");
  const month = params.get("month");
  const spotId = params.get("spot_id") ?? undefined;
  const regionId = params.get("region_id") ?? undefined;
  const mode = params.get("mode"); // "weeks" → the temporal best-weeks list
  const originParam = params.get("origin");

  const eventKey = params.toString();
  useEffect(() => {
    const eventParams = new URLSearchParams(eventKey);
    trackEvent("search", {
      surface: "search",
      context: {
        query: (eventParams.get("q") ?? "").trim().slice(0, 120),
        sport: eventParams.get("sport"),
        mode: eventParams.get("mode"),
      },
    });
  }, [eventKey]); // one event per navigated search URL

  const placeOpen = !q && !spotId && !regionId;
  const timeOpen = !week && !month;
  const placeEntity = spotId ?? regionId;

  const showWeeks = mode === "weeks" && Boolean(placeEntity);
  const discovery = placeOpen && timeOpen && !showWeeks;
  const showBestRegions = placeOpen && !timeOpen && !showWeeks; // a month, place open
  const showSearch = !placeOpen && !showWeeks; // a place is present

  // Herkunftsfacette: nur wirksam, solange der Katalog überhaupt gemischt ist
  // (sonst filtert sie entweder alles oder nichts), und nur für die Listen, bei
  // denen die Herkunft am Treffer selbst mitkommt.
  const originsMixed = useSpotOriginsMixed();
  const originFilter =
    originsMixed && (originParam === "editorial" || originParam === "community")
      ? (originParam as api.SpotOrigin)
      : null;
  const byOrigin = useCallback(
    (spots: Spot[]) =>
      originFilter ? spots.filter((spot) => (spot.origin ?? "editorial") === originFilter) : spots,
    [originFilter],
  );
  const setOriginFilter = (next: api.SpotOrigin | null) => {
    const nextParams = new URLSearchParams(params);
    if (next) nextParams.set("origin", next);
    else nextParams.delete("origin");
    setParams(nextParams, { replace: true });
  };

  // Shared data.
  const { data: catalogue, loading: catalogueLoading, error: catalogueError, reload: reloadCatalogue } = useSpots({ limit: 100 });
  const { data: topSpots, error: topSpotsError, reload: reloadTopSpots } = useTopSpots(6);
  const performing = useMemo(() => byOrigin((topSpots ?? []).slice(0, 6)), [topSpots, byOrigin]);
  // Region catalogue (SWR-cached under the "regions" key — every consumer on
  // this page, including DiscoveryRegions below, shares the one fetch) so
  // direct-hit region tiles can carry image/country/spot_count/sports
  // without an extra request per tile.
  const { data: regionsCatalogue, error: regionsError, reload: reloadRegions } = useRegions();
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
  const filterSummary = [
    q || (placeOpen ? "überall" : null),
    sport ? sportLabel(sport) : "alle Sportarten",
    monthName ?? (week ? `Kalenderwoche ${week}` : "jederzeit"),
    originFilter === "editorial"
      ? "von der Redaktion"
      : originFilter === "community"
      ? "von der Community"
      : null,
  ].filter(Boolean).join(" · ");
  const pageLoading = loading || (discovery && catalogueLoading && !catalogue);
  const criticalError = error ?? (discovery && !catalogue ? catalogueError : null);
  const partialError = criticalError ? null : catalogueError ?? topSpotsError ?? regionsError;
  const retryAll = () => {
    setRetry((value) => value + 1);
    reloadCatalogue();
    reloadTopSpots();
    reloadRegions();
  };

  // Direct-hit spots (enriched) + the anchor for the "comparable profile" row.
  const directSpots = useMemo(
    () => byOrigin(result ? enrichSpots(result.spots, catalogue ?? []) : []),
    [result, catalogue, byOrigin],
  );
  const anchorSpotId = spotId ?? directSpots[0]?.uuid ?? directSpots[0]?.id;
  const similarAll = useSimilarSpots(showSearch ? anchorSpotId : undefined, sport);
  const similar = useMemo(() => byOrigin(similarAll), [similarAll, byOrigin]);

  // Live conditions for everything shown on tiles/map.
  const liveIds = useMemo(
    () => Array.from(new Set([...directSpots, ...similar, ...performing].map((s) => s.id))),
    [directSpots, similar, performing],
  );
  const { data: liveData } = useSpotsLive(liveIds);
  const live = liveData ?? undefined;

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

  // What the companion map should be looking at, in the order the search
  // itself resolved: a named region is an area, so it gets the region frame;
  // otherwise the hits (or, on the discovery view, what's performing) are
  // framed by their own bounding box. Nothing resolved → no map.
  const mapFrame = useMemo(() => {
    const regionCenter = (result?.regionen ?? [])
      .map((r) => regionById.get(r.id)?.center)
      .find((center): center is NonNullable<typeof center> => Boolean(center));
    if (regionCenter) return { center: [regionCenter.lon, regionCenter.lat] as [number, number], zoom: REGION_FOCUS_ZOOM };
    const framed = directSpots.length ? directSpots : similar.length ? similar : performing;
    return framingFor(framed.flatMap((spot) => (spot.coords ? [spot.coords] : [])));
  }, [result, regionById, directSpots, similar, performing]);

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <ResultsHeader />

      <main className="flex-1 pt-20 sm:pt-24">
        {pageLoading && (
          <div className="mx-auto w-full max-w-page px-4 pt-2 sm:px-8">
            <ResultHead heading={heading} summary={filterSummary} />
            <div className="mt-8">
              <SpotGridSkeleton />
            </div>
          </div>
        )}

        {criticalError && !pageLoading && (
          <div className="mx-auto w-full max-w-page px-4 pt-2 sm:px-8">
            <ResultHead heading={heading} summary={filterSummary} />
            <div className="mt-8">
              <ErrorBanner title="Die Suche ist gerade nicht verfügbar." message={criticalError} onRetry={retryAll} />
            </div>
          </div>
        )}

        {!pageLoading && !criticalError && showWeeks && bestWeeks && (
          <div className={RESULTS_COLUMN}>
            <ResultHead heading={heading} summary={filterSummary} />
            <div className="mt-8">
              <BestWeeksList data={bestWeeks} place={q} />
            </div>
          </div>
        )}

        {!pageLoading && !criticalError && (discovery || showBestRegions || showSearch) && (
          <ResultsLayout frame={mapFrame} head={<ResultHead heading={heading} summary={filterSummary} />}>
            {originsMixed && (
              <OriginFacet active={originFilter} onChange={setOriginFilter} />
            )}
            {partialError && (
              <ErrorBanner
                title="Ein Teil der Ergebnisse konnte nicht geladen werden."
                message={partialError}
                onRetry={retryAll}
              />
            )}
            {showSearch && (
              <>
                <RegionRow title="Direkte Treffer" subtitle="Regionen zu deiner Suche" regions={directRegions} />
                <SpotRow
                  title={directRegions.length ? "Spots" : "Direkte Treffer"}
                  subtitle={nearby && geocodeName ? `In der Nähe von ${geocodeName}` : "Ergebnisse deiner Suche"}
                  spots={directSpots}
                  live={live}
                />
                {directSpots.length === 0 && directRegions.length === 0 && (
                  <EmptyState message="Keine direkten Treffer. Versuche einen anderen Ort oder Spotnamen." />
                )}
                <SpotRow title="Weitere Spots" subtitle="Weitere Auswahl für deine Suche" spots={similar} live={live} />
              </>
            )}

            {showBestRegions && (
              <BestRegionsRow data={bestRegions} monthName={monthName} meta={regionMeta} />
            )}

            <SpotRow title="Aktuelle Top-Spots" subtitle="Ausgewählte Spots" spots={performing} live={live} surface="now" />

            {discovery && <DiscoveryRegions />}
          </ResultsLayout>
        )}
      </main>

      <Footer />
    </div>
  );
}

/**
 * Herkunftsfacette. Die Unterscheidung ist Autorschaft, nicht Qualität —
 * deshalb steht sie hier als Auswahl und nicht als Rangfolge, und die Legende
 * sagt beides ausdrücklich. Erscheint nur, wenn der Katalog gemischt ist.
 */
function OriginFacet({
  active,
  onChange,
}: {
  active: api.SpotOrigin | null;
  onChange: (next: api.SpotOrigin | null) => void;
}) {
  const options: { value: api.SpotOrigin | null; label: string }[] = [
    { value: null, label: "Alle Spots" },
    { value: "editorial", label: "Von der Redaktion" },
    { value: "community", label: "Von der Community" },
  ];
  return (
    <div>
      <div role="group" aria-label="Herkunft der Spots" className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Chip
            key={option.label}
            active={active === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </Chip>
        ))}
      </div>
      <p className="mt-2 text-caption text-muted">
        Beide gehen durch dieselbe Freigabe — die Herkunft sagt nur, wer den Spot eingetragen hat.
      </p>
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
  const ranking = data?.regions ?? [];
  if (ranking.length === 0) {
    return <EmptyState message="Noch keine Saisondaten (Klimatologie fehlt für die veröffentlichten Spots)." />;
  }
  return (
    <RegionRow
      title="Direkte Treffer"
      subtitle={`Beste Reviere ${monthName ? `im ${monthName}` : "über die Saison"}`}
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

/** Server-ordered regions for the discovery view. */
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

  const ranking = (data?.regions ?? []).slice(0, 4);
  if (ranking.length === 0) return null;
  return (
    <RegionRow
      title="Top-Regionen"
      subtitle="Ausgewählte Reviere"
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

/** The server-ordered "best weeks" answer, reached via ?mode=weeks. */
function BestWeeksList({ data, place }: { data: api.BestWeeksResponse; place: string }) {
  const weeks = (data.weeks ?? []).slice(0, 12);
  if (weeks.length === 0) {
    return <EmptyState message="Noch keine Saisondaten für diesen Ort (Klimatologie fehlt)." />;
  }
  const best = weeks[0]?.week;
  return (
    <section>
      <p className="mb-4 max-w-measure text-body text-muted">Die besten Wochen für {place || "diesen Ort"}.</p>
      <ul className="space-y-2">
        {weeks.map((w) => {
          const isBest = w.week === best;
          return (
            <li key={w.week} className="flex items-center gap-3 rounded-card border border-line bg-surface px-4 py-3">
              <span className={`h-2 w-2 rounded-full ${isBest ? "bg-orange" : "bg-teal"}`} />
              <span className="font-medium text-ink">KW {w.week}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
