import type { LiveConditionsRead } from "./api";
import { currentWindPresentation, MS_TO_KT } from "./liveWindPresentation";

export { MS_TO_KT } from "./liveWindPresentation";

export type ObservationType = "measurement" | "nowcast" | "live_wind" | "forecast";
export type SpotMapReading = {
  type: ObservationType;
  windDir: number | null;
  windKt: number | null;
  waveDir: number | null;
  waveM: number | null;
  period: number | null;
  coastalNormalDeg: number | null;
  label: string;
};

export type ForecastHourLike = {
  dir: number | null;
  wind: number | null;
  swell_dir: number | null;
  swell: number | null;
  period: number | null;
  coastal_normal_deg?: number | null;
  localTimeWithOffset: string;
};

/** The single COMPUTED reading SpotMap shows, in priority order: the spot's
 *  scrubbed forecast hour (if the Daten tab has one selected), then LiveWind,
 *  else the model nowcast. A real station measurement is deliberately NOT returned here: it is
 *  a separate reference product (see {@link referenceMeasurement}) and must not
 *  be presented as the computed spot wind. Never uses a raw station value as
 *  the spot wind. */
export function currentReading(live: LiveConditionsRead | null, selectedForecast: ForecastHourLike | null): SpotMapReading | null {
  if (selectedForecast) {
    return {
      type: "forecast", windDir: selectedForecast.dir, windKt: selectedForecast.wind,
      waveDir: selectedForecast.swell_dir, waveM: selectedForecast.swell, period: selectedForecast.period,
      coastalNormalDeg: selectedForecast.coastal_normal_deg ?? null,
      label: `Forecast · ${selectedForecast.localTimeWithOffset}`,
    };
  }
  const currentWind = currentWindPresentation(live);
  if (currentWind.status !== "unavailable") {
    const c = live?.current;
    return {
      type: currentWind.source === "live_wind" ? "live_wind" : "nowcast",
      windDir: currentWind.directionFromDeg,
      windKt: currentWind.windKt,
      waveDir: c?.swell_dir ?? null,
      waveM: c?.swell ?? null,
      period: c?.period ?? null,
      coastalNormalDeg: c?.coastal_normal_deg ?? live?.coastal_normal_deg ?? null,
      label: currentWind.status === "station_adjusted"
        ? "LiveWind · stationskorrigiert"
        : currentWind.source === "live_wind"
          ? "Baseline · LiveWind-Modellbasis"
          : "Baseline · Modell-Nowcast",
    };
  }
  return null;
}

export type ReferenceMeasurement = {
  windDir: number | null;
  windKt: number | null;
  windMs: number | null;
  observedAt: string;
  ageSeconds: number;
  provider: string;
  stationName: string | null;
  distanceKm: number | null;
};

/** The station reading as a SEPARATE reference product, never as the spot wind.
 *  Carries its own ``observedAt`` so the sidebar/card labels it as a measured
 *  reference with the real observation time, distinct from the model nowcast. */
export function referenceMeasurement(live: LiveConditionsRead | null): ReferenceMeasurement | null {
  const m = live?.measurement;
  if (!m) return null;
  return {
    windDir: m.wind_direction_from_deg ?? null,
    windKt: m.wind_speed_ms != null ? m.wind_speed_ms * MS_TO_KT : null,
    windMs: m.wind_speed_ms ?? null,
    observedAt: m.observed_at,
    ageSeconds: m.age_seconds,
    provider: m.provider,
    stationName: m.station_name ?? null,
    distanceKm: m.distance_km ?? null,
  };
}

export const OBSERVATION_BADGE: Record<ObservationType, string> = { measurement: "Messung", nowcast: "Baseline", live_wind: "LiveWind", forecast: "Forecast" };
