import { bottomTypeLabel, levelLabel, waterTypeLabel } from "../lib/labels";
import type { Spot } from "../lib/types";

type Item = { label: string; value: string };

export default function SpotMetaGrid({ spot }: { spot: Spot }) {
  const items: Item[] = [
    { label: "Level", value: (spot.level ?? []).map(levelLabel).join(", ") },
    { label: "Gewässer", value: (spot.waterTypes ?? []).map(waterTypeLabel).join(", ") },
    { label: "Untergrund", value: (spot.bottomType ?? []).map(bottomTypeLabel).join(", ") },
  ].filter((i) => Boolean(i.value));

  if (items.length === 0) return null;

  return (
    <dl className="grid grid-cols-3 gap-x-4 border-y border-line py-5 lg:grid-cols-1 lg:gap-7 lg:border-0 lg:py-0">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-caption font-medium uppercase tracking-[0.08em] text-muted">
            {item.label}
          </dt>
          <dd className="mt-1.5 text-ui font-medium leading-snug text-ink lg:mt-2 lg:text-body">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
