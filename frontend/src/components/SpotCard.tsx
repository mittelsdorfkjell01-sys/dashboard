import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";
import type { LiveConditionsRead } from "../lib/api";
import { sportLabel } from "../lib/labels";
import { countryName } from "../lib/flags";
import SpotImage from "./SpotImage";
import { spotPath } from "../lib/spotRoutes";

/**
 * The one spot-tile layout used everywhere a spot is browsed: landing grid,
 * top-spots row, region grid, similar-spots, and (via `compact`) the map
 * popup/strip. No background, border or shadow — the rounded image is the
 * only framed element; the card itself is a plain link over the page
 * surface. No hover treatment on the card (no bg change) — the whole tile
 * is the tap target, `focus-visible` covers keyboard/a11y.
 *
 * The wind-or-wave-height figure gets a live green-dot reading when the
 * caller passes `live` (see lib/hooks.ts's useSpotsLive, chunked to the
 * `/spots/live` endpoint's 20-id cap); otherwise it falls back to the
 * typical/editorial figure with no dot. Exactly one of wind/wave-height
 * shows, per the spot's primary sport (see app.scoring.context on the
 * backend) — never both, never invented when the data isn't there.
 *
 * `compact` is the map popup/strip treatment: image + name/figure row only —
 * no room there for region, sports or best-months.
 */
export default function SpotCard({
  spot,
  compact = false,
  live,
}: {
  spot: Spot;
  compact?: boolean;
  live?: LiveConditionsRead;
}) {
  const sports = (spot.sports ?? []).map(sportLabel).join(" · ");
  const regionLine = [spot.regionName, countryName(spot.regionCountry ?? undefined)]
    .filter(Boolean)
    .join(" · ");

  const isWave = spot.typicalWaveHeightM != null;
  const liveValue = isWave ? live?.current.swell : live?.current.wind;
  const value = liveValue ?? (isWave ? spot.typicalWaveHeightM : spot.typicalWindKt);
  const isLive = liveValue != null;
  const unit = isWave ? "m" : "kts";

  return (
    <Link
      to={spotPath(spot)}
      className="group flex h-full flex-col rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
    >
      <div className="relative aspect-video overflow-hidden rounded-2xl">
        <SpotImage src={spot.image} name={spot.name} region={spot.region} compact />
      </div>

      <div className={`flex flex-1 flex-col ${compact ? "gap-0.5 pt-2" : "gap-1 pt-2 sm:pt-3"}`}>
        <div className="flex items-baseline justify-between gap-3">
          <p
            className={`min-w-0 truncate font-semibold text-ink ${compact ? "text-label" : "text-body"}`}
          >
            {spot.name}
          </p>
          {value != null && (
            <div className="flex shrink-0 items-baseline gap-1 whitespace-nowrap">
              {isLive && <span aria-hidden className="inline-block h-1.5 w-1.5 translate-y-[-1px] rounded-full bg-green" />}
              <span className="text-label font-semibold text-ink">{value}</span>
              <span className="text-caption text-ink-soft">{unit}</span>
            </div>
          )}
        </div>

        {!compact && (
          <>
            {regionLine && <p className="truncate text-[11px] text-muted sm:text-caption">{regionLine}</p>}

            {(sports || spot.windAvailability) && (
              <div className="mt-auto pt-1">
                <div className="flex items-baseline justify-between gap-3">
                {sports && <span className="min-w-0 truncate text-[11px] text-muted sm:text-caption">{sports}</span>}
                {spot.windAvailability && <span className="shrink-0 text-[10px] text-muted">15–20 kt</span>}
                </div>
                {spot.windAvailability && <div className="mt-1.5 grid grid-cols-12 gap-0.5" aria-label="Monatliche Windverfügbarkeit bei 15 bis 20 Knoten">{spot.windAvailability.map((value, index) => <span key={index} title={`${index + 1}. Monat: ${value}%`} className="h-1.5 rounded-sm bg-teal" style={{ opacity: Math.max(.12, value / 100) }}><span className="sr-only">{value}%</span></span>)}</div>}
              </div>
            )}
          </>
        )}
      </div>
    </Link>
  );
}
