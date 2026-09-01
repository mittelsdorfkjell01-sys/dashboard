import { lazy, Suspense } from "react";
import type { LiveConditionsRead } from "../../../lib/api";
import type { Spot } from "../../../lib/types";
import type { NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { sportLabel } from "../../../lib/labels";
import { CheckCircleIcon } from "../../../lib/icons";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import { EmptyState } from "../../AsyncStates";
import "./daten-theme.css";
import MeteoChart from "./MeteoChart";
import TodaySummary from "./TodaySummary";
import ForecastGrid from "./ForecastGrid";
import WindSidebar from "./WindSidebar";

const SpotMap = lazy(() => import("../../SpotMap"));
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
  live,
  forecast,
  forecastLoading,
  forecastError,
}: {
  spot: Spot;
  live?: LiveConditionsRead | null;
  forecast: NormalizedForecastSeries | null;
  forecastLoading: boolean;
  forecastError?: string | null;
}) {
  const [lat, lng] = spot.coords ?? [undefined, undefined];
  const hasForecast = !!forecast && forecast.days.length > 0;

  return (
    <SpotDataScopeProvider forecast={forecast}>
      <div className="daten-dark min-h-screen">
        <div className="mx-auto max-w-[1340px] px-5 pb-24 pt-10 sm:px-8">
          {/* Location + sport (Figma: "Alcyons" / "Surfen"). */}
          <header>
            <h1 className="text-sz-24 font-semibold tracking-tight text-ink">{spot.name}</h1>
            {spot.sports && spot.sports.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
                {spot.sports.map((s) => (
                  <span key={s} className="inline-flex items-center gap-1 text-label font-medium text-ink">
                    {sportLabel(s)}
                    <CheckCircleIcon width={15} height={15} className="text-teal" />
                  </span>
                ))}
              </div>
            )}
          </header>

          {/* 1) Meteogram — waves, weather, temperature, wind, direction, time. */}
          <section aria-label="Meteogramm" className="mt-10">
            {forecastLoading && <MeteogramSkeleton />}
            {!forecastLoading && hasForecast && <MeteoChart forecast={forecast!} />}
            {!forecastLoading && !hasForecast && (
              <EmptyState message={forecastError ? "Vorhersage momentan nicht verfügbar." : "Keine Vorhersage-Daten."} />
            )}
          </section>

          {/* 2) Today summary + 8-day outlook. */}
          {hasForecast && (
            <section aria-label="Tagesübersicht und Ausblick" className="mt-14 grid gap-12 lg:grid-cols-2 lg:gap-16">
              <TodaySummary forecast={forecast!} lat={lat} lng={lng} />
              <ForecastGrid forecast={forecast!} />
            </section>
          )}

          {/* 3) Map + live wind. */}
          <section aria-label="Karte und Livewind" className="mt-16 grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-12">
            <Suspense fallback={<div className="aspect-[16/9] w-full animate-pulse rounded-2xl bg-band" />}>
              <SpotMap
                spot={spot}
                live={live}
                forecast={forecast}
                zoom={spot.mapView?.zoom}
                mapCenter={spot.mapView?.center}
                aspect="sm:aspect-[16/9]"
                rounded
              />
            </Suspense>
            <WindSidebar forecast={forecast} live={live} lat={lat} lng={lng} />
          </section>

          {/* 4) Wind months. */}
          <section aria-label="Windmonate" className="mt-16">
            <div className="rounded-2xl border border-line p-6 sm:p-8">
              <Suspense fallback={<div className="h-40 animate-pulse rounded bg-band" />}>
                <WindClimatologyModule spot={spot} />
              </Suspense>
            </div>
          </section>
        </div>
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
  const windH = (i: number) => 26 + ((i * 5) % 8) * 8; // 26–82px
  return (
    <div className="flex min-w-0 animate-pulse gap-3" role="status" aria-label="Meteogramm wird geladen">
      <div className="shrink-0 select-none pt-1 text-data-caption uppercase tracking-[0.14em] text-muted/40">
        {["WELLE", "WETTER", "TEMP.", "WIND", "RICHT.", "ZEIT"].map((label, i) => (
          <div key={label} className="flex items-center" style={{ height: [40, 58, 108, 134, 26, 22][i] }}>
            {label}
          </div>
        ))}
      </div>
      <div className="min-w-0 flex-1 overflow-hidden">
        {/* WELLE — short bars hanging from the top. */}
        <div className="flex h-10 items-start gap-3">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="w-[22px] rounded-[4px] bg-line" style={{ height: waveH(i) }} />
          ))}
        </div>
        {/* WETTER — glyph placeholders. */}
        <div className="flex h-[58px] items-center gap-3">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="h-[22px] w-[22px] rounded-full bg-line-soft" />
          ))}
        </div>
        {/* TEMP — a faint curve stand-in. */}
        <div className="flex h-[108px] items-center">
          <span className="h-px w-full bg-line" />
        </div>
        {/* WIND — bars rising from the baseline. */}
        <div className="flex h-[134px] items-end gap-3">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="w-[22px] rounded-[5px] bg-line" style={{ height: windH(i) }} />
          ))}
        </div>
        {/* RICHT + ZEIT — axis ticks (combined height of both label rows). */}
        <div className="flex h-[48px] items-center gap-3">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className="h-3 w-[22px] rounded-sm bg-line-soft" />
          ))}
        </div>
      </div>
    </div>
  );
}
