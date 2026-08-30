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
            {forecastLoading && <div className="h-[360px] animate-pulse rounded bg-band" />}
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
