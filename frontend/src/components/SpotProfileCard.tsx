import { Link } from "react-router-dom";
import Facilities from "./Facilities";
import { bottomTypeLabel, levelLabel, waterTypeLabel, windDirectionLabel } from "../lib/labels";
import type { Facility, Spot } from "../lib/types";
import { ChevronRightIcon } from "../lib/icons";
import { spotPath } from "../lib/spotRoutes";
import { formatMonthDayRange } from "../lib/bestSeason";

type Item = { label: string; value: string };

/**
 * The Info tab's spec column, beside the community gallery.
 *
 * Not one sheet any more: the specs are separate cards, each a label and its
 * value, so a missing fact leaves no empty row in a shared table and each one
 * can be read on its own. They sit top-aligned in the upper half of the
 * column; the facilities card takes the lower half. The halves are `flex-1`
 * against the gallery height the page passes down, so the split lands on the
 * gallery's midpoint at any gallery size instead of a guessed pixel value.
 *
 * "Beste Reisezeit" keeps its own card above the specs when the spot has a
 * climatology for it — it is a different kind of statement (a derived window,
 * with a link into the chart), not another label/value pair.
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
    <div className={`flex min-w-0 flex-col gap-4 ${className}`}>
      {/* Upper half: the separate spec cards, aligned to the top. */}
      <div className="flex min-w-0 flex-col gap-2.5 lg:flex-1">
        {bestSeason && (
          <div className="min-w-0">
            <p className="text-caption font-medium uppercase tracking-caps text-muted">
              Beste Reisezeit
            </p>
            <p className="mt-1.5 break-words text-lead font-semibold leading-[1.15] text-ink">
              {formatMonthDayRange(bestSeason.start_date, bestSeason.end_date)}
            </p>
            <p className="mt-1 text-caption leading-snug text-muted">
              Verlässlichste Windzeit im Jahr
            </p>
            <Link
              to={`${spotPath(spot, "daten")}#windmonate`}
              className="mt-2 inline-flex items-center gap-0.5 text-caption font-medium text-accent transition-opacity hover:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Windmonate <ChevronRightIcon width={14} height={14} />
            </Link>
          </div>
        )}

        {/* Phones put the four facts side by side as one band of tiles, label
            over value: on a narrow screen the column is the whole page width,
            and four full-width rows cost four scroll-lengths for twelve words.

            Stroke only, never a fill (DESIGN.md, The No Tile Background Rule):
            the outline is what separates four equal values standing next to
            each other, and that is the whole job it has.

            Two per row, two rows. Four across fit the width but not the
            words: a 390px phone left about 67px of text per tile, and no
            readable size fits "Fortgeschritten" in that, so every long value
            broke into syllables. At two per row each value has room to stand
            on one line. The type sits on the 10px rung, the label drops its
            letter-spacing, and both still hyphenate (`lang="de"` is set on the
            document) if a value does outrun the tile. From `lg` the column is
            a column again: label left, value right, full type size. */}
        <div className="grid grid-cols-2 gap-1.5 lg:flex lg:flex-col lg:gap-2">
          {items.map((item) => (
            <dl
              key={item.label}
              className="flex min-w-0 flex-col rounded-card border border-line px-2 py-2 lg:flex-row lg:items-center lg:justify-between lg:gap-4 lg:px-3.5 lg:py-2.5"
            >
              <dt className="hyphens-auto break-words text-micro font-medium uppercase leading-tight text-muted lg:shrink-0 lg:hyphens-none lg:text-caption lg:tracking-caps">
                {item.label}
              </dt>
              <dd className="mt-0.5 min-w-0 hyphens-auto break-words text-micro font-normal leading-snug text-ink lg:mt-0 lg:text-right lg:text-caption">
                {item.value}
              </dd>
            </dl>
          ))}
        </div>
      </div>

      {/* Lower half: facilities. No frame, no fill, no rules between the rows
          — a heading and a list, standing on the page like the rest of the
          column (DESIGN.md, The No Tile Background Rule / The Earned Line
          Rule). Six amenities of the same kind need spacing to be read as a
          list, not a grid drawn around them. */}
      {facilities.length > 0 && (
        <div className="min-w-0 lg:flex-1">
          <h2 className="text-caption font-medium uppercase tracking-caps text-muted">
            Ausstattung
          </h2>
          <div className="mt-2">
            <Facilities items={facilities} variant="table" />
          </div>
        </div>
      )}
    </div>
  );
}
