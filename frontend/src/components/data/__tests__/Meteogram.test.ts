import { describe, expect, it } from "vitest";
import type { ForecastDay, ForecastHour, ForecastSeries } from "../../../lib/api";
import { normalizeForecast } from "../../../lib/forecastNormalization";
import { buildMeteogramModel, hasValidSpread, marineStatusText } from "../meteogramModel";

const hour = (time: string, patch: Partial<ForecastHour> = {}): ForecastHour => ({
  time, wind: null, gust: null, dir: null, air: null, swell: null,
  period: null, swell_dir: null, precip: null, sst: null, ...patch,
});
const day = (date: string, hours: ForecastHour[], detail: "hourly" | "trend" = "hourly"): ForecastDay => ({
  date, confidence: "hoch", hours, detail,
  summary: { wind_avg: null, wind_max: null, gust_max: null, air_min: null, air_max: null, swell_max: null },
});
const forecast = (days: ForecastDay[], timezone = "UTC", marine: ForecastSeries["availability"] = { atmosphere: "available", solar: "available", marine: "available" }): ForecastSeries => ({
  spot_id: "spot", model: "consensus", generated_at: "2026-08-23T00:00:00Z", timezone, days, availability: marine,
});

describe("Meteogram data model", () => {
  it.each([
    ["kein Wind",null,null,null,20],
    ["sehr schwach",0.4,0.8,null,1],
    ["typisch",16,22,null,50],
    ["starke Böe",20,63,null,100],
    ["Spanne über Böe",20,30,{low:15,median:20,high:74,n:4},100],
  ] as const)("bildet die Windskala für %s aus allen relevanten Werten",(_label,wind,gust,wind_spread,max)=>{
    const model=buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23",[hour("2026-08-23T00:00:00Z",{wind,gust,wind_spread})])])));
    expect(model.scales.wind.max).toBe(max);
  });

  it("keeps a constant temperature on a finite visible range",()=>{
    const model=buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23",[hour("2026-08-23T00:00:00Z",{air:15}),hour("2026-08-23T03:00:00Z",{air:15})])])));
    expect(model.scales.temperature).toEqual({min:10,mid:15,max:20});
  });

  it("sizes every scale from all valid detail values including gust and spread high", () => {
    const model = buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23", [
      hour("2026-08-23T00:00:00Z", { air: -7, precip: 1, wind: 28, gust: 42, wind_spread: { low: 22, median: 28, high: 47, n: 4 }, swell: 4.6, period: 13 }),
      hour("2026-08-23T03:00:00Z", { air: 38, precip: 50, wind: 12 }),
    ])])));
    expect(model.scales.temperature).toEqual({ min: -10, mid: 15, max: 40 });
    expect(model.scales.wind).toEqual({ min: 0, mid: 25, max: 50 });
    expect(model.scales.wave).toEqual({ min: 0, mid: 2.5, max: 5 });
    expect(model.scales.precipitation).toEqual({ min: 0, mid: 25, max: 50 });
  });

  it("keeps 1, 3, 10 and 50 mm/h distinct without a hidden cap", () => {
    const model = buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23", [1,3,10,50].map((precip,index)=>hour(`2026-08-23T${String(index*3).padStart(2,"0")}:00:00Z`,{precip})))])));
    expect(model.scales.precipitation.max).toBe(50);
    expect(new Set([1,3,10,50].map((value)=>value/model.scales.precipitation.max)).size).toBe(4);
  });

  it("breaks temperature paths at missing values and actual time gaps", () => {
    const model = buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23", [
      hour("2026-08-23T00:00:00Z",{air:10}), hour("2026-08-23T03:00:00Z",{air:null}),
      hour("2026-08-23T06:00:00Z",{air:12}), hour("2026-08-23T12:00:00Z",{air:14}),
    ])])));
    expect(model.temperatureSegments.map((segment)=>segment.map((slot)=>slot.utcKey))).toEqual([
      ["2026-08-23T00:00:00.000Z"], ["2026-08-23T06:00:00.000Z"], ["2026-08-23T12:00:00.000Z"],
    ]);
  });

  it("uses only real hourly days and keeps trend days without synthetic slots", () => {
    const model = buildMeteogramModel(normalizeForecast(forecast([
      day("2026-08-23",[hour("2026-08-23T00:00:00Z")]),
      day("2026-08-28",[],"trend"), day("2026-08-29",[],"trend"),
    ])));
    expect(model.slots).toHaveLength(1);
    expect(model.trendDays.map((item)=>item.date)).toEqual(["2026-08-28","2026-08-29"]);
  });

  it("shows model spread only for an ordered band from at least two models", () => {
    const normalized = normalizeForecast(forecast([day("2026-08-23",[
      hour("2026-08-23T00:00:00Z",{wind:10,wind_spread:{low:8,median:10,high:14,n:2}}),
      hour("2026-08-23T03:00:00Z",{wind:10,wind_spread:{low:8,median:10,high:14,n:1}}),
    ])]));
    expect(hasValidSpread(normalized.days[0].hours[0])).toBe(true);
    expect(hasValidSpread(normalized.days[0].hours[1])).toBe(false);
  });

  it("does not render fake marine rows and explains the concrete status", () => {
    const model = buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23",[hour("2026-08-23T00:00:00Z")])],"UTC",{atmosphere:"available",solar:"available",marine:"not_applicable_inland"})));
    expect(model.showMarine).toBe(false);
    expect(marineStatusText(model.marineStatus)).toContain("Binnen-Spot");
  });

  it.each([
    ["available",true],["available_stale",true],["not_applicable_inland",false],["unavailable_provider",false],
  ] as const)("handles marine status %s",(marine,expected)=>{
    const model=buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23",[hour("2026-08-23T00:00:00Z",{swell:6.4,period:14})])],"UTC",{atmosphere:"available",solar:"available",marine})));
    expect(model.showMarine).toBe(expected);
    expect(model.scales.wave.max).toBe(10);
  });

  it("keeps missing precipitation and waves unavailable rather than zero",()=>{
    const model=buildMeteogramModel(normalizeForecast(forecast([day("2026-08-23",[hour("2026-08-23T00:00:00Z",{precip:null,swell:null})])])));
    expect(model.slots[0]).toMatchObject({precip:null,swell:null});
  });
});
