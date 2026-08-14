import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { ErrorBanner, EmptyState } from "../components/AsyncStates";
import * as api from "../lib/api";
import { sportLabel } from "../lib/labels";
import RegionTile from "../components/RegionTile";
import { spotPath } from "../lib/spotRoutes";

const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

/** A skeleton list of result rows. */
function ResultSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-xl bg-line" />
      ))}
    </div>
  );
}

/**
 * Search results — routes on which axes are open (place × time):
 *  • place fixed + time fixed/free → GET /search (spots/regions).
 *  • place fixed (entity) + time open → GET /areas/best-weeks (best weeks here).
 *  • place open → GET /search/best-regions (best regions, for a month or season).
 */
export default function SearchResults() {
  const [params] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const sport = params.get("sport") ?? undefined;
  const week = params.get("week");
  const month = params.get("month");
  const spotId = params.get("spot_id") ?? undefined;
  const regionId = params.get("region_id") ?? undefined;

  const placeOpen = !q && !spotId && !regionId;
  const timeOpen = !week && !month;
  const placeEntity = spotId ?? regionId;

  const [result, setResult] = useState<api.SearchResult | null>(null);
  const [bestRegions, setBestRegions] = useState<api.BestRegionsResponse | null>(null);
  const [regionMeta, setRegionMeta] = useState<Map<string, api.Region>>(new Map());
  const [bestWeeks, setBestWeeks] = useState<api.BestWeeksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setResult(null);
    setBestRegions(null);
    setRegionMeta(new Map());
    setBestWeeks(null);

    let run: Promise<unknown>;
    if (placeOpen) {
      // WO offen → beste Reviere (für den Monat, sonst die Saison). Regionen-
      // Stammdaten (Bild/Land) parallel laden und per id zuordnen, damit die
      // Kacheln denselben Look wie der Rest der Seite bekommen.
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
      // Ort + Zeit fix (oder Freitext) → Spot-/Regionen-Suche
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
  }, [q, sport, week, month, spotId, regionId, placeOpen, placeEntity, timeOpen, retry]);

  const monthName = month ? MONTHS[Number(month) - 1] : null;
  const heading = placeOpen
    ? monthName
      ? `Beste Reviere im ${monthName}`
      : "Beste Reviere für die Saison"
    : placeEntity && timeOpen
    ? `Beste Wochen für „${q}“`
    : `Suche: „${q}“`;

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <Header />
      <main className="mx-auto w-full max-w-[1180px] flex-1 px-4 pb-20 pt-24 sm:px-8 sm:pt-28">
        <nav className="mb-4 text-[13px] font-medium text-muted">
          <Link to="/" className="hover:underline">
            Übersicht
          </Link>
          <span className="mx-1.5 text-muted">›</span>
          <span className="text-ink">Suche</span>
        </nav>

        <h1 className="text-[28px] font-semibold leading-tight text-ink sm:text-[30px]">{heading}</h1>
        {sport && (
          <p className="mt-1 text-[14px] text-muted">
            Sportart: {sportLabel(sport)}
            {week ? ` · KW ${week}` : ""}
          </p>
        )}

        <div className="mt-6">
          {loading && <ResultSkeleton />}
          {error && !loading && (
            <ErrorBanner message={error} onRetry={() => setRetry((n) => n + 1)} />
          )}
          {!loading && !error && result && <SearchHits result={result} />}
          {!loading && !error && bestRegions && (
            <BestRegionsList data={bestRegions} monthName={monthName} meta={regionMeta} />
          )}
          {!loading && !error && bestWeeks && (
            <BestWeeksList data={bestWeeks} place={q} />
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}

function SearchHits({ result }: { result: api.SearchResult }) {
  const empty = result.regionen.length === 0 && result.spots.length === 0;
  if (empty) {
    return (
      <EmptyState message="Keine Treffer. Versuche einen anderen Ort oder Spotnamen." />
    );
  }
  return (
    <div className="space-y-10">
      {result.regionen.length > 0 && (
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-ink">Regionen</h2>
          <ul className="space-y-2">
            {result.regionen.map((r) => (
              <li key={r.id}>
                <Link
                  to={`/region/${r.slug}`}
                  className="flex items-center justify-between rounded-2xl border border-line bg-surface px-4 py-3 transition-colors hover:bg-band/60"
                >
                  <span className="font-medium text-ink">{r.name}</span>
                  <span className="text-[13px] text-muted">Region ›</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.spots.length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="text-[15px] font-semibold text-ink">Spots</h2>
            <span className="text-[12px] text-muted">Skala 0 bis 100 · höher bedeutet besser</span>
          </div>
          <ul className="space-y-2">
            {result.spots.map((s) => (
              <li key={s.id}>
                <Link
                  to={spotPath(s)}
                  className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-4 py-3 transition-colors hover:bg-band/60"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-ink">{s.name}</span>
                    <span className="block truncate text-[12px] text-muted">
                      {s.sports.map(sportLabel).join(", ")}
                    </span>
                  </span>
                  {typeof s.score === "number" && (
                    <span
                      className="shrink-0 text-[12px] text-muted"
                      title="Eignungs-Score für deinen Zeitraum (0–100), höher ist besser"
                    >
                      Score <span className="data-accent">{Math.round(s.score * 100)}</span>
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function BestRegionsList({
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
      <EmptyState message="Noch keine Saisondaten (Klimatologie fehlt für die veröffentlichten Spots)." />
    );
  }
  return (
    <section>
      <p className="mb-5 text-[14px] text-muted">
        Offene Achse <b>wo</b>: die besten Reviere{" "}
        {monthName ? `im ${monthName}` : "über die Saison"} · geordnet nach Abdeckung
        (Anteil der Spots mit fahrbaren Bedingungen).
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
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
                windMonths={(m?.season?.best_months as number[] | undefined) ?? null}
              />
            </div>
          );
        })}
      </div>
    </section>
  );
}

function BestWeeksList({
  data,
  place,
}: {
  data: api.BestWeeksResponse;
  place: string;
}) {
  const weeks = (data.weeks ?? []).filter((w) => (w.score ?? 0) > 0).slice(0, 12);
  if (weeks.length === 0) {
    return (
      <EmptyState message="Noch keine Saisondaten für diesen Ort (Klimatologie fehlt)." />
    );
  }
  const max = Math.max(...weeks.map((w) => w.score ?? 0), 0.01);
  return (
    <section>
      <p className="mb-3 text-[14px] text-muted">
        Offene Achse <b>wann</b>: die besten Wochen für {place || "diesen Ort"} —
        nach nutzbaren Stunden.
      </p>
      <ul className="space-y-2">
        {weeks.map((w) => (
          <li
            key={w.week}
            className="flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3"
          >
            <span className="w-16 shrink-0 font-medium text-ink">KW {w.week}</span>
            <span className="h-2 flex-1 overflow-hidden rounded-full bg-ink/10">
              <span
                className="block h-full rounded-full bg-ink"
                style={{ width: `${Math.round(((w.score ?? 0) / max) * 100)}%` }}
              />
            </span>
            {typeof w.score === "number" && (
              <span
                className="w-24 shrink-0 text-right text-[13px] text-muted"
                title="Anteil der Zeit mit fahrbaren Bedingungen in dieser Woche"
              >
                <span className="data-accent">{Math.round(w.score * 100)}%</span> nutzbar
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
