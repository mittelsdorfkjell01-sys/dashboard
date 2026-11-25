import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const result = {
  resolved: "entities",
  regionen: [],
  spots: [
    {
      id: "s1",
      slug: "laboe",
      name: "Laboe",
      location: { lat: 54.4, lon: 10.2 },
      sports: ["windsurf"],
      score: 0.82,
    },
  ],
  treffer: 1,
};

const catalogueSpot = {
  id: "s1",
  slug: "laboe",
  name: "Laboe",
  region_id: null,
  region_name: "Kieler Bucht",
  region_country: "DE",
  location: { lat: 54.4, lon: 10.2 },
  sports: ["windsurf"],
  water_type: [],
  bottom_type: [],
  level: [],
  water_character: [],
  style: [],
  facilities: null,
  status: "published",
  facing: null,
  image: null,
  typical_wind_kt: null,
  typical_wave_height_m: null,
  wind_availability: null,
};

async function mockSearchDependencies(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/(?:spots|regions|live)(?:\/|\?|$)/, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/spots/landing") {
      return route.fulfill({ json: { spots: [], total: 0, version: "test" } });
    }
    if (path === "/spots/version") {
      return route.fulfill({ json: { version: "test", origins_mixed: false } });
    }
    if (path === "/spots") return route.fulfill({ json: [catalogueSpot] });
    return route.fulfill({ json: [] });
  });
}

test("search forwards a week range and renders an accessible result", async ({ page }) => {
  await mockSearchDependencies(page);
  let requestedWeeks: string | null = null;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/search/, (route) => {
    requestedWeeks = new URL(route.request().url()).searchParams.get("weeks");
    return route.fulfill({ json: result });
  });

  await page.goto("/search?q=Laboe&weeks=3-4");
  await expect(page.getByRole("link", { name: /Laboe/ })).toBeVisible();
  expect(requestedWeeks).toBe("3-4");
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
  ).toEqual([]);
});

test("search forwards a selected month", async ({ page }) => {
  await mockSearchDependencies(page);
  let requestedMonth: string | null = null;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/search/, (route) => {
    requestedMonth = new URL(route.request().url()).searchParams.get("month");
    return route.fulfill({ json: result });
  });

  await page.goto("/search?q=Laboe&month=7");
  await expect(page.getByRole("link", { name: /Laboe/ })).toBeVisible();
  // The redesigned results page names the search in its header bar, not in a
  // separate "Aktive Suche" status line; what matters here is the request.
  expect(requestedMonth).toBe("7");
});

test("search recovers after an API error", async ({ page }) => {
  await mockSearchDependencies(page);
  let attempts = 0;
  let recover = false;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/search/, (route) => {
    attempts += 1;
    return recover
      ? route.fulfill({ json: result })
      : route.fulfill({ status: 503, json: { detail: "temporarily unavailable" } });
  });

  await page.goto("/search?q=Laboe&weeks=3-4");
  await expect(page.getByRole("alert")).toBeVisible();
  recover = true;
  await page.getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(page.getByRole("link", { name: /Laboe/ })).toBeVisible();
  expect(attempts).toBeGreaterThanOrEqual(2);
});

test("results switch between the tiles and the region view with wind months", async ({ page }) => {
  const cat = [
    { ...catalogueSpot, id: "s1", slug: "laboe", name: "Laboe", region_name: "Kieler Bucht" },
    { ...catalogueSpot, id: "s2", slug: "heidkate", name: "Heidkate", region_name: "Kieler Bucht" },
    { ...catalogueSpot, id: "s3", slug: "wulfen", name: "Wulfen", region_name: "Fehmarn" },
  ];
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/(?:spots|regions|live)(?:\/|\?|$)/, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/spots/version") return route.fulfill({ json: { version: "test", origins_mixed: false } });
    if (path === "/spots/landing") return route.fulfill({ json: { spots: [], total: 0, version: "test" } });
    if (path === "/spots") return route.fulfill({ json: cat });
    const clim = path.match(/^\/spots\/(s\d)\/wind-climatology$/);
    if (clim) {
      const base = { s1: 20, s2: 30, s3: 10 }[clim[1] as "s1" | "s2" | "s3"];
      const sections = Array.from({ length: 48 }, (_, t) => ({
        month: Math.floor(t / 4) + 1, section: t + 1, day_start: 1, day_end: 7, date_label: "", calendar_days: 7, daylight_hours: 12,
        windows: {
          "10_15": { hours: 0, percent: 20, hours_per_day: 2 },
          "15_20": { hours: 0, percent: base, hours_per_day: 2 },
          "20_30": { hours: 0, percent: 5, hours_per_day: 1 },
          "30_plus": { hours: 0, percent: 0, hours_per_day: 0 },
        },
      }));
      return route.fulfill({ json: { status: "ready", period: { start_year: 2005, end_year: 2024 }, sections } });
    }
    return route.fulfill({ json: [] });
  });
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/search/, (route) =>
    route.fulfill({ json: { resolved: "entities", regionen: [], spots: cat.map((s) => ({ id: s.id, slug: s.slug, name: s.name, location: s.location, sports: s.sports, score: 0.8 })), treffer: 3 } }),
  );

  await page.goto("/search?q=Kiel&month=6");
  const tabs = page.getByRole("tablist", { name: "Ergebnis-Ansicht" });
  await expect(tabs.getByRole("tab", { name: "Übersicht" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("link", { name: /Laboe/ }).first()).toBeVisible();

  await tabs.getByRole("tab", { name: "Nach Region" }).click();
  await expect(page).toHaveURL(/view=regionen/);
  await expect(page.getByRole("heading", { name: "Kieler Bucht" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fehmarn" })).toBeVisible();
  // Juni share at ≥15 kn: Heidkate 30+5 = 35 %, sorted first in its region.
  const kiel = page.getByRole("region", { name: "Kieler Bucht" });
  await expect(kiel.getByRole("link").first()).toContainText("Heidkate");
  await expect(kiel.getByRole("link").first()).toContainText("35 %");

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  if (process.env.RESULTS_SHOTS) await page.screenshot({ path: `${process.env.RESULTS_SHOTS}/regionen-${test.info().project.name}.png`, fullPage: true });

  await tabs.getByRole("tab", { name: "Übersicht" }).click();
  await expect(page).not.toHaveURL(/view=regionen/);
  await expect(page.getByRole("link", { name: /Laboe/ }).first()).toBeVisible();
});
