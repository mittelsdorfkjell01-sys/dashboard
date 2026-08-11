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
    <dl className="grid gap-7">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-caption font-medium uppercase tracking-[0.08em] text-muted">
            {item.label}
          </dt>
          <dd className="mt-2 text-body font-medium leading-snug text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
