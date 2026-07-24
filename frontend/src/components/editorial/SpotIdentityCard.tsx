import type { LiveConditionsRead } from "../../lib/api";
import { degToCompass } from "../WindRose";
import WindArrow from "../WindArrow";
import { formatCoords, mapLinkProps } from "../../lib/mapLinks";

/**
 * The page's single <h1> (spot name) plus location, coordinates, and the
 * current live wind — floating over the hero's bottom edge (replaces the old
 * `ConditionsBand variant="card"` at this position). Live-wind is omitted
 * entirely (not shown as an empty row) when `live` has no reading.
 *
 * The region name itself is *not* repeated here — it already floats on the
 * hero image as a live link. Showing it again as a second, separately-linked
 * breadcrumb would just duplicate that navigation; this is plain descriptive
 * "Ort, Land" text instead.
 */
export default function SpotIdentityCard({
  name,
  regionName,
  country,
  coords,
  live,
}: {
  name: string;
  regionName?: string;
  country?: string;
  coords?: [number, number];
  live: LiveConditionsRead | null;
}) {
  const wind = live?.current.wind;
  const dir = live?.current.dir;
  const location = [regionName, country].filter(Boolean).join(", ");

  return (
    <div className="relative z-20 -mt-16 max-w-[1180px] rounded-3xl bg-white/95 px-6 py-7 shadow-float backdrop-blur-xl sm:-mt-20 sm:px-10 sm:py-8">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0">
          {location && <p className="text-label text-muted">{location}</p>}

          <h1 className="mt-1 text-display-2 font-semibold text-balance text-ink">{name}</h1>

          {coords && (
            <a
              {...mapLinkProps(coords[0], coords[1])}
              className="mt-2 inline-block text-caption tabular-nums text-teal transition-colors hover:text-teal-hover hover:underline"
            >
              {formatCoords(coords[0], coords[1])}
            </a>
          )}
        </div>

        {typeof wind === "number" && (
          <div className="flex shrink-0 items-center gap-2">
            <span className="inline-block h-2 w-2 shrink-0 animate-[pulse_2.4s_ease-in-out_infinite] rounded-full bg-orange" />
            <span className="flex items-baseline gap-1">
              <span className="text-stat font-semibold leading-none tabular-nums text-ink">
                {Math.round(wind)}
              </span>
              <span className="text-body text-muted">kts</span>
            </span>
            {typeof dir === "number" && (
              <span className="flex flex-col items-center gap-1 pb-1">
                <WindArrow dir={dir} size={22} className="text-ink" />
                <span className="text-caption font-medium text-ink-soft">{degToCompass(dir)}</span>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
