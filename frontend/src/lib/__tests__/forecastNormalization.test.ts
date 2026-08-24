import { describe, expect, it, vi } from "vitest";
import type { ForecastDay, ForecastHour, ForecastSeries } from "../api";
import { closestForecastUtc, normalizeForecast, selectedForecastHour } from "../forecastNormalization";

const baseHour = (time: string, patch: Partial<ForecastHour> = {}): ForecastHour => ({
  time, wind: 12, gust: 16, dir: 270, air: 18, swell: 1.2, period: 8,
  swell_dir: 250, precip: 0, sst: 17, ...patch,
});
const baseDay = (date: string, hours: ForecastHour[], detail: ForecastDay["detail"] = "hourly"): ForecastDay => ({
  date, local_date: date, confidence: "hoch", detail, hours,
  summary: { wind_avg: null, wind_max: null, gust_max: null, air_min: null, air_max: null, swell_max: null },
});
const series = (timezone: string, days: ForecastDay[]): ForecastSeries => ({
  spot_id: "spot", model: "consensus", generated_at: "2026-01-01T00:00:00Z", timezone, days,
});

describe("forecast UTC identity and spot-local display", () => {
  it.each([
    ["UTC", "2026-01-01T12:00:00Z", "12:00"],
    ["Pacific/Kiritimati", "2026-01-01T12:00:00Z", "02:00"],
    ["America/New_York", "2026-01-01T12:00:00Z", "07:00"],
    ["Etc/GMT+8", "2026-01-01T12:00:00Z", "04:00"],
  ])("formats %s without using the browser timezone", (timezone, instant, localTime) => {
    vi.stubEnv("TZ", "Asia/Tokyo");
    const normalized = normalizeForecast(series(timezone, [baseDay("2026-01-01", [baseHour(instant)])]));
    expect(normalized.days[0].hours[0].localTime).toBe(localTime);
    expect(normalized.days[0].hours[0].utcKey).toBe(new Date(instant).toISOString());
    vi.unstubAllEnvs();
  });

  it("handles the Europe/Berlin DST gap using real UTC instants", () => {
    const normalized = normalizeForecast(series("Europe/Berlin", [baseDay("2026-03-29", [
      baseHour("2026-03-29T00:00:00Z"), baseHour("2026-03-29T01:00:00Z"),
    ])]));
    expect(normalized.days[0].hours.map((hour) => hour.localTime)).toEqual(["01:00", "03:00"]);
  });

  it("keeps both Europe/Berlin DST-fold instants distinguishable", () => {
    const normalized = normalizeForecast(series("Europe/Berlin", [baseDay("2026-10-25", [
      baseHour("2026-10-25T00:30:00Z"), baseHour("2026-10-25T01:30:00Z"),
    ])]));
    const hours = normalized.days[0].hours;
    expect(hours.map((hour) => hour.localTime)).toEqual(["02:30", "02:30"]);
    expect(hours[0].utcKey).not.toBe(hours[1].utcKey);
    expect(hours[0].localTimeWithOffset).not.toBe(hours[1].localTimeWithOffset);
    expect(selectedForecastHour(normalized, hours[1].utcKey)).toBe(hours[1]);
  });

  it("falls back diagnostically to UTC for an invalid IANA timezone", () => {
    const normalized = normalizeForecast(series("Mars/Olympus", [baseDay("2026-01-01", [baseHour("2026-01-01T01:00:00Z")])]));
    expect(normalized.timezoneStatus).toEqual({ requested: "Mars/Olympus", effective: "UTC", status: "fallback_utc" });
    expect(normalized.days[0].hours[0].localTime).toBe("01:00");
    expect(normalized.diagnostics.some((item) => item.code === "invalid_timezone")).toBe(true);
  });
});

describe("forecast validation", () => {
  it("sorts unique UTC instants and drops duplicates without inventing slots", () => {
    const normalized = normalizeForecast(series("UTC", [baseDay("2026-01-01", [
      baseHour("2026-01-01T02:00:00Z"), baseHour("2026-01-01T01:00:00Z"), baseHour("2026-01-01T01:00:00+00:00"),
    ])]));
    expect(normalized.days[0].hours.map((hour) => hour.utcKey)).toEqual([
      "2026-01-01T01:00:00.000Z", "2026-01-01T02:00:00.000Z",
    ]);
    expect(normalized.diagnostics.map((item) => item.code)).toEqual(expect.arrayContaining(["unsorted_timestamp", "duplicate_timestamp"]));
  });

  it("orders unsorted days and their actual slots without filling calendar gaps", () => {
    const normalized=normalizeForecast(series("UTC",[
      baseDay("2026-01-03",[baseHour("2026-01-03T06:00:00Z")]),
      baseDay("2026-01-01",[baseHour("2026-01-01T09:00:00Z")]),
    ]));
    expect(normalized.days.map((day)=>day.date)).toEqual(["2026-01-01","2026-01-03"]);
    expect(normalized.days).toHaveLength(2);
  });

  it("rejects non-finite, negative, directional and relational violations per field", () => {
    const normalized = normalizeForecast(series("UTC", [baseDay("2026-01-01", [baseHour("2026-01-01T00:00:00Z", {
      wind: Number.NaN, gust: Number.POSITIVE_INFINITY, dir: 360, precip: -1, swell: -2,
      wind_spread: { low: 15, median: 10, high: 20, n: 1 },
    })])]));
    const hour = normalized.days[0].hours[0];
    expect(hour).toMatchObject({ wind: null, gust: null, dir: null, precip: null, swell: null, wind_spread: null });
    expect(normalized.diagnostics.length).toBeGreaterThanOrEqual(6);
  });

  it("marks a gust below mean wind unavailable", () => {
    const normalized = normalizeForecast(series("UTC", [baseDay("2026-01-01", [baseHour("2026-01-01T00:00:00Z", { wind: 20, gust: 15 })])]));
    expect(normalized.days[0].hours[0].wind).toBe(20);
    expect(normalized.days[0].hours[0].gust).toBeNull();
    expect(normalized.diagnostics.some((item) => item.code === "gust_below_wind")).toBe(true);
  });

  it("passes through a valid confidence_source and rejects an unknown one",()=>{
    const valid={...baseDay("2026-01-01",[baseHour("2026-01-01T00:00:00Z")]),confidence_source:"spread"} as ForecastDay;
    const invalid={...baseDay("2026-01-02",[baseHour("2026-01-02T00:00:00Z")]),confidence_source:"guessed"} as unknown as ForecastDay;
    const normalized=normalizeForecast(series("UTC",[valid,invalid]));
    expect(normalized.days[0].confidenceSource).toBe("spread");
    expect(normalized.days[1].confidenceSource).toBeNull();
    expect(normalized.diagnostics.some((item)=>item.code==="invalid_confidence_source")).toBe(true);
  });

  it("passes through the calibrated flag unchanged",()=>{
    const normalized=normalizeForecast({...series("UTC",[baseDay("2026-01-01",[baseHour("2026-01-01T00:00:00Z")])]),calibrated:true});
    expect(normalized.calibrated).toBe(true);
  });

  it("sanitizes non-finite, negative and contradictory daily summaries",()=>{
    const input=baseDay("2026-01-01",[],"trend");
    input.summary={...input.summary,wind_avg:Number.NaN,wind_max:20,gust_max:15,swell_max:-1,air_min:10,air_max:5,precipitation_sum_mm:Number.POSITIVE_INFINITY};
    const normalized=normalizeForecast(series("UTC",[input]));
    expect(normalized.days[0].summary).toMatchObject({wind_avg:null,gust_max:null,swell_max:null,air_min:null,air_max:null,precipitation_sum_mm:null});
    expect(normalized.diagnostics.some((item)=>item.code==="gust_below_wind")).toBe(true);
  });

  it("keeps incomplete and trend days without adding days or hours", () => {
    const normalized = normalizeForecast(series("UTC", [
      baseDay("2026-01-01", [baseHour("2026-01-01T00:00:00Z")]),
      baseDay("2026-01-02", [], "trend"),
    ]));
    expect(normalized.days).toHaveLength(2);
    expect(normalized.days[0].hours).toHaveLength(1);
    expect(normalized.days[1]).toMatchObject({ detail: "trend", hours: [] });
  });

  it("chooses the nearest actual forecast instant", () => {
    const normalized = normalizeForecast(series("UTC", [baseDay("2026-01-01", [
      baseHour("2026-01-01T00:00:00Z"), baseHour("2026-01-01T03:00:00Z"),
    ])]));
    expect(closestForecastUtc(normalized, Date.parse("2026-01-01T02:20:00Z"))).toBe("2026-01-01T03:00:00.000Z");
  });
});
