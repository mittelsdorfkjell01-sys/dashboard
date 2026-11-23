import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const region = {
  id: "r1",
  slug: "kieler-bucht",
  name: "Kieler Bucht",
  country: "DE",
  center: { lat: 54.4, lon: 10.2 },
  description: "Surfregion an der Ostsee.",
  image: null,
  season: null,
  defaults: null,
  status: "published",
  updated_at: "2026-11-18T00:00:00Z",
};

async function mockPublicApi(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots" || url.pathname === "/spots/top") {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === "/spots/landing") {
      return route.fulfill({ json: { spots: [], total: 0, version: "test" } });
    }
    if (url.pathname === "/spots/version") {
      return route.fulfill({ json: { version: "test", origins_mixed: false } });
    }
    if (url.pathname === "/regions") return route.fulfill({ json: [region] });
    if (url.pathname === "/regions/by-slug/kieler-bucht") {
      return route.fulfill({ json: region });
    }
    if (url.pathname === "/regions/r1/season") {
      return route.fulfill({ json: { weeks: [], months: [] } });
    }
    if (url.pathname === "/areas/best-weeks") {
      return route.fulfill({ json: { weeks: [] } });
    }
    return route.fulfill({ status: 404, json: { detail: "mock missing" } });
  });
}

async function expectAccessibleWithoutOverflow(page: Page) {
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
  ).toEqual([]);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test("landing remains usable with an empty catalogue", async ({ page }) => {
  await mockPublicApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /surfwind data/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Alle Spots entdecken" })).toBeVisible();
  await expectAccessibleWithoutOverflow(page);
});

test("region detail renders its empty state", async ({ page }) => {
  // The section bands fade in on scroll. Without reduced motion axe measured
  // their colours mid-fade (opacity 0, blended text) and flagged contrast in
  // Firefox — the finished page was never the problem.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockPublicApi(page);
  await page.goto("/region/kieler-bucht");
  await expect(page.getByRole("heading", { name: "Kieler Bucht", exact: true })).toBeVisible();
  await expect(page.getByText(/Keine Spots/)).toBeVisible();
  const descriptionSection = page
    .getByText("Surfregion an der Ostsee.")
    .locator("xpath=ancestor::section[1]");
  await descriptionSection.scrollIntoViewIfNeeded();
  await expect(descriptionSection).toHaveCSS("opacity", "1");
  const seasonSection = page.locator("#season");
  await seasonSection.scrollIntoViewIfNeeded();
  await expect(seasonSection).toHaveCSS("opacity", "1");
  await expectAccessibleWithoutOverflow(page);
});
