import { expect, test } from "@playwright/test";

const spots = Array.from({ length: 36 }, (_, index) => ({
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
  water_type: [],
  bottom_type: [],
  level: [],
  water_character: [],
  style: [],
  facilities: null,
  best_months: null,
  typical_wind_kt: null,
  typical_wave_height_m: null,
}));

test("all spots expand in place without a second catalogue request or scroll reset", async ({ page }) => {
  let catalogueCalls = 0;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots") {
      catalogueCalls += 1;
      expect(url.searchParams.get("limit")).toBe("100");
      return route.fulfill({ json: spots });
    }
    if (url.pathname === "/spots/top" || url.pathname === "/spots/live") {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === "/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await expect(page.locator("p", { hasText: /^Spot 19$/ })).toBeVisible();
  await expect(page.locator("p", { hasText: /^Spot 20$/ })).toHaveCount(0);

  const button = page.getByRole("button", { name: "Alle Spots anzeigen" });
  await button.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  await button.click();

  await expect(page.locator("p", { hasText: /^Spot 35$/ })).toBeVisible();
  const after = await page.evaluate(() => window.scrollY);
  expect(after).toBeGreaterThan(before - 50);
  expect(catalogueCalls).toBe(1);
});
