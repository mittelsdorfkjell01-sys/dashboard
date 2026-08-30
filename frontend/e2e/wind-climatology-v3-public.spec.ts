import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const spot = {
  id: "test", slug: "laboe", name: "Laboe", region_id: "r1",
  location: { lat: 54.4, lon: 10.2 }, sports: ["wind"],
  water_type: ["sea"], bottom_type: ["sand"], level: ["advanced"],
  water_character: ["welle_klein"], style: ["wave_riding"], facilities: null,
  status: "published", confidence: null, facing: 45, image: null,
  era5_cell: null, model_pref: null, editorial: { description: "Testspot" },
  climatology: null, overrides: null, finish_rank: null,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-08-06T00:00:00Z",
};

const region = {
  id: "r1", slug: "kieler-bucht", name: "Kieler Bucht", country: "DE",
  center: null, description: null, image: null, season: null, defaults: null,
  status: "published", updated_at: "2026-08-06T00:00:00Z",
};

function pad(n: number) { return String(n).padStart(2, "0"); }

function week(index: number, reliability: number | null) {
  const date = new Date(2000, 0, 1 + index * 7);
  const end = new Date(2000, 0, 7 + index * 7);
  return {
    week: index + 1,
    date_range: { start: `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`, end: `${pad(end.getMonth() + 1)}-${pad(end.getDate())}` },
    sample_years: 19,
    successful_years: reliability == null ? 0 : Math.round((reliability / 100) * 19),
    reliability_percent: reliability,
    reliability_low_percent: reliability == null ? null : Math.max(0, reliability - 20),
    reliability_high_percent: reliability == null ? null : Math.min(100, reliability + 20),
    probability_at_least_1_day: reliability,
    probability_at_least_2_days: reliability,
    probability_at_least_3_days: reliability,
    median_usable_days: reliability == null ? null : 2,
    median_session_hours: reliability == null ? null : 9,
    p25_session_hours: reliability == null ? null : 5,
    p75_session_hours: reliability == null ? null : 14,
    median_longest_session: reliability == null ? null : 4,
    quality_status: reliability == null ? "insufficient" : "high",
  };
}

function v3Payload(overrides: Partial<{ minWindKn: number; maxWindKn: number | null; directionMode: "all" | "usable"; usableAvailable: boolean }> = {}) {
  const minWindKn = overrides.minWindKn ?? 15;
  const maxWindKn = overrides.maxWindKn === undefined ? 20 : overrides.maxWindKn;
  const directionMode = overrides.directionMode ?? "all";
  const usableAvailable = overrides.usableAvailable ?? true;
  const weeks = Array.from({ length: 52 }, (_, i) => week(i, i >= 20 && i < 35 ? 70 : i === 0 ? 0 : 40));
  return {
    status: "ready",
    algorithm_version: "wind-climatology-v3.0",
    period: [2006, 2025],
    model: "ERA5",
    wind_height_m: 10,
    grid_resolution_degrees: 0.25,
    default_window: { min_wind_kn: 15, max_wind_kn: 20 },
    direction: { usable_available: usableAvailable, description: usableAvailable ? "WSW bis NW" : null, selected_mode: directionMode },
    selection: { min_wind_kn: minWindKn, max_wind_kn: maxWindKn, direction_mode: directionMode },
    weeks,
    best_season: { start_week: 21, end_week: 35, start_date: "05-22", end_date: "08-28" },
    data_quality: "high",
    updated_at: "2026-08-01T00:00:00Z",
    attribution: "Open-Meteo / ERA5",
  };
}

async function baseRoutes(page: Page, opts: { v3: "ready" | "404"; usableAvailable?: boolean }) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (["/spots/test", "/spots/laboe", "/spots/Laboe"].includes(url.pathname)) return route.fulfill({ json: spot });
    if (url.pathname === "/regions/r1") return route.fulfill({ json: region });
    if (url.pathname === "/spots/test/live") return route.fulfill({ status: 404, json: { detail: "none" } });
    if (url.pathname === "/spots/test/forecast") return route.fulfill({ json: { spot_id: "test", model: "test", generated_at: "2026-08-06T08:00:00Z", days: [] } });
    if (url.pathname === "/spots/test/ratings") return route.fulfill({ json: { items: [], aggregate: { count: 0, average: null } } });
    if (url.pathname === "/spots/test/tips" || url.pathname === "/spots/test/images") return route.fulfill({ json: [] });
    if (url.pathname === "/spots/test/tides") return route.fulfill({ json: { available: false, message: null, timezone: "Europe/Berlin", phase: null, cycle_position: null, quality: null, approximate: true, last_calculated_at: null, valid_until: null, events: [] } });
    if (url.pathname === "/spots/test/wind-climatology") {
      return route.fulfill({ json: { status: "ready", period: { start_year: 2006, end_year: 2025 }, model: "ERA5", wind_height_m: 10, updated_at: "2026-08-01", grid: { resolution_degrees: 0.25 }, sections: [] } });
    }
    if (url.pathname === "/spots/test/wind-climatology-v3") {
      if (opts.v3 === "404") return route.fulfill({ status: 404, json: { detail: "Wind climatology V3 not available for this spot" } });
      const minWindKn = Number(url.searchParams.get("min_wind_kn") ?? 15);
      const openUpper = url.searchParams.get("open_upper") === "true";
      const maxWindKnRaw = url.searchParams.get("max_wind_kn");
      const maxWindKn = openUpper ? null : maxWindKnRaw ? Number(maxWindKnRaw) : 20;
      const directionMode = (url.searchParams.get("direction_mode") ?? "all") as "all" | "usable";
      if (directionMode === "usable" && opts.usableAvailable === false) {
        return route.fulfill({ status: 422, json: { detail: "usable direction mode requires reviewed direction windows for this spot" } });
      }
      return route.fulfill({ json: v3Payload({ minWindKn, maxWindKn, directionMode, usableAvailable: opts.usableAvailable ?? true }) });
    }
    return route.fulfill({ status: 404, json: { detail: "mock missing" } });
  });
}

test("V3 module loads with the default 15–20 kt window and matching selection summary", async ({ page }) => {
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  await expect(page.getByText("Wann ist regelmäßig Wind?")).toBeVisible();
  await expect(page.getByText("15–20 kt · passende Richtung · 2006–2025")).toBeVisible();
});

test("changing the preset updates the URL and the selection summary", async ({ page }) => {
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  await expect(page.getByText("15–20 kt · passende Richtung · 2006–2025")).toBeVisible();
  await page.getByRole("button", { name: "20–30 kt", exact: true }).click();
  await expect(page.getByText("20–30 kt · passende Richtung · 2006–2025")).toBeVisible();
  await expect(page).toHaveURL(/wind_min=20&wind_max=30/);
});

test("turning off the direction filter switches to alle Richtungen", async ({ page }) => {
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  // The direction filter lives inside the collapsible "Anpassen" panel.
  await page.getByRole("button", { name: /Anpassen/ }).click();
  const toggle = page.getByLabel("Passende Windrichtung berücksichtigen");
  await expect(toggle).toBeChecked();
  // Controlled checkbox: its state only flips once the re-fetch resolves, so
  // click and wait on the resulting summary rather than uncheck()'s eager check.
  await toggle.click();
  await expect(page.getByText("15–20 kt · alle Richtungen · 2006–2025")).toBeVisible();
  await expect(page).toHaveURL(/wind_dir=all/);
});

test("a spot without reviewed directions disables the filter and shows the explanatory note", async ({ page }) => {
  await baseRoutes(page, { v3: "ready", usableAvailable: false });
  await page.goto("/spot/test/daten");
  await expect(page.getByText("15–20 kt · alle Richtungen · 2006–2025")).toBeVisible();
  // The direction filter lives inside the collapsible "Anpassen" panel.
  await page.getByRole("button", { name: /Anpassen/ }).click();
  await expect(page.getByLabel("Passende Windrichtung berücksichtigen")).toBeDisabled();
  await expect(page.getByText("Für diesen Spot sind noch keine geprüften Windrichtungen hinterlegt.")).toBeVisible();
});

test("selecting a week shows its detail values below the chart", async ({ page }) => {
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  const bar = page.locator('[data-week="30"]');
  await bar.click();
  await expect(page.getByText("Wochendetail")).toBeVisible();
  await expect(page.getByText("Zuverlässigkeit", { exact: true }).locator("..").getByText("70%", { exact: true })).toBeVisible();
});

test("a spot without an active V3 run falls back to the V2 climatology view", async ({ page }) => {
  await baseRoutes(page, { v3: "404" });
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Windmonate" })).toBeVisible();
  await expect(page.getByText("Wann ist regelmäßig Wind?")).not.toBeVisible();
});

test("mobile: chart keeps the complete year visible and the page never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  await expect(page.getByText("Wann ist regelmäßig Wind?")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("chart supports keyboard week selection without 52 tab stops", async ({ page }) => {
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  const chart = page.getByRole("slider", { name: /52 Wochen Windzuverlässigkeit/ });
  await expect(chart).toBeVisible();
  await chart.focus();
  await page.keyboard.press("Home");
  await expect(chart).toHaveAttribute("aria-valuenow", "1");
  await page.keyboard.press("ArrowRight");
  await expect(chart).toHaveAttribute("aria-valuenow", "2");
  await expect(page.locator('[data-week][tabindex]')).toHaveCount(0);
});

test("V3 module has no serious/critical accessibility violations", async ({ page }) => {
  await baseRoutes(page, { v3: "ready" });
  await page.goto("/spot/test/daten");
  await expect(page.getByText("Wann ist regelmäßig Wind?")).toBeVisible();
  const results = await new AxeBuilder({ page }).include('[aria-label*="52 Wochen"]').analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
