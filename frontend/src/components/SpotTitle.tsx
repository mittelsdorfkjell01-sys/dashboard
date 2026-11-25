import { Link } from "react-router-dom";
import { regionSlug, type Spot } from "../lib/types";
import SpotOriginMark from "./SpotOriginMark";

/**
 * The spot's name with region and country beside it, on the same baseline
 * (chosen again 2026-11-25, "Wie heute"). One component for the Info and the
 * Daten tab, so both show the identical line. Region and country read as the
 * rest of the spot's address; on a narrow column they wrap to their own line
 * instead of squeezing the name. The origin mark trails the name.
 * One step smaller since 2026-11-25 (title/heading, was heading/heading-lg),
 * so the Daten tab's Wind/Welle switch fits on the same line.
 */
export default function SpotTitle({ spot }: { spot: Pick<Spot, "name" | "region" | "origin"> }) {
  const [regionPart, country] = spot.region.split(",").map((part) => part.trim());
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <h1 className="text-title font-semibold text-balance text-ink sm:text-heading">
        {spot.name}
        <SpotOriginMark origin={spot.origin} className="ml-2 align-baseline" />
      </h1>
      {(regionPart || country) && (
        <p className="text-caption leading-tight text-ink-soft/80 sm:text-ui">
          {regionPart && (
            <Link
              to={`/region/${regionSlug(spot.region)}`}
              className="whitespace-nowrap font-medium text-ink transition-opacity hover:opacity-70 hover:underline"
            >
              {regionPart}
            </Link>
          )}
          {country && regionPart && <span className="mx-1.5 text-ink-soft/50">·</span>}
          {country && <span className="whitespace-nowrap">{country}</span>}
        </p>
      )}
    </div>
  );
}
