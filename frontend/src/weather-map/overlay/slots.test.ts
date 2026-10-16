import { describe, expect, it } from "vitest";
import { dayRuns, fieldSampleSlots, fieldTileSeriesSlots } from "./slots";
import type { FieldSample, WaveFieldSample } from "../contracts";

function sample(validAt: string, speedMs: number, gustMs: number | null, temperature: number | null): FieldSample {
  return {
    product: "model_wind", publication_id: "p", generation: 1, run_id: "r", provider: "dwd", model: "icon-eu",
    model_run: "2026-10-03T00:00:00Z", valid_at: validAt, latitude: 54, longitude: 10,
    u_ms: speedMs, v_ms: 0, speed_ms: speedMs, direction_from_deg: 270, gust_ms: gustMs,
    temperature_c: temperature, precipitation_mm: null, pressure_hpa: null, cloud_cover_percent: null,
    interpolation: "bilinear_uv", freshness: "fresh",
  };
}

describe("map forecast slots", () => {
  it("converts field samples to knots and keeps them in time order", () => {
    const slots = fieldSampleSlots([
      sample("2026-10-03T13:00:00Z", 10, 15, 15),
      sample("2026-10-03T12:00:00Z", 5, null, 14),
    ]);

    expect(slots.map((slot) => slot.utcKey)).toEqual(["2026-10-03T12:00:00Z", "2026-10-03T13:00:00Z"]);
    expect(slots[0].wind).toBeCloseTo(9.719, 2);
    expect(slots[0].gust).toBeNull();
    expect(slots[1].gust).toBeCloseTo(29.158, 2);
    expect(slots[0].air).toBe(14);
  });

  it("maps wave height, period and direction into forecast slots", () => {
    const wave = {
      product: "model_wave",
      valid_at: "2026-10-03T12:00:00Z",
      total_wave_height_m: 1.8,
      total_wave_period_s: 8.5,
      total_wave_direction_from_deg: 285,
    } as WaveFieldSample;
    const [slot] = fieldSampleSlots([wave]);

    expect(slot).toMatchObject({ swell: 1.8, period: 8.5, swellDirection: 285, wind: null });
  });

  it("groups contiguous hours into one caption per local day", () => {
    const slots = [
      { utcKey: "a", localDate: "2026-10-03", localTime: "12:00", localHour: 12 },
      { utcKey: "b", localDate: "2026-10-03", localTime: "13:00", localHour: 13 },
      { utcKey: "c", localDate: "2026-10-04", localTime: "06:00", localHour: 6 },
    ];
    expect(dayRuns(slots)).toEqual([{ date: "2026-10-03", count: 2 }, { date: "2026-10-04", count: 1 }]);
  });

  it("maps browser-sampled wind and wave tiles without API response objects", () => {
    const wind = fieldTileSeriesSlots([{
      validAt: "2026-10-03T12:00:00Z",
      values: { wind_u: 3, wind_v: 4, wind_gust: 8, temperature_2m: 17 },
    }], "wind")[0];
    const wave = fieldTileSeriesSlots([{
      validAt: "2026-10-03T12:00:00Z",
      values: { wave_u: 1, wave_v: 0, total_wave_height: 1.7, total_wave_period: 9 },
    }], "waves")[0];

    expect(wind.wind).toBeCloseTo(9.719, 2);
    expect(wind.gust).toBeCloseTo(15.551, 2);
    expect(wind.air).toBe(17);
    expect(wave).toMatchObject({ swell: 1.7, period: 9 });
  });
});
