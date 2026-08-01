import { Link } from "react-router-dom";
import SpotImage from "./SpotImage";
import { sportLabel } from "../lib/labels";
import type { Spot } from "../lib/types";

/**
 * Top-spot card: image on top, a clean white info area below (region kicker,
 * name, sport pills) — image and information are separated rather than
 * overlaid. No favourites/hearts and no live conditions on the landing page.
 */
export default function SpotTile({ spot }: { spot: Spot }) {
  const id = spot.uuid ?? spot.id;
  const tags = (spot.sports ?? []).slice(0, 3).map(sportLabel);

  return (
    <Link
      to={`/spot/${id}`}
      className="flex h-full flex-col overflow-hidden rounded-3xl border border-line bg-white"
    >
      {/* 16:9 image, fixed width by the grid cell — no hover zoom. */}
      <div className="relative aspect-video overflow-hidden">
        <SpotImage src={spot.image} name={spot.name} region={spot.region} compact />
      </div>

      <div className="flex flex-1 flex-col p-3.5">
        <p className="truncate text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
          {spot.region}
        </p>
        <p className="mt-0.5 truncate text-[15px] font-semibold leading-tight text-ink">
          {spot.name}
        </p>
        {tags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <span
                key={t}
                className="rounded-full bg-band px-2 py-0.5 text-[11px] font-medium text-ink-soft"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}
