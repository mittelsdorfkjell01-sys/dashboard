import type { RegionInfo, Spot } from "../lib/types";
import RegionTile from "./RegionTile";
import { useRegions, useSpots } from "../lib/hooks";

/**
 * "Ähnliche Regionen" — reviers that resemble the current one, drawn from the
 * live catalogue (no mock data / picsum). Placeholder ranking: same country
 * first, then closest mean wind; the real similarity comes from the backend in a
 * later step. Renders through the shared RegionTile so this reads as the same
 * card as search results — the region's own image is preferred, falling back
 * to a lead spot's image only when the region has none.
 */
export default function SimilarRegions({
  region,
  limit = 4,
}: {
  region: RegionInfo;
  limit?: number;
}) {
  const { data: regions } = useRegions();
  const { data: spots } = useSpots();
  if (!regions || !spots) return null;

  const byRegion = new Map<string, Spot[]>();
  for (const s of spots) {
    if (!s.regionId) continue;
    const list = byRegion.get(s.regionId) ?? byRegion.set(s.regionId, []).get(s.regionId)!;
    list.push(s);
  }
  const meanWind = (list: Spot[]) =>
    list.length ? Math.round(list.reduce((a, s) => a + s.wind, 0) / list.length) : 0;

  const currentMean = meanWind(region.spots);

  const ranked = regions
    .filter((r) => r.slug !== region.slug)
    .map((r) => {
      const list = byRegion.get(r.id) ?? [];
      return {
        r,
        list,
        score:
          (r.country === region.country ? 0 : 100) +
          Math.abs(meanWind(list) - currentMean),
      };
    })
    .sort((a, b) => a.score - b.score)
    .slice(0, limit);

  if (ranked.length === 0) return null;

  return (
    <section>
      <div className="mb-6 border-b border-line/70 pb-4">
        <h2 className="text-sz-20 font-semibold text-ink sm:text-sz-24">Ähnliche Regionen</h2>
        <p className="mt-1 text-ui text-muted">
          Vergleichbare Reviere nach Charakter und Windstärke
        </p>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-9 md:grid-cols-4">
        {ranked.map(({ r, list }) => (
          <RegionTile
            key={r.slug}
            slug={r.slug}
            name={r.name}
            country={r.country}
            image={r.image ?? (list[0]?.image ? {
              url: list[0].image,
              width: list[0].heroWidth,
              focal: list[0].heroFocal ?? undefined,
              focal_mobile: list[0].heroFocalMobile,
              rotation: list[0].heroRotation,
            } : undefined)}
            spotCount={r.spot_count}
            sports={r.sports}
          />
        ))}
      </div>
    </section>
  );
}
