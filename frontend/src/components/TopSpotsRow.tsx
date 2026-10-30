import { useEffect, useState } from "react";
import { useTopSpots, useSpotsLive } from "../lib/hooks";
import SpotCard from "./SpotCard";

// One full-width row on desktop; tiles wrap on smaller screens.
const GRID =
  "grid auto-rows-fr grid-cols-2 gap-x-8 gap-y-10 px-4 sm:grid-cols-3 sm:px-10 lg:grid-cols-5";
const MAX_TILES = 5;

function RowSkeleton() {
  return (
    <div className={GRID}>
      {Array.from({ length: MAX_TILES }).map((_, i) => (
        <div key={i}>
          <div className="aspect-video animate-pulse rounded-card bg-band" />
          <div className="space-y-2 pt-3">
            <div className="h-2 w-1/3 animate-pulse rounded-card bg-band" />
            <div className="h-3.5 w-2/3 animate-pulse rounded-card bg-band" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * A responsive catalogue selection. `/spots/top` only switches to forecast
 * ordering after a scope-specific decision-support gate passes; otherwise it
 * uses reviewed editorial relevance and stable name order. Fills the row's full width (no horizontal scroll,
 * so no tile is ever clipped), capped at MAX_TILES so the desktop row stays a
 * single clean line. A small, bounded row — cheap to also fetch live
 * conditions for (see SpotCard's `live` prop).
 */
export default function TopSpotsRow() {
  const { data: spots, loading, error } = useTopSpots(MAX_TILES);
  const top = (spots ?? []).slice(0, MAX_TILES);
  const [loadLive, setLoadLive] = useState(false);
  useEffect(() => {
    if (!top.length) return;
    const win = window as Window & {
      requestIdleCallback?: (cb: () => void, options?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (win.requestIdleCallback) {
      const id = win.requestIdleCallback(() => setLoadLive(true), { timeout: 2500 });
      return () => win.cancelIdleCallback?.(id);
    }
    const id = window.setTimeout(() => setLoadLive(true), 1200);
    return () => window.clearTimeout(id);
  }, [top.length]);
  const { data: live } = useSpotsLive(top.map((s) => s.id), loadLive);

  if (loading) return <RowSkeleton />;
  if (error) return null;
  if (top.length === 0) return null;

  return (
    <div className={GRID}>
      {top.map((spot) => (
        <div key={spot.id}>
          <SpotCard spot={spot} live={live?.get(spot.id)} surface="now" />
        </div>
      ))}
    </div>
  );
}
