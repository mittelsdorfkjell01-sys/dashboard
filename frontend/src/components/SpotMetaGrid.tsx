import { levelLabel, waterCharacterLabel } from "../lib/labels";
import type { Spot } from "../lib/types";

type Item = { label: string; value: string };

export default function SpotMetaGrid({ spot }: { spot: Spot }) {
  const items: Item[] = [
    { label: "Level", value: levelLabel(spot.level) },
    { label: "Gewässer", value: waterCharacterLabel(spot.waterCharacter) },
    // TODO(redesign): add Untergrund (spot.bottomType) and Wind-Typ (spot.editorial?.windType)
    // once water_type / bottom_type / editorial.wind_type are mapped in adapt.ts → Spot
  ].filter((i) => Boolean(i.value));

  if (items.length === 0) return null;

  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
      {items.map((item) => (
        <div key={item.label}>
          <dt className="text-caption text-muted tracking-wider uppercase mb-1">
            {item.label}
          </dt>
          <dd className="text-ui text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
