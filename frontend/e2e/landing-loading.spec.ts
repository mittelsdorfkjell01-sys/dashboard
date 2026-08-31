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

test("hero search remains fully visible when opened after scrolling", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.includes("mobile"), "Desktop hero search uses the inline panel");

  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots") return route.fulfill({ json: spots });
    if (url.pathname === "/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await page.evaluate(() => window.scrollTo(0, window.innerHeight * 0.42));
  await page.locator("#landing-search").getByRole("button", { name: "Jetzt suchen" }).click();

  const stack = page.getByTestId("desktop-search-stack");
  const panel = page.getByTestId("desktop-search-panel");
  await expect(stack).toBeVisible();
  await expect(panel).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Region oder Spot suchen" })).toBeFocused();

  const box = await stack.boundingBox();
  const panelBox = await panel.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(panelBox).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(box!.y).toBeGreaterThanOrEqual(23);
  expect(panelBox!.y + panelBox!.height).toBeLessThanOrEqual(viewport!.height - 23);
});

test("mobile search contains focus and returns it to its trigger", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"), "Mobile search uses the full-screen sheet");

  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots") return route.fulfill({ json: spots });
    if (url.pathname === "/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  const trigger = page.locator("#landing-search").getByRole("button", { name: "Jetzt suchen" });
  await trigger.click();

  const dialog = page.getByRole("dialog", { name: "Suche" });
  const close = dialog.getByRole("button", { name: "Schließen" });
  await expect(close).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Suchen", exact: true })).toBeFocused();

  await close.click();
  await expect(trigger).toBeFocused();
});
