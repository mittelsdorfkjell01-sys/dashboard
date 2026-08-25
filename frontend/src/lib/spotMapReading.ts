import type { LiveConditionsRead } from "./api";

export const MS_TO_KT = 1 / 0.514444;

export type ObservationType = "measurement" | "nowcast" | "forecast";
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

/** The single reading SpotMap actually shows, in priority order: the spot's
 *  scrubbed forecast hour (if the Daten tab has one selected), else a real
 *  station measurement, else the model nowcast. Never a mix of fields from
 *  different sources for the same instant — each branch reads one source
 *  only, so a value's provenance badge is always accurate for every field
 *  shown alongside it. A station here measures wind only, so a
 *  "measurement" reading always carries null wave fields rather than
 *  silently borrowing them from the nowcast. */
export function currentReading(live: LiveConditionsRead | null, selectedForecast: ForecastHourLike | null): SpotMapReading | null {
  if (selectedForecast) {
    return {
      type: "forecast", windDir: selectedForecast.dir, windKt: selectedForecast.wind,
      waveDir: selectedForecast.swell_dir, waveM: selectedForecast.swell, period: selectedForecast.period,
      coastalNormalDeg: selectedForecast.coastal_normal_deg ?? null,
      label: `Forecast · ${selectedForecast.localTimeWithOffset}`,
    };
  }
  if (live?.measurement) {
    const m = live.measurement;
    return {
      type: "measurement", windDir: m.wind_direction_from_deg,
      windKt: m.wind_speed_ms != null ? m.wind_speed_ms * MS_TO_KT : null,
      waveDir: null, waveM: null, period: null,
      coastalNormalDeg: null,
      label: `Messung · ${m.provider}`,
    };
  }
  if (live?.current) {
    const c = live.current;
    return { type: "nowcast", windDir: c.dir, windKt: c.wind, waveDir: c.swell_dir, waveM: c.swell, period: c.period, coastalNormalDeg: c.coastal_normal_deg ?? live.coastal_normal_deg ?? null, label: `Nowcast · ${live.model}` };
  }
  return null;
}

export const OBSERVATION_BADGE: Record<ObservationType, string> = { measurement: "Messung", nowcast: "Nowcast", forecast: "Forecast" };
