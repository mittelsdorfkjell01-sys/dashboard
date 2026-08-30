import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Regression coverage for the rebuilt Daten page (Figma Frame 67): the dark
// instrument composition — meteogram, today summary + 8-day outlook, map +
// live-wind sidebar, wind-months field. Replaces the retired
// meteogram-accessibility / public-tides specs, whose subjects (hourly
// meteogram controls, data table, direction-compass card, tide panel) were
// intentionally removed in the rebuild.

const spot = { id: "test", slug: "laboe", name: "Alcyons", region_id: "r1", location: { lat: 54.4, lon: 10.2 }, sports: ["surf"], water_type: ["sea"], bottom_type: ["sand"], level: ["advanced"], water_character: ["welle_klein"], style: ["wave_riding"], facilities: null, status: "published", confidence: null, facing: 45, image: null, era5_cell: null, model_pref: null, editorial: { description: "Testspot" }, climatology: null, overrides: null, finish_rank: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-08-24T00:00:00Z" };
const conditions = ["clear", "partly_cloudy", "rain", "snow", "thunderstorm", "overcast", "drizzle", "mainly_clear"] as const;
const summary = (i: number) => ({ wind_avg: 12, wind_max: 18, gust_max: 24, air_min: 16 + i, air_max: 24 + i, swell_max: 1.8, apparent_temperature_max_c: 23, precipitation_sum_mm: 0.5, uv_index_max: 9, weather_condition: conditions[i % conditions.length] });
const hourly = Array.from({ length: 5 }, (_, day) => { const date = `2026-08-${String(24 + day).padStart(2, "0")}`; return { date, local_date: date, detail: "hourly", confidence: day < 2 ? "hoch" : "mittel", summary: summary(day), hours: Array.from({ length: 9 }, (_, slot) => { const h = slot * 2 + 6; return { time: `${date}T${String(h).padStart(2, "0")}:00:00Z`, wind: 8 + ((slot * 7) % 28), gust: 14 + ((slot * 7) % 28), dir: (180 + slot * 23) % 360, air: 17 + Math.round(6 * Math.sin(slot / 1.5)), precip: slot === 3 ? 0.4 : 0, swell: 0.4 + ((slot * 3) % 9) / 10, period: 7 + slot / 2, swell_dir: 270, sst: 18, uv_index: slot, apparent_temperature_c: 23, coastal_normal_deg: 180, coastal_classification: "onshore", weather_condition: conditions[slot % conditions.length], is_day: h >= 7 && h <= 20 }; }) }; });
const trend = Array.from({ length: 3 }, (_, day) => { const date = `2026-08-${String(29 + day).padStart(2, "0")}`; return { date, local_date: date, detail: "trend", confidence: "niedrig", summary: summary(day + 3), hours: [] }; });
const forecast = { spot_id: "test", model: "consensus", product: "Surfwinddata Forecast", generated_at: "2026-08-24T08:00:00Z", updated_at: "2026-08-24T08:00:00Z", timezone: "Europe/Berlin", stale: false, availability: { atmosphere: "available", solar: "available", marine: "available" }, days: [...hourly, ...trend] };

async function mockApi(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (["/spots/test", "/spots/laboe", "/spots/Alcyons"].includes(path)) return route.fulfill({ json: spot });
    if (path === "/regions/r1") return route.fulfill({ json: { id: "r1", slug: "kieler-bucht", name: "Kieler Bucht", country: "DE", center: null, description: null, image: null, season: null, defaults: null, status: "published", updated_at: "2026-08-24T00:00:00Z" } });
    if (path === "/spots/test/forecast") return route.fulfill({ json: forecast });
    if (path === "/spots/test/live") return route.fulfill({ json: { spot_id: "test", model: "consensus", time: "2026-08-24T12:00:00Z", current: { wind: 9, gust: 14, dir: 247, air: 23, sst: 18, swell: 2.5, period: 8, swell_dir: 250, coastal_normal_deg: 180, coastal_classification: "cross_onshore" } } });
    if (path === "/spots/test/tides") return route.fulfill({ status: 404, json: { detail: "none" } });
    if (path === "/spots/test/ratings") return route.fulfill({ json: { items: [], aggregate: { count: 0, average: null } } });
    if (path === "/spots/test/tips" || path === "/spots/test/images") return route.fulfill({ json: [] });
    if (path.startsWith("/spots/test/wind-climatology")) return route.fulfill({ status: 404, json: { detail: "none" } });
    return route.fulfill({ status: 404, json: { detail: `mock missing: ${path}` } });
  });
}

test("Daten-Seite zeigt Meteogramm, Ausblick und Livewind", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  // Meteogram row labels + the direction/time axes.
  await expect(page.getByText("WELLE", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("RICHT.", { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" })).toBeVisible();
  // 8-day outlook grid renders the weekday cards.
  await expect(page.getByText("MO 24.08", { exact: true })).toBeVisible();
  // Live-wind sidebar metrics.
  await expect(page.getByText("UV INDEX", { exact: true })).toBeVisible();
  await expect(page.getByText("GEFÜHLT", { exact: true })).toBeVisible();
});

for (const width of [320, 375, 768, 1280, 1440]) {
  test(`Daten-Seite bleibt bei ${width}px innerhalb der Seite`, async ({ page }) => {
    await page.setViewportSize({ width, height: width < 500 ? 720 : 900 });
    await mockApi(page);
    await page.goto("/spot/test/daten");
    await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test("Meteogramm-Auswahl per Pointer aktualisiert die geteilte Auswahl", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  const strip = page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" });
  await strip.click({ position: { x: 30, y: 90 } });
  // The live-region summary reflects a concrete selected hour.
  await expect(page.getByText(/Ausgewählt 2026-08-24/)).toBeAttached();
});

test("Daten-Seite ist axe-konform (mobil)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
