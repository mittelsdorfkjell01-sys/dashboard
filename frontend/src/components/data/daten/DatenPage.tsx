import { lazy, Suspense, useEffect } from "react";
import { Link } from "react-router-dom";
import type { LiveConditionsRead } from "../../../lib/api";
import type { Spot } from "../../../lib/types";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { sportLabel } from "../../../lib/labels";
import { formatMonthDayRange } from "../../../lib/bestSeason";
import { CheckCircleIcon, MapIcon } from "../../../lib/icons";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import { EmptyState } from "../../AsyncStates";
import "./daten-theme.css";
import MeteoChart from "./MeteoChart";
import TodaySummary from "./TodaySummary";
import ForecastGrid from "./ForecastGrid";
import ForecastDayStrip from "./ForecastDayStrip";
import { SPOT_FOCUS_ZOOM } from "../../../weather-map/camera";
import { windMapHref } from "../../../weather-map/fieldUrlState";
import TidePanel from "../../TidePanel";

const WindClimatologyModule = lazy(() => import("../WindClimatologyModule"));

/**
 * The spot Daten page rebuilt to the Figma Frame 67 composition: a dark
 * weather-instrument canvas with the meteogram on top, a today-summary /
 * 8-day-outlook band, a map / live-wind band, and the wind-months field. The
 * whole surface is scoped dark via `.daten-dark` (see index.css) regardless of
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

  const jumpToWindmonate = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    document.getElementById("windmonate")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <SpotDataScopeProvider forecast={forecast}>
      <div className="daten-dark min-h-screen">
        {/* Same page frame as the landing grid and every other public page. */}
        <div className="mx-auto max-w-page px-5 pb-24 pt-10 sm:px-8">
          {/* Location + sport (Figma: "Alcyons" / "Surfen"). */}
          <header>
            <h1 className="text-title font-semibold tracking-tight text-ink">{spot.name}</h1>
            {spot.sports && spot.sports.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
                {spot.sports.map((s) => (
                  <span key={s} className="inline-flex items-center gap-1 text-ui font-medium text-ink">
                    {sportLabel(s)}
                    <CheckCircleIcon checkOnly width={15} height={15} className="text-ink" />
                  </span>
                ))}
              </div>
            )}

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
          {hasForecast && (
            <div className="mt-8">
              <ForecastDayStrip forecast={forecast!} />
            </div>
          )}

          {/* 1) Meteogram — waves, weather, temperature, wind, direction, time. */}
          <section
            id="spot-meteogramm"
            aria-label="Meteogramm"
            className="mt-4 scroll-mt-6"
          >
            {forecastLoading && <MeteogramSkeleton />}
            {!forecastLoading && hasForecast && <MeteoChart forecast={forecast!} />}
            {!forecastLoading && !hasForecast && (
              <EmptyState message={forecastError ? "Vorhersage momentan nicht verfügbar." : "Keine Vorhersage-Daten."} />
            )}
          </section>

          {/* 2) Today summary + compact 10-day outlook. */}
          {hasForecast && (
            <section aria-label="Tagesübersicht und Ausblick" className="mt-6 grid gap-12 lg:grid-cols-2 lg:gap-16">
              <TodaySummary forecast={forecast!} />
              <ForecastGrid forecast={forecast!} />
            </section>
          )}

          {spot.uuid && <TidePanel spotId={spot.uuid} />}

          {/* 3) The map is no longer a second map of its own: the "Karte"
              button below opens the one weather map, framed on this spot. */}

          {/* 4) Wind months. */}
          {/* Flush to the content column like the meteogram above — no card,
              no stroke, full width; the chart itself handles its own rhythm. */}
          <section id="windmonate" aria-label="Beste Reisezeit" className="mt-16 scroll-mt-6">
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
          <Link
            to={windMapHref([spot.coords[1], spot.coords[0]], SPOT_FOCUS_ZOOM, { toggle: false })}
            aria-label="Karte öffnen"
            className="fixed bottom-6 left-1/2 z-sticky flex -translate-x-1/2 items-center gap-1.5 rounded-card bg-page px-4 py-2 text-ui font-normal text-white shadow-float"
          >
            Karte <MapIcon className="text-body" />
          </Link>
        )}
      </div>
    </SpotDataScopeProvider>
  );
}

// Loading placeholder that mirrors the meteogram's instrument structure (row-
// label gutter + wave bars, a temperature line and wind bars) rather than a
// single block, so the skeleton reads as "this chart is loading". Kept quiet:
// faint hairline-toned shapes, one gentle pulse, no glow (per the instrument
// aesthetic). Deterministic bar heights so it doesn't reflow between frames.
function MeteogramSkeleton() {
  const cols = 18;
  const waveH = (i: number) => 6 + ((i * 7) % 5) * 3; // 6–18px
  const windH = (i: number) => 14 + ((i * 5) % 7) * 7; // 14–56px
  return (
    <div className="flex min-w-0 animate-pulse gap-3" role="status" aria-label="Meteogramm wird geladen">
      <div className="shrink-0 select-none pt-1 text-data-caption uppercase tracking-caps text-muted/40">
        {["WELLE", "WETTER", "TEMP.", "WIND", "RICHT.", "ZEIT"].map((label, i) => (
          <div key={label} className="flex items-center" style={{ height: [40, 58, 24, 78, 26, 26][i] }}>
            {label}
          </div>
        ))}
      </div>
      <div className="min-w-0 flex-1 overflow-hidden">
        {/* WELLE — short bars hanging from the top. */}
        <div className="flex h-10 items-start gap-[3px]">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="w-[22px] rounded-card bg-line" style={{ height: waveH(i) }} />
          ))}
        </div>
        {/* WETTER — glyph placeholders. */}
        <div className="flex h-[58px] items-center gap-[3px]">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="h-[22px] w-[22px] rounded-full bg-line-soft" />
          ))}
        </div>
        {/* TEMP — text-width placeholders, matching the value-only row. */}
        <div className="flex h-[24px] items-center gap-[3px]">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="w-[22px] text-center text-caption leading-none text-line-soft">—</span>
          ))}
        </div>
        {/* WIND — bars rising from the baseline. */}
        <div className="flex h-[78px] items-end gap-[3px]">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="w-[22px] rounded-card bg-line" style={{ height: windH(i) }} />
          ))}
        </div>
        {/* RICHT + ZEIT — axis ticks (combined height of both label rows). */}
        <div className="flex h-[52px] items-center gap-[3px]">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="h-3 w-[22px] rounded-card bg-line-soft" />
          ))}
        </div>
      </div>
    </div>
  );
}
