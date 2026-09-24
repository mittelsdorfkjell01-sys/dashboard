import { useEffect, useState, type ReactNode } from "react";
import { useRecommendations, useSpotsLive } from "../lib/hooks";
import type { RecommendationSurface } from "../lib/api";
import SpotCard from "./SpotCard";

const GRID =
  "grid auto-rows-fr grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-3 sm:gap-x-8 sm:gap-y-10 lg:grid-cols-5";
const MAX_TILES = 5;

function RowSkeleton() {
  return (
    <div className={GRID} aria-hidden>
      {Array.from({ length: MAX_TILES }).map((_, index) => (
        <div key={index}>
          <div className="aspect-video animate-pulse rounded-[14px] bg-band" />
          <div className="space-y-2 pt-3">
            <div className="h-3.5 w-2/3 animate-pulse rounded bg-band" />
            <div className="h-2 w-1/3 animate-pulse rounded bg-band" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function RecommendationRow({
  title,
  surface,
  sport = "kitesurf",
  personalized = true,
  regionId,
  month,
  weeks,
  action,
  className = "",
}: {
  title: string;
  surface: RecommendationSurface;
  /** Personalized only for kitesurf today; other sports fall back to the
   *  existing per-sport scoring once the backend surfaces support them. */
  sport?: string;
  /** False ranks like a logged-out visitor (ignore the rider's profile). */
  personalized?: boolean;
  regionId?: string;
  month?: number;
  weeks?: string;
  action?: ReactNode;
  className?: string;
}) {
  const { data, loading, error } = useRecommendations({
    sport,
    surface,
    region_id: regionId,
    month,
    weeks,
    limit: MAX_TILES,
    personalized: personalized ? undefined : false,
  });
  const spots = (data ?? []).slice(0, MAX_TILES);
  const [loadLive, setLoadLive] = useState(false);

  useEffect(() => {
    if (!spots.length) return;
    const timer = window.setTimeout(() => setLoadLive(true), 800);
    return () => window.clearTimeout(timer);
  }, [spots.length]);
  const { data: live } = useSpotsLive(spots.map((spot) => spot.id), loadLive);

  useEffect(() => {
    if (error) console.error(`Recommendation surface ${surface} failed`, error);
  }, [error, surface]);

  if (!loading && (error || spots.length === 0)) return null;

  return (
    <section className={className} data-recommendation-surface={surface}>
      <div className="mb-4 flex min-h-11 items-center justify-between gap-4">
        <h2 className="text-sz-22 font-semibold text-ink">{title}</h2>
        {action}
      </div>
      {loading ? (
        <RowSkeleton />
      ) : (
        <div className={GRID}>
          {spots.map((spot) => (
            <SpotCard
              key={spot.id}
              spot={spot}
              live={live?.get(spot.id)}
              surface={surface}
            />
          ))}
        </div>
      )}
    </section>
  );
}
