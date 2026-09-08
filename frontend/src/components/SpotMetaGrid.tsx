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
    <dl className="grid gap-5 sm:grid-cols-3 sm:gap-6 lg:grid-cols-1 lg:gap-0 lg:divide-y lg:divide-line/70">
      {items.map((item) => {
        const Icon = item.icon;
        return <div key={item.label} className="grid min-w-0 grid-cols-[2rem_minmax(0,1fr)] items-center gap-x-3 sm:block lg:grid lg:grid-cols-[2rem_minmax(0,1fr)_minmax(0,1.15fr)] lg:py-5 first:lg:pt-0">
          <span aria-hidden className="grid h-8 w-8 place-items-center rounded-full bg-band text-ink sm:mb-3 lg:mb-0"><Icon width={16} height={16} /></span>
          <dt className="text-caption font-medium uppercase tracking-[0.08em] text-muted lg:text-label lg:normal-case lg:tracking-normal">
            {item.label}
          </dt>
          <dd className="col-start-2 mt-1 min-w-0 break-words text-ui font-medium leading-snug text-ink sm:col-start-auto lg:mt-0 lg:text-right lg:text-ui">{item.value}</dd>
        </div>;
      })}
    </dl>
  );
}
