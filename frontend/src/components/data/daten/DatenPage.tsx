import { lazy, Suspense, useEffect } from "react";
import type { LiveConditionsRead } from "../../../lib/api";
import type { Spot } from "../../../lib/types";
import SpotTitle from "../../SpotTitle";
import Segmented from "../../ui/Segmented";
import { useDatenFocus } from "./datenFocus";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { formatMonthDayRange } from "../../../lib/bestSeason";
import MapPill from "../../MapPill";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import { EmptyState } from "../../AsyncStates";
import "./daten-theme.css";
import MeteoChart, { MeteoChartSkeleton } from "./MeteoChart";
import TodaySummary, { TodaySummarySkeleton } from "./TodaySummary";
import ForecastDayStrip, { ForecastDayStripSkeleton } from "./ForecastDayStrip";
import { SPOT_FOCUS_ZOOM } from "../../../weather-map/camera";
import { windMapHref } from "../../../weather-map/fieldUrlState";
import TidePanel from "../../TidePanel";

const WindClimatologyModule = lazy(() => import("../WindClimatologyModule"));

/**
 * The spot Daten page rebuilt to the Figma Frame 67 composition: a dark
 * weather-instrument canvas with the meteogram on top, a today-summary /
 * 8-day-outlook band, a map / live-wind band, and the wind-months field. The
 * page follows the site theme like the Info tab; `.daten-theme`
 * (daten-theme.css) only adds the data-encoding tones, independent of
 * the site theme, matching the mockup.
 */
export default function DatenPage({
  spot,
  forecast,
  forecastLoading,
  forecastError,
  bestSeason = null,
}: {
  spot: Spot;
  live?: LiveConditionsRead | null;
  liveLoading?: boolean;
  liveError?: string | null;
  liveStale?: boolean;
  onRetryLive?: () => void;
  forecast: NormalizedForecastSeries | null;
  forecastLoading: boolean;
  forecastError?: string | null;
  /** The spot's natural best-travel-season window (V3 best_season), surfaced as
   *  a jump link in the header. Null while loading or when no clear season. */
  bestSeason?: { start_date: string; end_date: string } | null;
}) {
  const hasForecast = !!forecast && forecast.days.length > 0;
  const hasMarineWater = (spot.waterTypes ?? []).some((kind) =>
    kind === "ocean" || kind === "sea" || kind === "lagoon",
  );

  // Arriving from the Info-tab "Beste Reisezeit" link lands on /daten#windmonate.
  // The section is lazy-loaded and far down the page, so native hash scrolling
  // can fire before it mounts — retry briefly until the anchor exists.
  useEffect(() => {
    if (typeof window === "undefined" || window.location.hash !== "#windmonate") return;
    let tries = 0;
    let timer: number;
    const scroll = () => {
      const el = document.getElementById("windmonate");
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      } else if (tries++ < 20) {
        timer = window.setTimeout(scroll, 100);
      }
    };
    scroll();
    return () => window.clearTimeout(timer);
  }, []);

  const [savedFocus, setFocus] = useDatenFocus();
  // A lake has no sea to lay the tab out for.
  const focus = hasMarineWater ? savedFocus : "wind";

  const jumpToWindmonate = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    document.getElementById("windmonate")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <SpotDataScopeProvider forecast={forecast}>
      <div className="daten-theme min-h-screen">
        {/* Same page frame as the landing grid and every other public page. */}
        <div className="mx-auto max-w-page px-5 pb-24 pt-10 sm:px-8">
          {/* Spot identity exactly as on the Info tab: the name at the same
              size, region and country beside it on the same baseline. */}
          <header>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <SpotTitle spot={spot} />
              </div>
              {/* Wind is the default layout; at the coast a switch lays the
                  tab out for the sea instead (2026-11-25). */}
              {hasMarineWater && (
                <Segmented
                  size="sm"
                  className="shrink-0"
                  label="Daten ausgelegt für"
                  value={focus}
                  onChange={setFocus}
                  options={[
                    { id: "wind", label: "Wind" },
                    { id: "wave", label: "Welle" },
                  ]}
                />
              )}
            </div>

            {/* The page's core answer — "when should I go?" — surfaced right up
                top as a jump link to the detailed Windmonate section below, so
                it isn't buried under the near-term forecast. */}
            {bestSeason && (
              <a
                href="#windmonate"
                onClick={jumpToWindmonate}
                className="group mt-3 inline-flex items-center gap-1.5 text-ui font-medium text-ink underline decoration-ink/40 underline-offset-4 transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                Beste Reisezeit: {formatMonthDayRange(bestSeason.start_date, bestSeason.end_date)}
                <span aria-hidden="true" className="transition-transform group-hover:translate-y-0.5">↓</span>
              </a>
            )}
          </header>

          {/* 0) Compact multi-day overview — mini wind bars per day; click a day
              to jump the meteogram below to it (Windfinder-style day tabs). */}
          {/* Every section shows a placeholder in its final size while the
              forecast loads, then fades the data in (chosen 2026-11-25,
              "Platzhalter in Endgröße"): nothing below moves. */}
          {(hasForecast || forecastLoading) && (
            <div className="mt-8">
              {hasForecast ? (
                <div className="swd-fade-in"><ForecastDayStrip forecast={forecast!} focus={focus} /></div>
              ) : (
                <ForecastDayStripSkeleton />
              )}
            </div>
          )}

          {/* 1) Meteogram — waves, weather, temperature, wind, direction, time. */}
          <section
            id="spot-meteogramm"
            aria-label="Meteogramm"
            className="mt-4 scroll-mt-6"
          >
            {forecastLoading && <MeteoChartSkeleton />}
            {!forecastLoading && hasForecast && <div className="swd-fade-in"><MeteoChart forecast={forecast!} focus={focus} /></div>}
            {!forecastLoading && !hasForecast && (
              <EmptyState message={forecastError ? "Vorhersage momentan nicht verfügbar." : "Keine Vorhersage-Daten."} />
            )}
          </section>

          {/* 2) The selected day: big reading, sky arc and the day's wind band.
              (The 10-day confidence list that sat beside it was removed on
              2026-11-24 — the day strip above already covers the ten days.) */}
          {(hasForecast || forecastLoading) && (
            <section aria-label="Tagesübersicht" className="mt-6 max-w-[900px]">
              {hasForecast ? (
                <div className="swd-fade-in"><TodaySummary forecast={forecast!} focus={focus} /></div>
              ) : (
                <TodaySummarySkeleton />
              )}
            </section>
          )}

          {/* Far sections render only once they near the screen
              (content-visibility), so the first paint of the tab is quicker;
              the intrinsic size keeps the scrollbar honest meanwhile. */}
          {spot.uuid && hasMarineWater && (
            <div className="[content-visibility:auto] [contain-intrinsic-size:auto_320px]">
              <TidePanel spotId={spot.uuid} />
            </div>
          )}

          {/* 3) The map is no longer a second map of its own: the "Karte"
              button below opens the one weather map, framed on this spot. */}

          {/* 4) Wind months. */}
          {/* Flush to the content column like the meteogram above — no card,
              no stroke, full width; the chart itself handles its own rhythm. */}
          <section id="windmonate" aria-label="Beste Reisezeit" className="mt-16 scroll-mt-6 [content-visibility:auto] [contain-intrinsic-size:auto_720px]">
            <Suspense fallback={<div className="h-40 animate-pulse rounded-card bg-band" />}>
              <WindClimatologyModule spot={spot} />
            </Suspense>
          </section>
        </div>

        {/* Floating map access, bottom-centre — mirrors the landing / results
            "Karte" pill (filled, no stroke, travels with the scroll). It opens
            the shared weather map zoomed to this spot, locked to the wind
            field: on a spot surface there is nothing to toggle to. */}
        {spot.coords && (
          <MapPill
            to={windMapHref([spot.coords[1], spot.coords[0]], SPOT_FOCUS_ZOOM, { toggle: false })}
            ground="band"
            className="text-ink"
          />
        )}
      </div>
    </SpotDataScopeProvider>
  );
}
