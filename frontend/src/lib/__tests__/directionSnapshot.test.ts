import { describe, expect, it } from "vitest";
import { degreesToCompass, resolveDirectionSnapshot } from "../directionSnapshot";
import type { NormalizedForecastHour } from "../forecastNormalization";
import type { LiveConditionsRead } from "../api";

const hour = (patch: Partial<NormalizedForecastHour> = {}): NormalizedForecastHour => ({
  time: "2026-08-24T14:00:00.000Z", utcKey: "2026-08-24T14:00:00.000Z",
  localDate: "2026-08-24", localTime: "16:00", localTimeWithOffset: "16:00 GMT+2", localHour: 16, localMinute: 960,
  wind: 20, gust: 27, dir: 318, air: 20, swell: 1.8, period: 11, swell_dir: 292, precip: 0, sst: 18,
  weather_condition: "clear", ...patch,
});
const live: LiveConditionsRead = {
  spot_id: "s", model: "Nowcast model", time: "2026-08-24T13:00:00Z",
  current: { wind: 9, gust: 12, dir: 90, air: 20, sst: 18, swell: 3, period: 6, swell_dir: 180 },
};

describe("resolveDirectionSnapshot", () => {
  it("uses the selected forecast as one complete snapshot", () => {
    const result = resolveDirectionSnapshot({ selectedForecast: hour(), live, forecastTimezone: "Europe/Berlin", forecastStale: true, forecastModel: "Forecast model" });
    expect(result).toMatchObject({ kind: "forecast", windDirectionFromDeg: 318, waveDirectionFromDeg: 292, stale: true, model: "Forecast model" });
  });
  it("never fills a missing forecast field from nowcast", () => {
    const result = resolveDirectionSnapshot({ selectedForecast: hour({ swell_dir: null }), live, forecastTimezone: "Europe/Berlin" });
    expect(result?.waveDirectionFromDeg).toBeNull();
  });
  it("uses the complete nowcast only without a forecast selection", () => {
    expect(resolveDirectionSnapshot({ selectedForecast: null, live, forecastTimezone: "UTC" })).toMatchObject({ kind: "nowcast", windDirectionFromDeg: 90, waveDirectionFromDeg: 180 });
  });
  it("keeps a real measurement separate from model and wave fields", () => {
    const measured: LiveConditionsRead = { ...live, measurement: {
      observation_type: "measurement", station_id: "station", provider: "DWD", provider_station_id: "123",
      observed_at: "2026-08-24T12:00:00Z", age_seconds: 120, distance_km: 2,
      wind_speed_ms: 10, wind_gust_ms: 14, wind_direction_from_deg: 305, quality: 1,
    }};
    const result = resolveDirectionSnapshot({ selectedForecast: null, live: measured, forecastTimezone: "Europe/Berlin" });
    expect(result).toMatchObject({ kind: "measurement", provider: "DWD", windDirectionFromDeg: 305, waveDirectionFromDeg: null, waveHeightM: null });
  });
  it("keeps missing coastal metadata unavailable", () => {
    expect(resolveDirectionSnapshot({ selectedForecast: hour(), live, forecastTimezone: "UTC" })?.coastalNormalDeg).toBeNull();
  });
  it.each([[0,"N"],[22.5,"NNO"],[315,"NW"],[359.9,"N"]])("maps %s degrees to %s", (degrees, label) => expect(degreesToCompass(degrees as number)).toBe(label));
});
