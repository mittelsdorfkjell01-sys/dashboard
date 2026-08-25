import type { CoastalClassification, LiveConditionsRead } from "./api";
import type { NormalizedForecastHour } from "./forecastNormalization";

export type DirectionDataKind = "forecast" | "nowcast" | "measurement";

export type DirectionSnapshot = {
  validAtUtc: string;
  localLabel: string;
  timezone: string;
  kind: DirectionDataKind;
  windDirectionFromDeg: number | null;
  windKt: number | null;
  gustKt: number | null;
  waveDirectionFromDeg: number | null;
  waveHeightM: number | null;
  wavePeriodS: number | null;
  coastalNormalDeg: number | null;
  windCoastalClassification: CoastalClassification | null;
  waveCoastalClassification: CoastalClassification | null;
  stale: boolean;
  quality: string | null;
  provider: string | null;
  model: string | null;
};

const finiteDirection = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 && value < 360 ? value : null;

const localInstant = (instant: string, timezone: string) => {
  const date = new Date(instant);
  if (!Number.isFinite(date.getTime())) return "Zeit nicht verfügbar";
  return new Intl.DateTimeFormat("de-DE", {
    weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: timezone,
    timeZoneName: "short",
  }).format(date);
};

/** Resolve one provenance-clean directional state. No branch borrows a
 * missing field from another time or data kind. */
export function resolveDirectionSnapshot({
  selectedForecast,
  live,
  forecastTimezone,
  forecastStale = false,
  forecastModel = null,
}: {
  selectedForecast: NormalizedForecastHour | null;
  live?: LiveConditionsRead | null;
  forecastTimezone: string;
  forecastStale?: boolean;
  forecastModel?: string | null;
}): DirectionSnapshot | null {
  if (selectedForecast) {
    return {
      validAtUtc: selectedForecast.utcKey,
      localLabel: `${selectedForecast.localDate} · ${selectedForecast.localTimeWithOffset}`,
      timezone: forecastTimezone,
      kind: "forecast",
      windDirectionFromDeg: finiteDirection(selectedForecast.dir),
      windKt: selectedForecast.wind,
      gustKt: selectedForecast.gust,
      waveDirectionFromDeg: finiteDirection(selectedForecast.swell_dir),
      waveHeightM: selectedForecast.swell,
      wavePeriodS: selectedForecast.period,
      coastalNormalDeg: finiteDirection(selectedForecast.coastal_normal_deg),
      windCoastalClassification: selectedForecast.coastal_classification ?? null,
      waveCoastalClassification: selectedForecast.wave_coastal_classification ?? null,
      stale: forecastStale || selectedForecast.stale === true,
      quality: selectedForecast.quality_tier ?? null,
      provider: null,
      model: forecastModel,
    };
  }

  if (live?.measurement) {
    const measurement = live.measurement;
    const timezone = live.provenance?.spot_timezone ?? forecastTimezone;
    return {
      validAtUtc: measurement.observed_at,
      localLabel: localInstant(measurement.observed_at, timezone),
      timezone,
      kind: "measurement",
      windDirectionFromDeg: finiteDirection(measurement.wind_direction_from_deg),
      windKt: measurement.wind_speed_ms == null ? null : measurement.wind_speed_ms / 0.514444,
      gustKt: measurement.wind_gust_ms == null ? null : measurement.wind_gust_ms / 0.514444,
      waveDirectionFromDeg: null,
      waveHeightM: null,
      wavePeriodS: null,
      coastalNormalDeg: null,
      windCoastalClassification: null,
      waveCoastalClassification: null,
      stale: false,
      quality: measurement.quality == null ? null : String(measurement.quality),
      provider: measurement.provider,
      model: null,
    };
  }

  if (live?.current && live.time) {
    const current = live.current;
    const timezone = live.provenance?.spot_timezone ?? forecastTimezone;
    return {
      validAtUtc: live.time,
      localLabel: localInstant(live.time, timezone),
      timezone,
      kind: "nowcast",
      windDirectionFromDeg: finiteDirection(current.dir),
      windKt: current.wind,
      gustKt: current.gust,
      waveDirectionFromDeg: finiteDirection(current.swell_dir),
      waveHeightM: current.swell,
      wavePeriodS: current.period,
      coastalNormalDeg: finiteDirection(current.coastal_normal_deg ?? live.coastal_normal_deg),
      windCoastalClassification: current.coastal_classification ?? live.coastal_classification ?? null,
      waveCoastalClassification: current.wave_coastal_classification ?? null,
      stale: live.provenance?.stale === true,
      quality: live.quality_tier ?? live.provenance?.quality_tier ?? null,
      provider: live.provenance?.provider ?? null,
      model: live.model,
    };
  }
  return null;
}

export const COMPASS_16 = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"] as const;
export function degreesToCompass(degrees: number): string {
  return COMPASS_16[Math.round((((degrees % 360) + 360) % 360) / 22.5) % 16];
}

