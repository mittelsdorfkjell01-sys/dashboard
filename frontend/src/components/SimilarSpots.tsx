import SpotCard from "./SpotCard";
import type { Spot } from "../lib/types";
import { useSpots } from "../lib/hooks";

/**
 * "Ähnliche Spots" — spots that resemble the current one, drawn from the live
 * catalogue (no mock data / picsum). Placeholder ranking: same region first,
 * then closest wind strength; the real similarity ranking comes from the backend
 * similarity endpoints in a later step. Reuses the landing SpotCard. Headless:
 * the section heading lives in the caller's `SectionBand`.
 *
 * Three entries, not four — and the first is visually bigger (spans a 2x2
 * grid area, the other two stack beside it). Equal-size tiles would claim
 * there's no ranking; there is one, even if it's a placeholder for now.
 */
export default function SimilarSpots({ spot, limit = 3 }: { spot: Spot; limit?: number }) {
  const { data: all } = useSpots({ status: "published" });
  const others = (all ?? []).filter((s) => s.id !== spot.id);
  const sameRegion = spot.region.split(",")[0].trim();

  const ranked = others
    .map((s) => ({
      s,
      score:
        (s.region.split(",")[0].trim() === sameRegion ? 0 : 100) +
        Math.abs(s.wind - spot.wind),
    }))
    .sort((a, b) => a.score - b.score)
    .slice(0, limit)
    .map((x) => x.s);

  if (ranked.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-x-7 gap-y-8 sm:grid-cols-3 sm:grid-rows-2">
      {ranked.map((s, i) => (
        <div key={s.id} className={i === 0 ? "sm:col-span-2 sm:row-span-2" : ""}>
          <SpotCard spot={s} variant="editorial" />
        </div>
      ))}
    </div>
  );
}
