import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "./forecastNormalization";

export const SPOT_FORECAST_START_MINUTE = 6 * 60;
export const SPOT_FORECAST_END_MINUTE = 22 * 60;

/** The Spot-Daten forecast shows 17 local hourly slots from 06:00 through 22:00. */
export function isSpotForecastDisplayHour(hour: NormalizedForecastHour): boolean {
  return hour.localMinute >= SPOT_FORECAST_START_MINUTE && hour.localMinute <= SPOT_FORECAST_END_MINUTE;
}

export function spotForecastDayHours(day: NormalizedForecastDay): NormalizedForecastHour[] {
  return day.hours.filter(isSpotForecastDisplayHour);
}

export function spotForecastHours(
  forecast: NormalizedForecastSeries | null | undefined,
): NormalizedForecastHour[] {
  return forecast?.days.flatMap(spotForecastDayHours).sort((a, b) => Date.parse(a.utcKey) - Date.parse(b.utcKey)) ?? [];
}
