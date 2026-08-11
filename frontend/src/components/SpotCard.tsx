import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";
import { sportLabel } from "../lib/labels";
import SpotImage from "./SpotImage";

/**
 * The one spot-tile layout used everywhere a spot is browsed: landing grid,
 * top-spots row, region grid, similar-spots, and (via `compact`) the map
 * popup/strip. No shadow — separation is the hairline `border-line` only,
 * matching the rest of the app (see tailwind.config.js's borderRadius note).
 *
 * `spot.wind` is a typical/editorial value, never a live reading (see
 * `lib/adapt.ts`), so the wind figure is always shown as a plain static
 * reading — no pulse, no "jetzt". A live indicator would need a real signal
 * from the API that none of these call sites currently have.
 *
 * `compact` is the map popup/strip treatment: image + name/wind row only —
 * no room there for region, description or the footer action.
 */
export default function SpotCard({
  spot,
  compact = false,
}: {
  spot: Spot;
  compact?: boolean;
}) {
  const id = spot.uuid ?? spot.id;
  const known = typeof spot.wind === "number" && spot.wind > 0;
  const sports = (spot.sports ?? []).map(sportLabel).join(" · ");

  return (
    <Link
      to={`/spot/${id}`}
      className="group flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-surface"
    >
      <div className="relative aspect-video overflow-hidden">
        <SpotImage src={spot.image} name={spot.name} region={spot.region} compact />
      </div>

      <div className={`flex flex-1 flex-col ${compact ? "p-2.5" : "p-3.5"}`}>
        <div className="flex items-baseline justify-between gap-3">
          <p
            className={`min-w-0 truncate font-semibold text-ink ${compact ? "text-label" : "text-body"}`}
          >
            {spot.name}
          </p>
          <div className="flex shrink-0 items-baseline gap-1 whitespace-nowrap">
            <span className="inline-block h-1.5 w-1.5 translate-y-[-1px] rounded-full bg-orange" />
            <span className="text-label font-semibold text-ink">{known ? spot.wind : "—"}</span>
            <span className="text-caption text-ink-soft">kts</span>
          </div>
        </div>

        {!compact && (
          <>
            {spot.region && (
              <p className="mt-0.5 truncate text-caption text-muted">{spot.region}</p>
            )}

            {spot.description && (
              <p className="mt-2 line-clamp-2 text-caption text-ink-soft">{spot.description}</p>
            )}

            <div className="mt-auto flex items-center gap-3 pt-3">
              {sports && <span className="min-w-0 truncate text-caption text-muted">{sports}</span>}
              <span className="ml-auto shrink-0 rounded-2xl bg-teal px-3.5 py-2 text-label font-semibold text-white transition-colors group-hover:bg-teal-hover">
                Spot öffnen
              </span>
            </div>
          </>
        )}
      </div>
    </Link>
  );
}
