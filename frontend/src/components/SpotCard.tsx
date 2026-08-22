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
 * Every tile shows wind (kts) with wave height (m) stacked below it. Wind
 * gets a live green-dot reading when the caller passes `live` (see
 * lib/hooks.ts's useSpotsLive, chunked to the `/spots/live` endpoint's
 * 20-id cap); otherwise it falls back to the typical/editorial figure.
 * Wave height has no backend source yet, so it renders as a "—" placeholder
 * until that data exists.
 *
 * `compact` is the map popup/strip treatment: image + name/figure row only —
 * no room there for region, sports or best-months.
 */
export default function SpotCard({
  spot,
  compact = false,
  mapRail = false,
  live,
}: {
  spot: Spot;
  compact?: boolean;
  /** Public /map rail: compact image card with its factual region line. */
  mapRail?: boolean;
  live?: LiveConditionsRead;
}) {
  const sports = (spot.sports ?? []).map(sportLabel).join(" · ");
  const regionLine = [spot.regionName, countryName(spot.regionCountry ?? undefined)]
    .filter(Boolean)
    .join(" · ");

  const windLive = live?.current.wind;
  const windValue = windLive ?? spot.typicalWindKt;
  const windIsLive = windLive != null;
  const waveValue = spot.typicalWaveHeightM;
  // Map rail: "18 kn · live" / "18 kn · vor 12 Min." instead of a bare dot —
  // only when the API gave a real timestamp; no invented age otherwise.
  const liveMinutesAgo = windIsLive && live?.time ? Math.max(0, Math.round((Date.now() - new Date(live.time).getTime()) / 60_000)) : null;
  const liveSuffix = windIsLive ? (liveMinutesAgo !== null && liveMinutesAgo >= 1 ? `vor ${liveMinutesAgo} Min.` : "live") : null;

  return (
    <Link
      to={spotPath(spot)}
      className="swd-mobile-deferred-card group flex h-full flex-col rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
    >
      <div className={`relative overflow-hidden rounded-2xl ${mapRail ? "aspect-[3/2]" : "aspect-video"}`}>
        <SpotImage src={spot.image} name={spot.name} region={spot.region} compact />
      </div>

      <div className={`flex flex-1 flex-col ${compact ? "gap-0 pt-1.5" : "gap-0 pt-1.5 sm:pt-2"}`}>
        <div className="flex items-baseline justify-between gap-3">
          <p
            className={`min-w-0 truncate font-semibold text-ink ${compact ? "text-label" : "text-body"}`}
          >
            {spot.name}
          </p>
          {windValue != null && (
            <div className="flex shrink-0 items-baseline gap-1 whitespace-nowrap">
              {!mapRail && windIsLive && <span aria-hidden className="inline-block h-1.5 w-1.5 translate-y-[-1px] rounded-full bg-green" />}
              <span className="text-label font-semibold text-ink">{windValue}</span>
              <span className="text-caption text-ink-soft">kts</span>
              {mapRail && liveSuffix && <span className="text-caption text-muted">· {liveSuffix}</span>}
            </div>
          )}
        </div>

        {mapRail && regionLine && (
          <p className="min-w-0 truncate text-[11px] text-muted sm:text-caption">{regionLine}</p>
        )}

        {!compact && (
          <div className="flex items-baseline justify-between gap-3">
            {regionLine && <p className="min-w-0 truncate text-[11px] text-muted sm:text-caption">{regionLine}</p>}
            <div className="flex shrink-0 items-baseline gap-1 whitespace-nowrap">
              <span className="text-label font-semibold text-ink">{waveValue ?? "—"}</span>
              <span className="text-caption text-ink-soft">m</span>
            </div>
          </div>
        )}

        {!compact && (sports || spot.windAvailability) && (
          <div className="mt-auto pt-1">
            <div className="flex items-baseline justify-between gap-3">
              {sports && <span className="min-w-0 truncate text-[11px] text-muted sm:text-caption">{sports}</span>}
              {spot.windAvailability && <span className="shrink-0 text-[10px] text-muted">15–20 kt</span>}
            </div>
            {spot.windAvailability && <div className="mt-1.5 grid grid-cols-12 gap-0.5" aria-label="Monatliche Windverfügbarkeit bei 15 bis 20 Knoten">{spot.windAvailability.map((value, index) => <span key={index} title={`${index + 1}. Monat: ${value}%`} className="h-1.5 rounded-sm bg-teal" style={{ opacity: Math.max(.12, value / 100) }}><span className="sr-only">{value}%</span></span>)}</div>}
          </div>
        )}
      </div>
    </Link>
  );
}
