import { expect, test, type Page } from "@playwright/test";

const searchResult = {
  resolved: "entities",
  treffer: 3,
  regionen: [{ id: "r1", slug: "tarifa", name: "Tarifa", center: null }],
  spots: [
    {
      id: "11111111-1111-4111-8111-111111111111",
      slug: "valdevaqueros",
      name: "Valdevaqueros",
      location: { lat: 36, lon: -5 },
      sports: ["kitesurf", "windsurf"],
      score: 0.82,
    },
  ],
};

async function mockSearch(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/search") return route.fulfill({ json: searchResult });
    if (url.pathname === "/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });
}

test("results keep their editorial page structure on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 851 });
  await mockSearch(page);
  await page.goto("/search?q=Tarifa");
  await expect(page.getByText("Valdevaqueros", { exact: true })).toBeVisible();

  const header = await page.locator("header").boundingBox();
  const breadcrumb = await page.locator("main nav").boundingBox();
  expect(header).not.toBeNull();
  expect(breadcrumb).not.toBeNull();
  expect(header!.y + header!.height).toBeLessThanOrEqual(breadcrumb!.y);

  const footer = await page.locator("footer").boundingBox();
  expect(footer).not.toBeNull();
  expect(Math.round(footer!.y + footer!.height)).toBeGreaterThanOrEqual(851);
});

test("saved dark mode is applied before the results route renders", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("sw-theme", "dark"));
  await mockSearch(page);
  await page.goto("/search?q=Tarifa");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByText("Valdevaqueros", { exact: true })).toBeVisible();

  const pageBackground = await page.locator("html").evaluate((node) =>
    getComputedStyle(node).getPropertyValue("--sw-page").trim(),
  );
  expect(pageBackground.toLowerCase()).toBe("#0e1114");
});

test("search is the filled-action exception and loads regions on demand", async ({ page }) => {
  let regionCalls = 0;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/regions") {
      regionCalls += 1;
      return route.fulfill({ json: [] });
    }
    if (url.pathname === "/spots/top" || url.pathname === "/spots") {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === "/spots/live") return route.fulfill({ json: [] });
    if (url.pathname === "/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Suchen" })).toBeVisible();
  expect(regionCalls).toBe(0);

  const searchButtonBackground = await page
    .getByRole("button", { name: "Suchen" })
    .evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(searchButtonBackground).not.toBe("rgba(0, 0, 0, 0)");

  const mapBackground = await page
    .getByRole("link", { name: "Karte öffnen" })
    .evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(mapBackground).toBe("rgba(0, 0, 0, 0)");

  await page.getByRole("textbox", { name: "Region oder Spot suchen" }).focus();
  await expect.poll(() => regionCalls).toBe(1);
});
