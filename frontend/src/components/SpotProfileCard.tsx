import { Link } from "react-router-dom";
import Facilities from "./Facilities";
import { bottomTypeLabel, levelLabel, waterTypeLabel, windDirectionLabel } from "../lib/labels";
import type { Facility, Spot } from "../lib/types";
import { ChevronRightIcon } from "../lib/icons";
import { spotPath } from "../lib/spotRoutes";
import { formatMonthDayRange } from "../lib/bestSeason";

type Item = { label: string; value: string };

/**
 * The Info tab's spec card — the single object that sits beside the community
 * gallery and runs its full height.
 *
 * It reads top to bottom as one sheet, in three bands separated by hairlines:
 *   1. the best travel season as the card's head (the one raised fact, with
 *      the link into the Windmonate chart),
 *   2. the spot profile (Level / Gewässer / Untergrund / Beste Windrichtung)
 *      as label-left / value-right rows,
 *   3. the facilities as the card's foot, on the quieter band surface.
 *
 * The profile rows share the card's spare vertical space (`flex-1` per row),
 * so the card fills the gallery height without inventing content or leaving a
 * void. Everything missing simply disappears — no placeholder rows.
 */
export default function SpotProfileCard({
  spot,
  bestSeason = null,
  facilities = [],
  className = "",
}: {
  spot: Spot;
  bestSeason?: { start_date: string; end_date: string } | null;
  facilities?: Facility[];
  className?: string;
}) {
  const items: Item[] = [
    { label: "Level", value: (spot.level ?? []).map(levelLabel).join(", ") },
    { label: "Gewässer", value: (spot.waterTypes ?? []).map(waterTypeLabel).join(", ") },
    { label: "Untergrund", value: (spot.bottomType ?? []).map(bottomTypeLabel).join(", ") },
    {
      label: "Beste Windrichtung",
      value: (spot.bestWindDirections ?? []).map(windDirectionLabel).join(", "),
    },
  ].filter((i) => Boolean(i.value));

  if (items.length === 0 && !bestSeason && facilities.length === 0) return null;

  return (
    <div
      className={`flex min-w-0 flex-col overflow-hidden rounded-card border border-line bg-surface ${className}`}
    >
      {bestSeason && (
        <div className="border-b border-line px-4 py-4 sm:px-5">
          <p className="text-caption font-medium uppercase tracking-caps text-muted">Beste Reisezeit</p>
          <p className="mt-1.5 break-words text-lead font-semibold leading-[1.15] text-ink">
            {formatMonthDayRange(bestSeason.start_date, bestSeason.end_date)}
          </p>
          <p className="mt-1 text-caption leading-snug text-muted">Verlässlichste Windzeit im Jahr</p>
          <Link
            to={`${spotPath(spot, "daten")}#windmonate`}
            className="mt-2 inline-flex items-center gap-0.5 text-caption font-medium text-accent transition-opacity hover:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Windmonate <ChevronRightIcon width={14} height={14} />
          </Link>
        </div>
      )}

      {items.length > 0 && (
        <dl className="flex flex-1 flex-col divide-y divide-line px-4 sm:px-5">
          {items.map((item) => (
            <div
              key={item.label}
              className="flex flex-1 min-w-0 items-center justify-between gap-4 py-3"
            >
              <dt className="shrink-0 text-caption font-medium uppercase tracking-caps text-muted">
                {item.label}
              </dt>
              <dd className="min-w-0 break-words text-right text-caption font-medium leading-snug text-ink">
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {facilities.length > 0 && (
        <div className="border-t border-line bg-band px-4 py-3.5 sm:px-5">
          <h2 className="text-caption font-medium uppercase tracking-caps text-muted">Ausstattung</h2>
          <div className="mt-1">
            <Facilities items={facilities} variant="table" />
          </div>
        </div>
      )}
    </div>
  );
}
