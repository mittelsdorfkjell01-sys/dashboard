import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ForecastDay, ForecastHour, ForecastSeries } from "../../../lib/api";
import { normalizeForecast } from "../../../lib/forecastNormalization";
import MeteogramDetailChart from "../MeteogramDetailChart";
import MeteogramLegend from "../MeteogramLegend";
import MeteogramTrend from "../MeteogramTrend";
import ForecastDataTable from "../ForecastDataTable";
import { buildMeteogramModel } from "../meteogramModel";
import { projectMeteogramView } from "../meteogramView";

const hour = (time: string, patch: Partial<ForecastHour> = {}): ForecastHour => ({ time, wind: null, gust: null, dir: null, air: null, swell: null, period: null, swell_dir: null, precip: null, sst: null, ...patch });
const summary = { wind_avg: 12, wind_max: 18, gust_max: 24, air_min: 9, air_max: 17, swell_max: null };
const day = (date: string, hours: ForecastHour[], detail: "hourly"|"trend"): ForecastDay => ({ date, detail, hours, confidence: "mittel", summary });
const source: ForecastSeries = { spot_id:"spot", model:"consensus", generated_at:"2026-08-23T00:00:00Z", timezone:"Europe/Berlin", availability:{atmosphere:"available",solar:"available",marine:"not_applicable_inland"}, days:[
  day("2026-08-23",[hour("2026-08-23T00:00:00Z",{wind:12,gust:18,dir:270,air:14,precip:3,wind_spread:{low:9,median:12,high:15,n:3}})],"hourly"),
  day("2026-08-28",[],"trend"),
] };

describe("Meteogram rendering grammar", () => {
  it("renders every visible legend shape and the selected local timestamp", () => {
    const model=buildMeteogramModel(normalizeForecast(source));
    const legend=renderToStaticMarkup(<MeteogramLegend/>);
    expect(legend).toContain("Mittelwind");
    expect(legend).toContain("Modellspanne");
    expect(legend).toContain("ausgewählter Zeitpunkt");
    expect(legend).toContain("keine Daten");
    const chart=renderToStaticMarkup(<MeteogramDetailChart model={model} selectedAtUtc={model.slots[0].utcKey} setSelectedAtUtc={()=>undefined} windUnit="kts"/>);
    expect(chart).toContain(model.slots[0].localTimeWithOffset);
    expect(chart).toContain("Sicherheit mittel");
    expect(chart).not.toContain("Wellenhöhe");
    expect(chart).not.toContain("Periode");
  });

  it("marks calendar-fallback confidence distinctly from spread-backed confidence", () => {
    const calendarSource: ForecastSeries = { ...source, days: [{ ...source.days[0], confidence_source: "calendar" } as ForecastDay, source.days[1]] };
    const chart = renderToStaticMarkup(<MeteogramDetailChart model={buildMeteogramModel(normalizeForecast(calendarSource))} selectedAtUtc={null} setSelectedAtUtc={()=>undefined} windUnit="kts"/>);
    expect(chart).toContain("Sicherheit mittel *");
  });

  it("renders trend days as summaries without hourly slots", () => {
    const model=buildMeteogramModel(normalizeForecast(source));
    const trend=renderToStaticMarkup(<MeteogramTrend days={model.trendDays} windUnit="kts"/>);
    expect(trend).toContain("Tagestrend · Tage 6–10");
    expect(trend).toContain("Tageswerte ohne scheinbare Stundenauflösung");
    expect(trend).not.toContain("02:00");
  });

  it("uses the same visible normalized values in the accessible table", () => {
    const model=buildMeteogramModel(normalizeForecast(source));
    const view=projectMeteogramView(model,0,"24h");
    const table=renderToStaticMarkup(<ForecastDataTable model={view} windUnit="kts"/>);
    expect(table).toContain("<caption");
    expect(table).toContain('scope="col"');
    expect(table).toContain('scope="row"');
    expect(table).toContain(view.slots[0].localTimeWithOffset);
    expect(table).toContain("12 kt");
    expect(table).toContain("9 kt bis 15 kt (3 Modelle)");
    expect(table).toContain("Nicht verfügbar");
  });
});
