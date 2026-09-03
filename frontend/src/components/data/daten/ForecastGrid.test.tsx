import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import ForecastGrid from "./ForecastGrid";

function day(date: string, detail: "hourly" | "trend"): NormalizedForecastDay {
  const hour = {
    utcKey: `${date}T00:00:00Z`,
    localDate: date,
    localTime: "00:00",
    localHour: 0,
    localMinute: 0,
  } as NormalizedForecastHour;
  return {
    date,
    local_date: date,
    confidence: detail === "hourly" ? "hoch" : "mittel",
    confidenceSource: detail === "hourly" ? "spread" : "calendar",
    detail,
    summary: {
      wind_avg: 12,
      wind_max: 16,
      gust_max: 21,
      air_min: 14,
      air_max: 21,
      swell_max: 1.2,
      weather_condition: "partly_cloudy",
    },
    hours: detail === "hourly" ? [hour] : [],
  } as NormalizedForecastDay;
}

function forecast(days: NormalizedForecastDay[]): NormalizedForecastSeries {
  return {
    spot_id: "spot",
    model: "surfwinddata",
    generated_at: "2026-09-03T12:00:00Z",
    stale: false,
    timezone: "Europe/Berlin",
    timezoneStatus: { requested: "Europe/Berlin", effective: "Europe/Berlin", status: "valid" },
    availability: { atmosphere: "available", solar: "available", marine: "available" },
    diagnostics: [],
    days,
  } as NormalizedForecastSeries;
}

describe("ForecastGrid", () => {
  it("keeps the compact outlook and adds descriptions plus day navigation", () => {
    const days = Array.from({ length: 8 }, (_, index) =>
      day(`2026-09-${String(index + 3).padStart(2, "0")}`, index < 5 ? "hourly" : "trend"),
    );
    const data = forecast(days);
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider forecast={data}>
        <ForecastGrid forecast={data} />
      </SpotDataScopeProvider>,
    );

    expect((html.match(/<button(?: |\/?>)/g) ?? [])).toHaveLength(8);
    expect(html).toContain("Teils bewölkt");
    expect(html).toContain("Im Stundenforecast anzeigen");
    expect(html).not.toContain("Stärkster Wind");
    expect(html).not.toContain("Böen");
    expect(html).not.toContain("Sicherheit");
  });
});
