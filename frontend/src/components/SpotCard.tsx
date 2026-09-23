import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import type { Spot } from "../lib/types";
import type { LiveConditionsRead } from "../lib/api";
import { sportLabelShort } from "../lib/labels";
import { countryName } from "../lib/flags";
import SpotImage from "./SpotImage";
import { spotPath } from "../lib/spotRoutes";
import { currentWindPresentation, formatAge } from "../lib/liveWindPresentation";
import { useOptionalUnits } from "../context/PrefsContext";
import { windValue as fmtWindValue, WIND_UNIT_SUFFIX, waveValue as fmtWaveValue, WAVE_UNIT_SUFFIX } from "../lib/units";
import { trackEvent } from "../lib/events";

const recordedImpressions = new Set<string>();

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
  preferLiveWind = false,
  eager = true,
  surface,
}: {
  spot: Spot;
  compact?: boolean;
  /** Public /map rail: compact image card with its factual region line. */
  mapRail?: boolean;
  live?: LiveConditionsRead;
  /** Wind-map surfaces may opt into the analyzed product; browse cards stay on current. */
  preferLiveWind?: boolean;
  /** Start the image request immediately once this card is mounted. */
  eager?: boolean;
  /** Recommendation/search context for score-private interaction events. */
  surface?: string;
}) {
  const linkRef = useRef<HTMLAnchorElement | null>(null);
  useEffect(() => {
    if (!surface || !linkRef.current || !("IntersectionObserver" in window)) return;
    const eventKey = `${surface}:${spot.id}`;
    if (recordedImpressions.has(eventKey)) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting || entry.intersectionRatio < 0.5) return;
        recordedImpressions.add(eventKey);
        trackEvent("impression", { spotId: spot.id, surface });
        observer.disconnect();
      },
      { threshold: 0.5 },
    );
    observer.observe(linkRef.current);
    return () => observer.disconnect();
  }, [spot.id, surface]);
  const sports = (spot.sports ?? []).map(sportLabelShort).join(" · ");
  const regionLine = [spot.regionName, countryName(spot.regionCountry ?? undefined)]
    .filter(Boolean)
    .join(" · ");

  const units = useOptionalUnits();
  const presentedWind = currentWindPresentation(live);
  const windLive = preferLiveWind && presentedWind.status !== "unavailable"
    ? presentedWind.windKt
    : live?.current.wind;
  const windValue = windLive ?? spot.typicalWindKt;
  const windIsLive = windLive != null;
  const waveValue = spot.typicalWaveHeightM;
  // Map rail: "18 kn · live" / "18 kn · vor 12 Min." instead of a bare dot —
  // only when the API gave a real timestamp; no invented age otherwise.
  const liveTime = preferLiveWind && presentedWind.status !== "unavailable"
    ? presentedWind.analyzedAt
    : live?.time;
  const liveMinutesAgo = windIsLive && liveTime ? Math.max(0, Math.round((Date.now() - new Date(liveTime).getTime()) / 60_000)) : null;
  const liveSuffix = windIsLive
    ? preferLiveWind
      ? presentedWind.status === "station_adjusted"
        ? "LiveWind"
        : "Baseline"
      : liveMinutesAgo !== null
        ? formatAge(liveMinutesAgo)
        : "live"
    : null;
  const adjustedLiveWind = preferLiveWind && presentedWind.status === "station_adjusted";

  return (
    <Link
      ref={linkRef}
      to={spotPath(spot)}
      onClick={() => {
        if (surface) trackEvent("click", { spotId: spot.id, surface });
      }}
      className="group flex h-full flex-col rounded-[14px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      <div className={`relative overflow-hidden rounded-[14px] ${mapRail ? "aspect-[3/2]" : "aspect-video"}`}>
        <SpotImage
          src={spot.image}
          name={spot.name}
          region={spot.region}
          width={spot.heroWidth}
          focal={spot.heroFocal}
          rotation={spot.heroRotation}
          eager={eager}
          compact
        />
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
              {!mapRail && windIsLive && (!preferLiveWind || adjustedLiveWind) && <span aria-hidden className="inline-block h-1.5 w-1.5 translate-y-[-1px] rounded-full bg-green" />}
              <span className="text-label font-semibold text-ink">{fmtWindValue(windValue, units.wind)}</span>
              <span className="text-caption text-ink-soft">{WIND_UNIT_SUFFIX[units.wind]}</span>
              {mapRail && liveSuffix && <span className="text-caption text-muted">· {liveSuffix}</span>}
            </div>
          )}
        </div>

        {mapRail && regionLine && (
          <p className="min-w-0 truncate text-sz-11 text-muted sm:text-caption">{regionLine}</p>
        )}

        {!compact && (
          <div className="flex items-baseline justify-between gap-3">
            {regionLine && <p className="min-w-0 truncate text-sz-11 text-muted sm:text-caption">{regionLine}</p>}
            <div className="flex shrink-0 items-baseline gap-1 whitespace-nowrap">
              <span className="text-label font-semibold text-ink">{waveValue == null ? "—" : fmtWaveValue(waveValue, units.wave)}</span>
              <span className="text-caption text-ink-soft">{WAVE_UNIT_SUFFIX[units.wave]}</span>
            </div>
          </div>
        )}

        {!compact && sports && (
          <div className="mt-auto min-w-0 pt-1">
            {/* `block` so `truncate` actually clips: an inline <span> ignores
                overflow, letting a full sports list spill past the card edge. */}
            <span className="block truncate text-sz-11 text-muted sm:text-caption">{sports}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
