import { Link } from "react-router-dom";
import SpotImage from "./SpotImage";
import { sportLabel } from "../lib/labels";
import type { Spot } from "../lib/types";

/**
 * Glass-overlay top-spot tile. Image with a bottom caption panel (region, name,
 * sports). No favourites/hearts and no live conditions on the landing page —
 * those live on the spot detail page.
 */
export default function SpotTile({ spot }: { spot: Spot }) {
  const id = spot.uuid ?? spot.id;
  const tags = (spot.sports ?? []).slice(0, 4).map(sportLabel);

  return (
    <Link
      to={`/spot/${id}`}
      className="group relative block h-[190px] w-full overflow-hidden rounded-3xl"
    >
      <div className="absolute inset-0">
        <SpotImage
          src={spot.image}
          name={spot.name}
          region={spot.region}
          compact
          className="transition-transform duration-500 group-hover:scale-105"
        />
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/10 to-transparent" />

      {/* bottom glass panel */}
      <div className="glass absolute inset-x-0 bottom-0 p-3.5 text-white">
        <p className="truncate text-[10px] font-medium text-white/90">{spot.region}</p>
        <p className="mt-0.5 min-w-0 truncate text-[15px] font-semibold">{spot.name}</p>
        {tags.length > 0 && (
          <p className="mt-1.5 flex flex-nowrap gap-x-2 overflow-hidden text-[10px] text-white/90">
            {tags.map((t) => (
              <span key={t} className="whitespace-nowrap">{t}</span>
            ))}
          </p>
        )}
      </div>
    </Link>
  );
}
