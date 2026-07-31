import { useTopSpots } from "../lib/hooks";
import SpotTile from "./SpotTile";
import { ErrorBanner } from "./AsyncStates";

// One full-width row on desktop; tiles wrap on smaller screens.
const GRID = "grid grid-cols-2 gap-3 px-4 sm:grid-cols-3 sm:px-10 lg:grid-cols-5";
const MAX_TILES = 5;

function RowSkeleton() {
  return (
    <div className={GRID}>
      {Array.from({ length: MAX_TILES }).map((_, i) => (
        <div
          key={i}
          className="overflow-hidden rounded-3xl border border-line bg-white shadow-card"
        >
          <div className="aspect-[4/3] animate-pulse bg-line" />
          <div className="space-y-2 p-3.5">
            <div className="h-2 w-1/3 animate-pulse rounded bg-line" />
            <div className="h-3.5 w-2/3 animate-pulse rounded bg-line" />
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
 * single clean line. No live conditions on the landing tiles.
 */
export default function TopSpotsRow() {
  const { data: spots, loading, error, reload } = useTopSpots(MAX_TILES);
  const top = (spots ?? []).slice(0, MAX_TILES);

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
          <SpotTile spot={spot} />
        </div>
      ))}
    </div>
  );
}
