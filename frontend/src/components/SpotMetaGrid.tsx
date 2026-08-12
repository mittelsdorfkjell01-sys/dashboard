import { bottomTypeLabel, levelLabel, waterTypeLabel } from "../lib/labels";
import type { Spot } from "../lib/types";
import { InfoIcon, MapIcon, PinIcon } from "../lib/icons";

type Item = { label: string; value: string; icon: typeof InfoIcon };

export default function SpotMetaGrid({ spot }: { spot: Spot }) {
  const items: Item[] = [
    { label: "Level", value: (spot.level ?? []).map(levelLabel).join(", "), icon: InfoIcon },
    { label: "Gewässer", value: (spot.waterTypes ?? []).map(waterTypeLabel).join(", "), icon: MapIcon },
    { label: "Untergrund", value: (spot.bottomType ?? []).map(bottomTypeLabel).join(", "), icon: PinIcon },
  ].filter((i) => Boolean(i.value));

  if (items.length === 0) return null;

  return (
    <dl className="grid gap-5 sm:grid-cols-3 sm:gap-6 lg:grid-cols-1 lg:gap-7">
      {items.map((item) => {
        const Icon = item.icon;
        return <div key={item.label} className="grid min-w-0 grid-cols-[2rem_minmax(0,1fr)] gap-x-3 sm:block lg:grid lg:grid-cols-[2rem_minmax(0,1fr)]">
          <span aria-hidden className="row-span-2 grid h-8 w-8 place-items-center rounded-full bg-band text-teal sm:mb-3 lg:mb-0"><Icon width={16} height={16} /></span>
          <dt className="text-caption font-medium uppercase tracking-[0.08em] text-muted">
            {item.label}
          </dt>
          <dd className="mt-1 min-w-0 break-words text-ui font-medium leading-snug text-ink lg:text-body">{item.value}</dd>
        </div>;
      })}
    </dl>
  );
}
