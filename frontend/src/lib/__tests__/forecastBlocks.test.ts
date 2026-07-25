import { describe, expect, it } from "vitest";
import type { ForecastDay, ForecastHour, ForecastSeries } from "../api";
import { forecastToBlocks, forecastToDetailBlocks, forecastToHourly } from "../seasonView";

const hour = (time: string, wind: number | null, extra: Partial<ForecastHour> = {}): ForecastHour => ({
  time,
  wind,
  gust: extra.gust ?? null,
  dir: extra.dir ?? null,
  air: extra.air ?? null,
  swell: extra.swell ?? null,
  period: extra.period ?? null,
  swell_dir: extra.swell_dir ?? null,
  precip: extra.precip ?? null,
  sst: extra.sst ?? null,
});

const day = (date: string, hours: ForecastHour[], summary: Partial<ForecastDay["summary"]> = {}): ForecastDay => ({
  date,
  confidence: "high",
  summary: {
    wind_avg: null,
    wind_max: null,
    gust_max: null,
    air_min: null,
    air_max: null,
    swell_max: null,
    ...summary,
  },
  hours,
});

const series = (days: ForecastDay[]): ForecastSeries => ({
  spot_id: "x",
  model: "m",
  generated_at: "2026-07-20T00:00:00Z",
  days,
});

describe("forecastToBlocks (Ebene 1 — 5×3h, best hour)", () => {
  it("assigns an hour exactly at a block boundary to the later block", () => {
    const d = day("2026-07-20", [hour("2026-07-20T09:00", 20), hour("2026-07-20T08:00", 5)]);
    const [result] = forecastToBlocks(series([d]));
    expect(result.blocks[0].wind).toBe(5); // 06–09 only has the 08:00 hour
    expect(result.blocks[1].wind).toBe(20); // 09–12 has the boundary 09:00 hour
  });

  it("picks the block's best (highest-wind) hour, not an average", () => {
    const d = day("2026-07-20", [
      hour("2026-07-20T06:00", 10),
      hour("2026-07-20T07:00", 25),
      hour("2026-07-20T08:00", 15),
    ]);
    const [result] = forecastToBlocks(series([d]));
    expect(result.blocks[0].wind).toBe(25);
  });

  it("skips null-wind hours and returns null for a block with no usable hour", () => {
    const d = day("2026-07-20", [hour("2026-07-20T06:00", null), hour("2026-07-20T07:00", null)]);
    const [result] = forecastToBlocks(series([d]));
    expect(result.blocks[0].wind).toBeNull();
  });

  it("handles a day with no hours at all", () => {
    const d = day("2026-07-20", []);
    const [result] = forecastToBlocks(series([d]));
    expect(result.blocks).toHaveLength(5);
    expect(result.blocks.every((b) => b.wind === null && b.dir === null)).toBe(true);
    expect(result.maxWind).toBeNull();
    expect(result.windDir).toBeNull();
  });

  it("derives the day max from across its blocks, not a single hour", () => {
    const d = day("2026-07-20", [
      hour("2026-07-20T07:00", 12),
      hour("2026-07-20T13:00", 28),
      hour("2026-07-20T19:00", 9),
    ]);
    const [result] = forecastToBlocks(series([d]));
    expect(result.maxWind).toBe(28);
  });

  it("prefers the midday hour's direction, falling back to the first known one", () => {
    const withMidday = day("2026-07-20", [hour("2026-07-20T06:00", 10, { dir: 90 }), hour("2026-07-20T12:00", 10, { dir: 200 })]);
    expect(forecastToBlocks(series([withMidday]))[0].windDir).toBe(200);

    const withoutMidday = day("2026-07-20", [hour("2026-07-20T06:00", 10, { dir: 90 })]);
    expect(forecastToBlocks(series([withoutMidday]))[0].windDir).toBe(90);
  });
});

describe("forecastToDetailBlocks (Ebene 2 — 8×2h, mean + gust max)", () => {
  it("averages wind within a 2h block, not the max", () => {
    const d = day("2026-07-20", [hour("2026-07-20T06:00", 10), hour("2026-07-20T07:00", 20)]);
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.blocks[0].windAvg).toBe(15);
  });

  it("takes the peak gust within a 2h block", () => {
    const d = day("2026-07-20", [
      hour("2026-07-20T06:00", 10, { gust: 14 }),
      hour("2026-07-20T07:00", 12, { gust: 22 }),
    ]);
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.blocks[0].gustMax).toBe(22);
  });

  it("respects 2h block boundaries", () => {
    const d = day("2026-07-20", [hour("2026-07-20T08:00", 30), hour("2026-07-20T07:00", 5)]);
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.blocks[0].windAvg).toBe(5); // 06–08
    expect(result.blocks[1].windAvg).toBe(30); // 08–10, boundary hour
  });

  it("skips null-wind hours when averaging", () => {
    const d = day("2026-07-20", [hour("2026-07-20T06:00", 10), hour("2026-07-20T07:00", null)]);
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.blocks[0].windAvg).toBe(10);
  });

  it("handles an incomplete day (only morning hours present)", () => {
    const d = day("2026-07-20", [hour("2026-07-20T06:00", 10), hour("2026-07-20T07:00", 12)]);
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.blocks[0].windAvg).not.toBeNull();
    expect(result.blocks[7].windAvg).toBeNull(); // 20–22, no data
  });

  it("handles a day with no hours at all", () => {
    const d = day("2026-07-20", []);
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.blocks).toHaveLength(8);
    expect(result.blocks.every((b) => b.windAvg === null && b.gustMax === null && b.dir === null)).toBe(true);
    expect(result.wavePeriod).toBeNull();
  });

  it("takes waveHeight/airTemp from the day summary and period as the mean of hourly readings", () => {
    const d = day(
      "2026-07-20",
      [hour("2026-07-20T06:00", 10, { period: 8 }), hour("2026-07-20T07:00", 10, { period: 10 })],
      { swell_max: 1.4, air_max: 22 }
    );
    const [result] = forecastToDetailBlocks(series([d]));
    expect(result.waveHeight).toBe(1.4);
    expect(result.airTemp).toBe(22);
    expect(result.wavePeriod).toBe(9);
  });
});

describe("forecastToHourly (Stundentabelle — raw hourly rows, all variables)", () => {
  it("carries every hour through unaggregated, in order", () => {
    const d = day("2026-07-20", [
      hour("2026-07-20T06:00", 10, { gust: 14, dir: 90, swell: 1.2, swell_dir: 250, period: 8, air: 18, sst: 19, precip: 0 }),
      hour("2026-07-20T07:00", 12, { gust: 16, dir: 95, swell: 1.3, swell_dir: 251, period: 8, air: 18.5, sst: 19, precip: 0.2 }),
    ]);
    const [result] = forecastToHourly(series([d]));
    expect(result.hours).toHaveLength(2);
    expect(result.hours[0]).toMatchObject({
      time: "06:00", hour: 6, wind: 10, gust: 14, dir: 90,
      waveHeight: 1.2, swellDir: 250, period: 8, air: 18, water: 19, precip: 0,
    });
    expect(result.hours[1].time).toBe("07:00");
  });

  it("leaves a missing variable null rather than fabricating a value", () => {
    const d = day("2026-07-20", [hour("2026-07-20T06:00", 10)]); // only wind set, rest default null
    const [result] = forecastToHourly(series([d]));
    const [row] = result.hours;
    expect(row.gust).toBeNull();
    expect(row.waveHeight).toBeNull();
    expect(row.water).toBeNull();
    expect(row.precip).toBeNull();
  });

  it("handles a day with no hours at all", () => {
    const d = day("2026-07-20", []);
    const [result] = forecastToHourly(series([d]));
    expect(result.hours).toEqual([]);
  });

  it("handles a short/incomplete day (fewer hours than a full 24h horizon) without padding it out", () => {
    const d = day("2026-07-20", [hour("2026-07-20T22:00", 8), hour("2026-07-20T23:00", 9)]);
    const [result] = forecastToHourly(series([d]));
    expect(result.hours).toHaveLength(2);
    expect(result.hours[0].hour).toBe(22);
    expect(result.hours[1].hour).toBe(23);
  });
});
