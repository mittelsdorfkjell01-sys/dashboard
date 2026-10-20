import { useEffect, useRef, useState, type ReactNode } from "react";
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
          <div className="aspect-video animate-pulse rounded-card bg-band" />
          <div className="space-y-2 pt-3">
            <div className="h-3.5 w-2/3 animate-pulse rounded-card bg-band" />
            <div className="h-2 w-1/3 animate-pulse rounded-card bg-band" />
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
  defer = false,
  hideHeader = false,
  onVisibilityChange,
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
  /** Delay network and live-weather work until the row approaches the viewport. */
  defer?: boolean;
  /** Suppress the row's own title/action header (rendered by the parent instead). */
  hideHeader?: boolean;
  /** Keep parent-owned chrome in sync when this category has no usable data. */
  onVisibilityChange?: (visible: boolean) => void;
}) {
  const sectionRef = useRef<HTMLElement | null>(null);
  const [inRange, setInRange] = useState(!defer);

  useEffect(() => {
    if (!defer || inRange) return;
    const section = sectionRef.current;
    if (!section || !("IntersectionObserver" in window)) {
      setInRange(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setInRange(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px 0px" },
    );
    observer.observe(section);
    return () => observer.disconnect();
  }, [defer, inRange]);

  const requestEnabled = !defer || inRange;
  const { data, loading } = useRecommendations({
    sport,
    surface,
    region_id: regionId,
    month,
    weeks,
    limit: MAX_TILES,
    personalized: personalized ? undefined : false,
  }, requestEnabled);
  const spots = (data ?? []).slice(0, MAX_TILES);
  const [loadLive, setLoadLive] = useState(false);

  // A category is useful while it loads or when it has data. Once the request
  // settles without rows, hide the complete category instead of exposing an
  // error/empty panel. Cached rows stay visible if a background refresh fails.
  const visible = loading || spots.length > 0;
  useEffect(() => {
    if (requestEnabled) onVisibilityChange?.(visible);
  }, [onVisibilityChange, requestEnabled, visible]);

  useEffect(() => {
    if (!spots.length) return;
    const timer = window.setTimeout(() => setLoadLive(true), 800);
    return () => window.clearTimeout(timer);
  }, [spots.length]);
  const { data: live } = useSpotsLive(spots.map((spot) => spot.id), requestEnabled && loadLive);

  if (!requestEnabled) {
    return (
      <section ref={sectionRef} className={className} data-recommendation-surface={surface}>
        {!hideHeader && (
          <div className="mb-4 flex min-h-11 items-center justify-between gap-4">
            <h2 className="text-lead font-semibold text-ink">{title}</h2>
            {action}
          </div>
        )}
        <RowSkeleton />
      </section>
    );
  }

  if (!loading && spots.length === 0) return null;

  return (
    <section ref={sectionRef} className={className} data-recommendation-surface={surface}>
      {/* `hideHeader` has to hold here too, not only in the loading and error
          branches: the landing's first row borrows the section heading beside
          the filter icon, so rendering this one as well printed the title
          twice as soon as the data arrived. */}
      {!hideHeader && (
        <div className="mb-4 flex min-h-11 items-center justify-between gap-4">
          <h2 className="text-title font-semibold text-ink">{title}</h2>
          {action}
        </div>
      )}
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
              eager={false}
            />
          ))}
        </div>
      )}
    </section>
  );
}
