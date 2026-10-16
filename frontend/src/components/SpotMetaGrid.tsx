import { Link } from "react-router-dom";
import { bottomTypeLabel, levelLabel, waterTypeLabel } from "../lib/labels";
import type { Spot } from "../lib/types";
import { ChevronRightIcon } from "../lib/icons";
import { spotPath } from "../lib/spotRoutes";
import { formatMonthDayRange } from "../lib/bestSeason";

type Item = { label: string; value: string };

export default function SpotMetaGrid({
  spot,
  bestSeason = null,
}: {
  spot: Spot;
  /** Best travel season (V3 best_season). When present, it leads a raised
   *  highlight panel to the right of Level/Gewässer/Untergrund, with a link to
   *  the Windmonate chart on the Daten tab. */
  bestSeason?: { start_date: string; end_date: string } | null;
}) {
  const items: Item[] = [
    { label: "Level", value: (spot.level ?? []).map(levelLabel).join(", ") },
    { label: "Gewässer", value: (spot.waterTypes ?? []).map(waterTypeLabel).join(", ") },
    { label: "Untergrund", value: (spot.bottomType ?? []).map(bottomTypeLabel).join(", ") },
  ].filter((i) => Boolean(i.value));

  if (items.length === 0 && !bestSeason) return null;

  // Alongside the season highlight the facts read as one quiet left column; on
  // their own they keep their own responsive rhythm (3-up on tablet, stacked
  // on desktop).
  const factsClass = bestSeason
    ? "grid content-start gap-5 lg:gap-6"
    : "grid gap-5 sm:grid-cols-3 sm:gap-6 lg:grid-cols-1 lg:gap-7";

  const facts = (
    <dl className={factsClass}>
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-caption font-medium uppercase tracking-caps text-muted">{item.label}</dt>
          <dd className="mt-1 min-w-0 break-words text-ui font-medium leading-snug text-ink lg:text-body">{item.value}</dd>
        </div>
      ))}
    </dl>
  );

  if (!bestSeason) return facts;

  return (
    // Facts (plain, editorial) left; the season as the one raised highlight
    // right. `items-stretch` lets the panel match the facts' height so the
    // region reads as a balanced block, with the link pinned to its base.
    <div className="grid grid-cols-[1fr_1.05fr] items-stretch gap-x-3 sm:gap-x-5">
      {facts}
      <div className="flex min-w-0 flex-col rounded-card p-3.5 sm:p-4">
        <p className="text-caption font-medium uppercase tracking-caps text-muted">Beste Reisezeit</p>
        <p className="mt-2 break-words text-lead font-semibold leading-[1.15] text-ink sm:text-lead">
          {formatMonthDayRange(bestSeason.start_date, bestSeason.end_date)}
        </p>
        <p className="mt-1.5 text-caption leading-snug text-muted">Verlässlichste Windzeit im Jahr</p>
        <Link
          to={`${spotPath(spot, "daten")}#windmonate`}
          className="mt-auto flex w-fit items-center gap-0.5 pt-4 text-ui font-medium text-accent transition-opacity hover:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Windmonate <ChevronRightIcon width={14} height={14} />
        </Link>
      </div>
    </div>
  );
}
