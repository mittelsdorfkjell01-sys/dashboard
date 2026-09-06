import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import ForecastGrid from "./ForecastGrid";
import { tempColor, COLDEST_TEMP_COLOR } from "../../../lib/tempScale";

function day(date: string, detail: "hourly" | "trend"): NormalizedForecastDay {
  const hour = {
    utcKey: `${date}T06:00:00Z`,
    localDate: date,
    localTime: "06:00",
    localHour: 6,
    localMinute: 6 * 60,
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
  it("shows a compact 10-day outlook without horizontal scrolling", () => {
    const days = Array.from({ length: 12 }, (_, index) =>
      day(`2026-09-${String(index + 3).padStart(2, "0")}`, index < 5 ? "hourly" : "trend"),
    );
    const data = forecast(days);
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider forecast={data}>
        <ForecastGrid forecast={data} />
      </SpotDataScopeProvider>,
    );

    expect((html.match(/<button(?: |\/?>)/g) ?? [])).toHaveLength(10);
    expect(html).toContain("grid-cols-5");
    expect(html).not.toContain("overflow-x-auto");
    expect(html).toContain("12.09");
    expect(html).not.toContain("13.09");
    expect(html).toContain("Teils bewölkt");
    expect(html).toContain("Im Stundenforecast anzeigen");
    expect(html).not.toContain("Stärkster Wind");
    expect(html).not.toContain("Böen");
    expect(html).not.toContain("Sicherheit");
  });

  it("tints high and low temps on one absolute scale with a ° unit", () => {
    const data = forecast([day("2026-09-03", "hourly")]); // air_max 21, air_min 14
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider forecast={data}>
        <ForecastGrid forecast={data} />
      </SpotDataScopeProvider>,
    );

    // Degree circle, no more C suffix.
    expect(html).toContain("21°");
    expect(html).toContain("14°");
    expect(html).not.toContain("21C");
    expect(html).not.toContain("14C");
    // High tinted by its value on the absolute scale; low always the coolest tone.
    expect(html).toContain(tempColor(21)); // high (21 °C)
    expect(html).toContain(COLDEST_TEMP_COLOR); // low always coolest
    expect(html).not.toContain(tempColor(14)); // low is NOT tinted by its own value
    // High primary (semibold, full colour), low secondary (normal weight, dimmed).
    expect(html).toContain("font-semibold");
    expect(html).toContain("opacity:0.78");
  });
});
