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
