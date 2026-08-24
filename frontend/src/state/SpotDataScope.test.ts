import { describe,expect,it } from "vitest";
import type { NormalizedForecastHour } from "../lib/forecastNormalization";
import { resolveForecastSelection } from "./SpotDataScope";

const hours=["2026-08-24T00:00:00.000Z","2026-08-24T03:00:00.000Z","2026-08-24T09:00:00.000Z"].map((utcKey)=>({utcKey} as NormalizedForecastHour));

describe("central forecast selection",()=>{
  it("keeps exact UTC identities and resolves missing instants to the nearest real slot",()=>{
    expect(resolveForecastSelection(hours,hours[1].utcKey)).toBe(hours[1].utcKey);
    expect(resolveForecastSelection(hours,"2026-08-24T05:00:00.000Z")).toBe(hours[1].utcKey);
  });
  it("uses the nearest real slot for invalid or empty requests",()=>{
    expect(resolveForecastSelection(hours,"invalid",Date.parse("2026-08-24T08:30:00Z"))).toBe(hours[2].utcKey);
    expect(resolveForecastSelection([],null)).toBeNull();
  });
});
