import { expect, test, type Page } from "@playwright/test";

const VALDEVAQUEROS_ID = "11111111-1111-4111-8111-111111111111";

const searchResult = {
  resolved: "entities",
  treffer: 3,
  regionen: [{ id: "r1", slug: "tarifa", name: "Tarifa", center: null }],
  spots: [
    {
      id: VALDEVAQUEROS_ID,
      slug: "valdevaqueros",
      name: "Valdevaqueros",
      location: { lat: 36, lon: -5 },
      sports: ["kitesurf", "windsurf"],
      score: 0.82,
    },
  ],
};

// The results page resolves the light /search hits against the full catalogue
// (GET /spots?limit=100) via enrichSpots — a hit with no catalogue match is
// dropped, so the mock must carry the same spot in the backend catalogue shape.
const catalogueSpots = [
  {
    id: VALDEVAQUEROS_ID,
    slug: "valdevaqueros",
    name: "Valdevaqueros",
    region_id: "r1",
    region_name: "Tarifa",
    region_country: "ES",
    location: { lat: 36, lon: -5 },
    sports: ["kitesurf", "windsurf"],
    image: null,
    facing: null,
    water_type: [],
    bottom_type: [],
    level: [],
    water_character: [],
    style: [],
    facilities: null,
    best_months: null,
    typical_wind_kt: null,
    typical_wave_height_m: null,
  },
];

async function mockSearch(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/search") return route.fulfill({ json: searchResult });
    if (url.pathname === "/spots/landing") {
      return route.fulfill({ json: { spots: catalogueSpots, total: catalogueSpots.length, version: "t-1" } });
    }
    if (url.pathname === "/spots") return route.fulfill({ json: catalogueSpots });
    if (url.pathname === "/auth/me" || url.pathname === "/account/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });
}

test("results keep their editorial page structure on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 851 });
  await mockSearch(page);
  await page.goto("/search?q=Tarifa");
  await expect(page.getByText("Valdevaqueros", { exact: true }).first()).toBeVisible();

  const header = await page.locator("header").boundingBox();
  const breadcrumb = await page.locator("main nav").boundingBox();
  expect(header).not.toBeNull();
  expect(breadcrumb).not.toBeNull();
  expect(header!.y + header!.height).toBeLessThanOrEqual(breadcrumb!.y);

  const footer = await page.locator("footer").boundingBox();
  expect(footer).not.toBeNull();
  expect(Math.round(footer!.y + footer!.height)).toBeGreaterThanOrEqual(851);
});

test("the results page shows the one weather map, framed on the hits", async ({ page }) => {
  // The page's own Leaflet copy was deleted (2026-10-10). What sits beside the
  // results from lg up is the shared weather map, embedded: wind only, so no
  // Spots/Wind switch and no second search inside it.
  await mockSearch(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/search?q=Tarifa");
  await expect(page.getByText("Valdevaqueros", { exact: true }).first()).toBeVisible();

  await expect(page.locator(".leaflet-container")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Vergrößern" })).toHaveCount(0);

  const map = page.locator(".swd-wind-explorer.is-embedded");
  await expect(map).toBeVisible();
  await expect(map.getByRole("group", { name: "Kartenmodus" })).toHaveCount(0);

  // The result column keeps its own measure beside the map rather than
  // stretching across the whole page.
  const mapBox = (await map.boundingBox())!;
  const grid = page.locator("main section div.grid").first();
  const gridBox = (await grid.boundingBox())!;
  expect(gridBox.x + gridBox.width).toBeLessThanOrEqual(mapBox.x + 1);
});

test("on mobile the results page offers the map as a framed link, not a second map", async ({ page }) => {
  await mockSearch(page);
  await page.setViewportSize({ width: 393, height: 851 });
  await page.goto("/search?q=Tarifa");
  await expect(page.getByText("Valdevaqueros", { exact: true }).first()).toBeVisible();

  await expect(page.locator(".swd-wind-explorer")).toHaveCount(0);
  const link = page.getByRole("link", { name: "Karte öffnen" });
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  expect(href).toContain("mode=wind");
  expect(href).toContain("toggle=0");
  expect(href).toMatch(/lat=-?\d/);
});

test("saved dark mode is applied before the results route renders", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("sw-theme", "dark"));
  await mockSearch(page);
  await page.goto("/search?q=Tarifa");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByText("Valdevaqueros", { exact: true }).first()).toBeVisible();

  const pageBackground = await page.locator("html").evaluate((node) =>
    getComputedStyle(node).getPropertyValue("--sw-page").trim(),
  );
  expect(pageBackground.toLowerCase()).toBe("#0e1114");
});

test("search is the filled-action exception and loads regions on demand", async ({ page }, testInfo) => {
  // Desktop landing docks the inline SearchBar panel; mobile uses the separate
  // MobileSearchTrigger/Sheet, covered elsewhere.
  test.skip(testInfo.project.name.includes("mobile"), "Desktop hero search uses the inline panel");
  let regionCalls = 0;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/regions") {
      regionCalls += 1;
      return route.fulfill({ json: [] });
    }
    if (url.pathname === "/spots/landing") {
      return route.fulfill({ json: { spots: [], total: 0, version: "t-1" } });
    }
    if (url.pathname === "/spots/top" || url.pathname === "/spots") {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === "/recommendations") {
      return route.fulfill({ json: catalogueSpots });
    }
    if (url.pathname === "/spots/live") return route.fulfill({ json: [] });
    if (url.pathname === "/auth/me" || url.pathname === "/account/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");

  // The hero search entry is the landing's one filled affordance; the map
  // entry beside "Aktuelle Top Spots" stays a ghost link.
  const heroSearch = page
    .locator("#landing-search")
    .getByRole("button", { name: "Jetzt suchen" });
  await expect(heroSearch).toBeVisible();

  const mapBackground = await page
    .getByRole("link", { name: "Karte öffnen" })
    .evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(mapBackground).toBe("rgba(0, 0, 0, 0)");

  // Regions are only fetched once the search is actually opened.
  expect(regionCalls).toBe(0);
  await heroSearch.click();

  const submit = page.getByRole("button", { name: "Suchen", exact: true });
  await expect(submit).toBeVisible();
  const submitBackground = await submit.evaluate(
    (node) => getComputedStyle(node).backgroundColor,
  );
  expect(submitBackground).not.toBe("rgba(0, 0, 0, 0)");

  await expect.poll(() => regionCalls).toBe(1);
});
