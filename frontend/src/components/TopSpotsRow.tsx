import { useTopSpots, useSpotsLive } from "../lib/hooks";
import SpotCard from "./SpotCard";
import { ErrorBanner } from "./AsyncStates";

// One full-width row on desktop; tiles wrap on smaller screens.
const GRID =
  "grid auto-rows-fr grid-cols-2 gap-x-5 gap-y-8 px-4 sm:grid-cols-3 sm:px-10 lg:grid-cols-5";
const MAX_TILES = 5;

function RowSkeleton() {
  return (
    <div className={GRID}>
      {Array.from({ length: MAX_TILES }).map((_, i) => (
        <div key={i}>
          <div className="aspect-video animate-pulse rounded-2xl bg-band" />
          <div className="space-y-2 pt-3">
            <div className="h-2 w-1/3 animate-pulse rounded bg-band" />
            <div className="h-3.5 w-2/3 animate-pulse rounded bg-band" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * "aktuelle Top Spots" — a responsive grid of the highest-ranked published
 * spots (backend `/spots/top`: this week's wind forecast + today's conditions +
 * popularity, rotating daily). Fills the row's full width (no horizontal scroll,
 * so no tile is ever clipped), capped at MAX_TILES so the desktop row stays a
 * single clean line. A small, bounded row — cheap to also fetch live
 * conditions for (see SpotCard's `live` prop).
 */
export default function TopSpotsRow() {
  const { data: spots, loading, error, reload } = useTopSpots(MAX_TILES);
  const top = (spots ?? []).slice(0, MAX_TILES);
  const { data: live } = useSpotsLive(top.map((s) => s.id));

  if (loading) return <RowSkeleton />;
  if (error)
    return (
      <div className="px-4 sm:px-10">
        <ErrorBanner message={error} onRetry={reload} />
      </div>
    );
  if (top.length === 0) return null;

  return (
    <div className={GRID}>
      {top.map((spot, i) => (
        <div
          key={spot.id}
          className="animate-fade-up"
          style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
        >
          <SpotCard spot={spot} live={live?.get(spot.id)} />
        </div>
      ))}
    </div>
  );
}
