import { describe, expect, it } from "vitest";
import { currentReading, referenceMeasurement } from "../spotMapReading";
import type { LiveConditionsRead } from "../api";

const baseLive: LiveConditionsRead = {
  spot_id: "spot-1", model: "icon_eu", time: "2026-08-24T12:00:00Z",
  current: { wind: 18, gust: 24, dir: 312, air: 21, sst: 19, swell: 1.2, period: 9, swell_dir: 270 },
};

describe("currentReading — provenance priority and never mixing sources", () => {
  it("prefers a scrubbed forecast hour over live data entirely", () => {
    const forecastHour = { dir: 200, wind: 25, swell_dir: 260, swell: 1.8, period: 10, coastal_normal_deg: 180, localTimeWithOffset: "16:00 +02:00" };
    const reading = currentReading(baseLive, forecastHour);
    expect(reading).toMatchObject({ type: "forecast", windDir: 200, windKt: 25, waveDir: 260, waveM: 1.8, period: 10 });
    expect(reading?.coastalNormalDeg).toBe(180);
    expect(reading!.label).toContain("16:00 +02:00");
  });

  it("P0.1: keeps the model nowcast as the computed reading even when a measurement exists", () => {
    const live: LiveConditionsRead = {
      ...baseLive,
      measurement: {
        observation_type: "measurement", station_id: "st-1", provider: "DWD", provider_station_id: "123",
        observed_at: "2026-08-24T11:58:00Z", age_seconds: 120, distance_km: 3.2,
        wind_speed_ms: 10, wind_gust_ms: 14, wind_direction_from_deg: 305, quality: 1,
      },
    };
    // The station reading must NOT be presented as the computed spot wind.
    const reading = currentReading(live, null);
    expect(reading!.type).toBe("nowcast");
    expect(reading!.windDir).toBe(312);
    expect(reading!.windKt).toBe(18);
    expect(reading!.label).toContain("icon_eu");
  });

  it("P0.1: exposes the station reading separately as a reference with its own observed_at", () => {
    const live: LiveConditionsRead = {
      ...baseLive,
      measurement: {
        observation_type: "measurement", station_id: "st-1", provider: "DWD", provider_station_id: "123",
        observed_at: "2026-08-24T11:58:00Z", age_seconds: 120, distance_km: 3.2,
        wind_speed_ms: 10, wind_gust_ms: 14, wind_direction_from_deg: 305, quality: 1,
      },
    };
    const reference = referenceMeasurement(live);
    expect(reference!.observedAt).toBe("2026-08-24T11:58:00Z");
    expect(reference!.windDir).toBe(305);
    expect(reference!.windKt).toBeCloseTo(19.4384, 3); // 10 m/s -> kt
    expect(reference!.provider).toBe("DWD");
    expect(referenceMeasurement(baseLive)).toBeNull();  // none when no station reading
  });

  it("falls back to the model nowcast when there is no measurement and no selected forecast hour", () => {
    const reading = currentReading(baseLive, null);
    expect(reading).toMatchObject({ type: "nowcast", windDir: 312, windKt: 18, waveDir: 270, waveM: 1.2, period: 9 });
    expect(reading!.label).toContain("icon_eu");
  });

  it("returns null — not a fabricated reading — when there is no data at all", () => {
    expect(currentReading(null, null)).toBeNull();
  });
});
