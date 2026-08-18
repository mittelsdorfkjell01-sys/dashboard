import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import Header from "../components/Header";
import Footer from "../components/Footer";
import SearchBar from "../components/SearchBar";
import SpotCard from "../components/SpotCard";
import RegionTile from "../components/RegionTile";
import TopSpotsRow from "../components/TopSpotsRow";
import { SectionBand } from "../components/editorial";
import { ErrorBanner, EmptyState, SpotGridSkeleton } from "../components/AsyncStates";
import * as api from "../lib/api";
import { sportLabel } from "../lib/labels";
import { spotPath } from "../lib/spotRoutes";
import { useSpots, useSpotsLive, useRegions } from "../lib/hooks";
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

/** Grey chip carrying one facet of the query the visitor just submitted, so the
 *  result head mirrors the question back. Same 8px radius + hairline as the rest
 *  of the UI. */
function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-2xl border border-line bg-surface px-3 py-1.5 text-label font-medium text-ink">
      {children}
    </span>
  );
}

/**
 * Search results. Three rankings, chosen from which axes are open (place × time):
 *  • place fixed + time fixed/free  → GET /search  (spots/regions, incl. the
 *    geocoded "in der Nähe von …" fallback for a place the catalogue doesn't hold).
 *  • place fixed (entity) + time open → GET /areas/best-weeks  (best weeks here).
 *  • place open + a month            → GET /search/best-regions (best regions).
 *  • place open + time open ("nur Suchen") → a discovery view: a map around the
 *    visitor's location, else the current top spots + regions.
 *
 * Everything renders in the site's editorial grammar (LandingHeader chrome aside):
 * the 1570px content frame, SectionBand rhythm and the SpotCard / RegionTile
 * tiles — so a result reads as the same product as the landing, not a separate
 * dashboard.
 */
export default function SearchResults() {
  const [params] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const sport = params.get("sport") ?? undefined;
  // The landing search forwards every selected sport as a CSV `sports=` (the
  // backend still reads only the first `sport=`, so ranking is unchanged); the
  // head shows all of them so a multi-sport query is mirrored back in full.
  const sports = (params.get("sports")?.split(",").filter(Boolean)) ?? (sport ? [sport] : []);
  const week = params.get("week");
  const month = params.get("month");
  const spotId = params.get("spot_id") ?? undefined;
  const regionId = params.get("region_id") ?? undefined;

  const placeOpen = !q && !spotId && !regionId;
  const timeOpen = !week && !month;
  const placeEntity = spotId ?? regionId;
  // "Nur Suchen": both axes open and no month picked → the discovery view.
  const discovery = placeOpen && timeOpen;

  const [result, setResult] = useState<api.SearchResult | null>(null);
  const [bestRegions, setBestRegions] = useState<api.BestRegionsResponse | null>(null);
  const [regionMeta, setRegionMeta] = useState<Map<string, api.Region>>(new Map());
  const [bestWeeks, setBestWeeks] = useState<api.BestWeeksResponse | null>(null);
  const [loading, setLoading] = useState(!discovery);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  // Catalogue (persistent, shared with the landing): used to enrich the light
  // search hits into full SpotCards (image, region, meta).
  const { data: catalogue } = useSpots({ limit: 100 });

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
    if (placeOpen) {
      // WO offen (aber ein Monat gewählt) → beste Reviere. Regionen-Stammdaten
      // (Bild/Land) parallel laden und per id zuordnen, damit die Kacheln
      // denselben Look wie der Rest der Seite bekommen.
      run = Promise.all([
        api.getBestRegions({ sport, month: month ? Number(month) : undefined }),
        api.getRegions(),
      ]).then(([r, regions]) => {
        if (!alive) return;
        setBestRegions(r);
        setRegionMeta(new Map(regions.map((x) => [x.id, x])));
      });
    } else if (placeEntity && timeOpen) {
      // Ort fix + WANN offen → beste Wochen für diesen Ort
      run = api
        .getBestWeeks({ spot_id: spotId, region_id: regionId, sport })
        .then((r) => alive && setBestWeeks(r));
    } else {
      // Ort + Zeit fix (oder Freitext, inkl. geocodiertem "in der Nähe von …")
      run = api
        .getSearch({ q, sport, week: week ? Number(week) : undefined })
        .then((r) => alive && setResult(r));
    }

    run
      .catch(
        (e) =>
          alive &&
          setError(e instanceof api.ApiError ? e.message : "Suche fehlgeschlagen.")
      )
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [q, sport, week, month, spotId, regionId, placeOpen, placeEntity, timeOpen, discovery, retry]);

  const monthName = month ? MONTHS[Number(month) - 1] : null;

  // Timeframe chip label (open → nothing).
  const timeChip = week ? `KW ${week}` : monthName ?? null;
  // Place / nearby heading. For a geocoded place the /search result carries the
  // resolved name, so "Kiel" (not in the catalogue) reads as "in der Nähe von Kiel".
  const geocodeName = result?.geocode?.name;
  const nearby = result?.resolved === "point" || result?.resolved === "area";

  const heading = discovery
    ? "Entdecken"
    : placeOpen
    ? monthName
      ? `Beste Reviere im ${monthName}`
      : "Beste Reviere für die Saison"
    : placeEntity && timeOpen
    ? `Beste Wochen für „${q}“`
    : nearby && geocodeName
    ? result?.resolved === "area"
      ? `Spots in ${geocodeName}`
      : `Spots in der Nähe von ${geocodeName}`
    : `Suche: „${q}“`;

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <Header />

      <main className="flex-1 pt-20 sm:pt-24">
        {/* Result head — mirrors the question back: breadcrumb, headline, the
            query as chips, and a search bar to refine right where you are. */}
        <SectionBand tone="page" pad="sm" className="pt-2">
          <nav className="text-caption font-medium text-muted">
            <Link to="/" className="hover:underline">Übersicht</Link>
            <span className="mx-1.5 text-muted">›</span>
            <span className="text-ink">Suche</span>
          </nav>

          <h1 className="mt-2 text-[28px] font-semibold leading-tight text-balance text-ink sm:text-[32px]">
            {heading}
          </h1>

          {(sports.length > 0 || timeChip || (!nearby && q)) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {!nearby && q && <Chip>{q}</Chip>}
              {timeChip && <Chip>{timeChip}</Chip>}
              {sports.map((s) => (
                <Chip key={s}>{sportLabel(s)}</Chip>
              ))}
            </div>
          )}

          <div className="mt-6 max-w-[760px]">
            <SearchBar />
          </div>
        </SectionBand>

        {loading && (
          <SectionBand tone="page" pad="md">
            <SpotGridSkeleton />
          </SectionBand>
        )}

        {error && !loading && (
          <SectionBand tone="page" pad="md">
            <ErrorBanner message={error} onRetry={() => setRetry((n) => n + 1)} />
          </SectionBand>
        )}

        {!loading && !error && (
          <>
            {discovery && <DiscoveryView />}

            {result && (
              <SearchHits result={result} catalogue={catalogue ?? []} />
            )}

            {bestRegions && (
              <BestRegionsSection data={bestRegions} monthName={monthName} meta={regionMeta} />
            )}

            {bestWeeks && <BestWeeksSection data={bestWeeks} place={q} />}

            {/* Achsen-Cross-Sell — die jeweils andere Achse als eigener Bereich. */}
            {placeEntity && (
              <CrossSell
                to={
                  timeOpen
                    ? // gerade "beste Wochen" → ähnliche Reviere entdecken
                      `/search?${new URLSearchParams({ ...(sport ? { sport } : {}), ...(month ? { month } : {}) }).toString()}`
                    : // Ergebnis für eine feste Woche → wann ist es hier am besten?
                      `/search?${new URLSearchParams({ ...(spotId ? { spot_id: spotId } : {}), ...(regionId ? { region_id: regionId } : {}), q, ...(sport ? { sport } : {}) }).toString()}`
                }
                label={
                  timeOpen
                    ? "Ähnliche Reviere entdecken"
                    : `Wann ist es in „${q}“ am besten?`
                }
              />
            )}
          </>
        )}
      </main>

      <Footer />
    </div>
  );
}

/** Resolve a light search hit to a full catalogue Spot (image/region/meta) so it
 *  renders as the same tile used everywhere else. Matches by slug first, then by
 *  the spot's uuid/id. */
function enrichSpots(hits: api.SearchSpot[], catalogue: Spot[]): Spot[] {
  const bySlug = new Map<string, Spot>();
  const byId = new Map<string, Spot>();
  for (const s of catalogue) {
    if (s.slug) bySlug.set(s.slug, s);
    byId.set(s.id, s);
    if (s.uuid) byId.set(s.uuid, s);
  }
  return hits
    .map((h) => bySlug.get(h.slug) ?? byId.get(h.id))
    .filter((s): s is Spot => Boolean(s));
}

function SearchHits({
  result,
  catalogue,
}: {
  result: api.SearchResult;
  catalogue: Spot[];
}) {
  const spots = useMemo(() => enrichSpots(result.spots, catalogue), [result.spots, catalogue]);
  const { data: live } = useSpotsLive(spots.map((s) => s.id));

  const empty = result.regionen.length === 0 && result.spots.length === 0;
  if (empty) {
    return (
      <SectionBand tone="page" pad="md">
        <EmptyState message="Keine Treffer. Versuche einen anderen Ort oder Spotnamen." />
      </SectionBand>
    );
  }

  return (
    <>
      {result.regionen.length > 0 && (
        <SectionBand tone="page" pad="md" heading="Regionen">
          <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3">
            {result.regionen.map((r, i) => (
              <div
                key={r.id}
                className="animate-fade-up"
                style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
              >
                <RegionTile slug={r.slug} name={r.name} windMonths={null} />
              </div>
            ))}
          </div>
        </SectionBand>
      )}

      {result.spots.length > 0 && (
        <SectionBand tone="page" pad="md" heading="Spots">
          {spots.length > 0 ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-8 sm:gap-y-10 lg:grid-cols-5">
              {spots.map((spot, i) => (
                <div
                  key={spot.id}
                  className="animate-fade-up"
                  style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
                >
                  <SpotCard spot={spot} live={live?.get(spot.id)} />
                </div>
              ))}
            </div>
          ) : (
            // Catalogue not (yet) resolvable — never show a blank section.
            <ul className="space-y-2">
              {result.spots.map((s) => (
                <li key={s.id}>
                  <Link
                    to={spotPath({ slug: s.slug, name: s.name })}
                    className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-4 py-3 transition-colors hover:bg-band/60"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink">{s.name}</span>
                      <span className="block truncate text-caption text-muted">
                        {s.sports.map(sportLabel).join(", ")}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </SectionBand>
      )}
    </>
  );
}

function BestRegionsSection({
  data,
  monthName,
  meta,
}: {
  data: api.BestRegionsResponse;
  monthName: string | null;
  meta: Map<string, api.Region>;
}) {
  const ranking = (data.regions ?? []).filter(
    (r) => (r.coverage ?? 0) > 0 || (r.intensity ?? 0) > 0
  );
  if (ranking.length === 0) {
    return (
      <SectionBand tone="page" pad="md">
        <EmptyState message="Noch keine Saisondaten (Klimatologie fehlt für die veröffentlichten Spots)." />
      </SectionBand>
    );
  }
  return (
    <SectionBand tone="page" pad="md">
      <p className="mb-6 max-w-[62ch] text-body text-muted">
        Die besten Reviere {monthName ? `im ${monthName}` : "über die Saison"} · geordnet
        nach Abdeckung (Anteil der Spots mit fahrbaren Bedingungen).
      </p>
      <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3">
        {ranking.map((r, i) => {
          const m = r.id ? meta.get(r.id) : undefined;
          return (
            <div
              key={r.id ?? r.slug ?? i}
              className="animate-fade-up"
              style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
            >
              <RegionTile
                slug={r.slug ?? m?.slug ?? ""}
                name={r.name ?? m?.name ?? r.slug ?? ""}
                country={m?.country ?? null}
                image={api.resolveMediaUrl(m?.image?.url)}
                coverage={r.coverage ?? null}
                rank={i + 1}
                windMonths={null}
              />
            </div>
          );
        })}
      </div>
    </SectionBand>
  );
}

function BestWeeksSection({
  data,
  place,
}: {
  data: api.BestWeeksResponse;
  place: string;
}) {
  const weeks = (data.weeks ?? []).filter((w) => (w.score ?? 0) > 0).slice(0, 12);
  if (weeks.length === 0) {
    return (
      <SectionBand tone="page" pad="md">
        <EmptyState message="Noch keine Saisondaten für diesen Ort (Klimatologie fehlt)." />
      </SectionBand>
    );
  }
  const max = Math.max(...weeks.map((w) => w.score ?? 0), 0.01);
  const best = weeks[0]?.week;
  return (
    <SectionBand tone="page" pad="md">
      <p className="mb-4 max-w-[62ch] text-body text-muted">
        Die besten Wochen für {place || "diesen Ort"} — nach nutzbaren Stunden.
      </p>
      <ul className="space-y-2">
        {weeks.map((w) => {
          const isBest = w.week === best;
          return (
            <li
              key={w.week}
              className="flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3"
            >
              <span className="w-16 shrink-0 font-medium text-ink">KW {w.week}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-line">
                {/* Data bar in the shared data accent (teal); the peak week is
                    flagged with the attention colour (orange), matching the
                    "best season" role used across the site. */}
                <span
                  className={`block h-full rounded-full ${isBest ? "bg-orange" : "bg-teal"}`}
                  style={{ width: `${Math.round(((w.score ?? 0) / max) * 100)}%` }}
                />
              </span>
              {typeof w.score === "number" && (
                <span
                  className="w-24 shrink-0 text-right text-label text-muted"
                  title="Anteil der Zeit mit fahrbaren Bedingungen in dieser Woche"
                >
                  <span className="data-accent">{Math.round(w.score * 100)}%</span> nutzbar
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </SectionBand>
  );
}

/** The other axis, as its own band — turns three result types into one
 *  exploration space instead of three dead ends. */
function CrossSell({ to, label }: { to: string; label: string }) {
  return (
    <SectionBand tone="band" pad="md">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-body font-medium text-ink-soft">Noch nicht das Richtige?</p>
        <Link
          to={to}
          className="inline-flex min-h-11 items-center gap-1.5 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
        >
          {label} ›
        </Link>
      </div>
    </SectionBand>
  );
}

/**
 * "Nur Suchen" landed here with both axes open. Ask for the visitor's location:
 * a map around it if granted, otherwise fall back to the current top spots and
 * top regions — never an empty screen, and always in the site's own grammar.
 */
function DiscoveryView() {
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null | "denied">(null);
  const { data: spots } = useSpots({ limit: 100 });

  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setCoords("denied");
      return;
    }
    let alive = true;
    navigator.geolocation.getCurrentPosition(
      (p) => alive && setCoords({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => alive && setCoords("denied"),
      { timeout: 8000, maximumAge: 10 * 60 * 1000 }
    );
    return () => {
      alive = false;
    };
  }, []);

  const withCoords = (spots ?? []).filter((s) => s.coords);

  // Located → a live map centred on the visitor, spots as pins.
  if (coords && coords !== "denied" && withCoords.length > 0) {
    return (
      <SectionBand tone="page" pad="md" heading="Spots in deiner Nähe">
        <div className="overflow-hidden rounded-3xl border border-line">
          <MapContainer
            center={[coords.lat, coords.lon]}
            zoom={8}
            zoomControl={false}
            scrollWheelZoom
            className="h-[360px] w-full sm:h-[520px]"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
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
    );
  }

  // Still asking (null) or denied → the current top spots + top regions.
  return (
    <>
      <SectionBand tone="page" pad="md" heading="Aktuelle Top-Spots">
        <TopSpotsRow />
      </SectionBand>
      <SectionBand tone="band" pad="md" heading="Top-Regionen aktuell">
        <TopRegions />
      </SectionBand>
    </>
  );
}

/** Season ranking of regions, tiles in the landing grammar. */
function TopRegions() {
  const [data, setData] = useState<api.BestRegionsResponse | null>(null);
  const [meta, setMeta] = useState<Map<string, api.Region>>(new Map());
  const { data: regions } = useRegions();

  useEffect(() => {
    let alive = true;
    api.getBestRegions({}).then((r) => alive && setData(r));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (regions) setMeta(new Map(regions.map((x) => [x.id, x])));
  }, [regions]);

  const ranking = (data?.regions ?? [])
    .filter((r) => (r.coverage ?? 0) > 0 || (r.intensity ?? 0) > 0)
    .slice(0, 6);

  if (ranking.length === 0) {
    return <EmptyState message="Noch keine Regionen-Daten verfügbar." />;
  }
  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3">
      {ranking.map((r, i) => {
        const m = r.id ? meta.get(r.id) : undefined;
        return (
          <div key={r.id ?? r.slug ?? i} className="animate-fade-up" style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}>
            <RegionTile
              slug={r.slug ?? m?.slug ?? ""}
              name={r.name ?? m?.name ?? r.slug ?? ""}
              country={m?.country ?? null}
              image={api.resolveMediaUrl(m?.image?.url)}
              coverage={r.coverage ?? null}
              rank={i + 1}
              windMonths={null}
            />
          </div>
        );
      })}
    </div>
  );
}
