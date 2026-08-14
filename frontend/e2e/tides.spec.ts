import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const spot = {
  id: "test", slug: "laboe", name: "Laboe", region_id: "r1",
  location: { lat: 54.4, lon: 10.2 }, sports: ["surf"],
  water_type: ["sea"], bottom_type: ["sand"], level: ["advanced"],
  water_character: ["welle_klein"], style: ["wave_riding"], facilities: null,
  status: "published", confidence: null, facing: 45, image: null,
  era5_cell: null, model_pref: null, editorial: { description: "Testspot" },
  climatology: null, overrides: null, finish_rank: null,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-08-06T00:00:00Z",
};

async function mockApi(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    // The legacy reference resolves once, then the page canonicalizes to the
    // public display-name URL without losing the already-supported old link.
    if (["/spots/test", "/spots/Laboe"].includes(url.pathname)) {
      return route.fulfill({ json: spot });
    }
    if (url.pathname === "/regions/r1") return route.fulfill({ json: {
      id: "r1", slug: "kieler-bucht", name: "Kieler Bucht", country: "DE",
      center: null, description: null, image: null, season: null, defaults: null,
      status: "published", updated_at: "2026-08-06T00:00:00Z",
    }});
    if (url.pathname === "/spots/test/tides") return route.fulfill({ json: {
      available: true, message: null, timezone: "Europe/Berlin", phase: "rising",
      cycle_position: 0.48, quality: "reviewed_anchor", approximate: true,
      last_calculated_at: "2026-08-06T08:00:00Z",
      valid_until: "2026-10-05T00:00:00Z",
      events: [
        { id: "e1", event_type: "high", time: "2026-08-06T12:20:00Z", uncertainty_minutes: 10 },
        { id: "e2", event_type: "low", time: "2026-08-06T18:30:00Z", uncertainty_minutes: 20 },
        { id: "e3", event_type: "high", time: "2026-08-07T00:40:00Z", uncertainty_minutes: 10 },
      ],
    }});
    if (url.pathname === "/spots/test/live") return route.fulfill({ status: 404, json: { detail: "none" } });
    if (url.pathname === "/spots/test/forecast") return route.fulfill({ json: { spot_id: "test", model: "test", generated_at: "2026-08-06T08:00:00Z", days: [] } });
    if (url.pathname === "/spots/test/ratings") return route.fulfill({ json: { items: [], aggregate: { count: 0, average: null } } });
    if (url.pathname === "/spots/test/tips" || url.pathname === "/spots/test/images") return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: { detail: "mock missing" } });
  });
}

test("public tide panel is readable and accessible", async ({ page }) => {
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByText("Gezeiten · 24 h", { exact: true })).toBeVisible();
  await expect(page.getByText("Steigend", { exact: true })).toBeVisible();
  await expect(page.getByText("ca. 14:20", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("ca. 20:10–20:50", { exact: true }).first()).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});

test("public tide panel has no mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByText("Steigend", { exact: true })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
