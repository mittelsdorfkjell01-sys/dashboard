import { expect, test, type Page } from "@playwright/test";

/**
 * Herkunftskennzeichnung: das Zeichen steht für Autorschaft, nicht für
 * Qualität, und es erscheint erst, wenn der Katalog überhaupt gemischt ist.
 * Genau diese Torschaltung ist der subtile Teil — deshalb hier beide Fälle.
 */

const spots = Array.from({ length: 12 }, (_, index) => ({
  id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
  slug: `spot-${index}`,
  name: `Spot ${index}`,
  region_id: null,
  region_name: "Testregion",
  region_country: "DE",
  location: { lat: 54 + index / 100, lon: 10 },
  sports: ["kitesurf"],
  image: null,
  facing: null,
  water_type: [], bottom_type: [], level: [], water_character: [], style: [],
  facilities: null, best_months: null,
  typical_wind_kt: null, typical_wave_height_m: null,
  origin: index === 0 ? "community" : "editorial",
  contributor_name: index === 0 ? "Lena K." : null,
}));

async function mockCatalogue(page: Page, originsMixed: boolean) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots/landing") {
      return route.fulfill({ json: { spots, total: spots.length, version: "t-1" } });
    }
    if (url.pathname === "/spots") return route.fulfill({ json: spots });
    if (url.pathname === "/spots/version") {
      return route.fulfill({ json: { version: "t-1", origins_mixed: originsMixed } });
    }
    if (url.pathname === "/auth/me" || url.pathname === "/account/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });
}

const mark = (page: Page) => page.getByRole("img", { name: "Von der Redaktion erfasst" });

test("no spot carries the origin mark while the catalogue is all ours", async ({ page }) => {
  await mockCatalogue(page, false);
  await page.goto("/");
  await expect(page.locator("span.truncate", { hasText: /^Spot 1$/ }).first()).toBeVisible();
  await expect(mark(page)).toHaveCount(0);
});

test("our own spots carry the mark once a community spot is live", async ({ page }) => {
  await mockCatalogue(page, true);
  await page.goto("/");
  await expect(mark(page).first()).toBeVisible();
  // Eleven editorial spots are marked; the community spot stays unmarked —
  // absence is the distinction, there is no second badge.
  expect(await mark(page).count()).toBe(11);
});
