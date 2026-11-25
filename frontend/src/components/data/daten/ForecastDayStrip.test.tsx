import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "../../../lib/forecastNormalization";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import ForecastDayStrip, { ForecastDayStripSkeleton } from "./ForecastDayStrip";

function hour(date: string, h: number, wind: number): NormalizedForecastHour {
  return {
    utcKey: `${date}T${String(h).padStart(2, "0")}:00:00Z`,
    localDate: date,
    localTime: `${String(h).padStart(2, "0")}:00`,
    localHour: h,
    localMinute: h * 60,
    wind,
  } as NormalizedForecastHour;
}

function day(date: string): NormalizedForecastDay {
  // Even local hours 06..22 inside the spot display window → the mini bars.
  const hours = Array.from({ length: 9 }, (_, i) => hour(date, 6 + i * 2, 8 + i));
  return {
    date,
    local_date: date,
    confidence: "hoch",
    confidenceSource: "spread",
    detail: "hourly",
    summary: { wind_avg: 12, wind_max: 16, gust_max: 21, air_min: 14, air_max: 21, swell_max: 1.2, weather_condition: "partly_cloudy" },
    hours,
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

describe("ForecastDayStrip", () => {
  it("renders ten clickable hourly days with weekday+date captions and real mini bars", () => {
    const days = Array.from({ length: 12 }, (_, index) =>
      day(`2026-09-${String(index + 3).padStart(2, "0")}`),
    );
    const data = forecast(days);
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider forecast={data}>
        <ForecastDayStrip forecast={data} />
      </SpotDataScopeProvider>,
    );

    // The backend may never exceed ten days, and the UI keeps the same cap if
    // an invalid oversized response reaches the browser.
    expect((html.match(/<button(?: |\/?>)/g) ?? [])).toHaveLength(10);
    expect(html).toContain("Im Stundenforecast anzeigen");
    // All ten days in one row at every width — no sideways scrolling.
    expect(html).toContain("grid-cols-10");
    expect(html).not.toContain("overflow-x-auto");
    // Weekday + date caption (2026-09-03 is a Thursday → "DO 03.09.").
    expect(html).toContain("03.09.");
    // One bar per hour of the spot window (06…20) per day — one continuous band.
    expect((html.match(/data-wind-bar/g) ?? [])).toHaveLength(10 * 15);
  });

  it("still renders all fifteen bars for a day already in progress (missing early hours)", () => {
    // A day whose forecast only starts at 14:00 — its 06..12 slots have no data.
    const partial: NormalizedForecastDay = {
      ...day("2026-09-05"),
      hours: [16, 18, 20].map((h) => hour("2026-09-05", h, 12 + h)),
    } as NormalizedForecastDay;
    const data = forecast([partial]);
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider forecast={data}>
        <ForecastDayStrip forecast={data} />
      </SpotDataScopeProvider>,
    );

    // Fifteen bars regardless of how many hours the day carries.
    expect((html.match(/data-wind-bar/g) ?? [])).toHaveLength(15);
  });

  it("shows the total wave per hour in the wave focus, in the sea's colour", () => {
    const withWaves = (date: string) => {
      const base = day(date);
      return {
        ...base,
        hours: base.hours.map((h, i) => ({ ...h, waves: { total_wave: { significant_height_m: 0.4 + i * 0.1 } } })),
      } as NormalizedForecastDay;
    };
    const data = forecast([withWaves("2026-09-03"), withWaves("2026-09-04")]);
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider forecast={data}>
        <ForecastDayStrip forecast={data} focus="wave" />
      </SpotDataScopeProvider>,
    );
    expect(html).toContain("var(--sw-data-swell)");
    // The day's peak is spelled in metres, not knots: the band's last slot
    // is 20:00, where the sample reaches 1.1 m.
    expect(html).toMatch(/bis 1,1 m/);
    expect(html).not.toMatch(/bis \d+ kn/);
  });

  it("holds its final size while loading", () => {
    const html = renderToStaticMarkup(<ForecastDayStripSkeleton />);
    expect((html.match(/grid-cols-10/g) ?? []).length).toBe(1);
    // Ten days of fifteen placeholder bars, the same band height as the real one.
    expect((html.match(/flex-1 rounded-t/g) ?? [])).toHaveLength(150);
    expect(html).toContain("height:42px");
  });
});
