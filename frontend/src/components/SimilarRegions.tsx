import { Link } from "react-router-dom";
import type { RegionInfo, Spot } from "../lib/types";
import { WindBadge } from "./SpotBits";
import SpotImage from "./SpotImage";
import { useRegions, useSpots } from "../lib/hooks";

/**
 * "Ähnliche Regionen" — reviers that resemble the current one, drawn from the
 * live catalogue (no mock data / picsum). Placeholder ranking: same country
 * first, then closest mean wind; the real similarity comes from the backend in a
 * later step. A region card = the lead spot's image (or a branded fallback),
 * country, name, spot count and the region's mean wind.
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
        <h2 className="text-[20px] font-semibold text-ink sm:text-[24px]">Ähnliche Regionen</h2>
        <p className="mt-1 text-[14px] text-muted">
          Vergleichbare Reviere nach Charakter und Windstärke
        </p>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-9 md:grid-cols-4">
        {ranked.map(({ r, list }) => (
          <Link key={r.slug} to={`/region/${r.slug}`} className="group block">
            <div className="relative aspect-[16/11] overflow-hidden rounded-2xl bg-line">
              <SpotImage
                src={list[0]?.image}
                name={r.name}
                region={r.country ?? undefined}
                className="transition-transform duration-500 group-hover:scale-[1.03] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
              />
            </div>
            <div className="mt-3">
              <div className="flex items-baseline justify-between gap-3">
                <p className="truncate text-[12px] text-muted">{r.country}</p>
                <WindBadge value={meanWind(list)} />
              </div>
              <h3 className="mt-1 text-lg font-semibold leading-tight text-ink">{r.name}</h3>
              <p className="mt-1 text-[12px] text-muted">
                {list.length} {list.length === 1 ? "Spot" : "Spots"}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
