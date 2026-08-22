import { expect, test } from "@playwright/test";

const CARTO_STYLE_URL = "https://tiles.basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

// A minimal-but-valid style document — enough for MapLibre to construct the
// map without any real tile/glyph network traffic. `buildPublicMapStyle`
// tolerates every one of its target layers being absent (see
// lib/__tests__/publicMap.test.ts), so this deliberately carries none.
const MINIMAL_STYLE = {
  version: 8,
  sources: {},
  // MapLibre rejects any symbol layer with `text-field` (our own appended
  // cluster-count/name layers included) unless the style declares `glyphs` —
  // this doesn't need to resolve for the map to load; glyph tiles are
  // fetched lazily when text actually needs to render.
  glyphs: "https://fonts.example.test/{fontstack}/{range}.pbf",
  layers: [{ id: "background", type: "background", paint: { "background-color": "#ffffff" } }],
};

const spots = [
  { id: "00000000-0000-4000-8000-000000000001", slug: "spot-a", name: "Spot A", region_id: null, region_name: "Region A", region_country: "DE", location: { lat: 54, lon: 10 }, sports: ["kitesurf"], image: null, facing: null, water_type: [], bottom_type: [], level: [], water_character: [], style: [], facilities: null, best_months: null, typical_wind_kt: 18, typical_wave_height_m: null },
  { id: "00000000-0000-4000-8000-000000000002", slug: "spot-b", name: "Spot B", region_id: null, region_name: "Region B", region_country: "FR", location: { lat: 43, lon: 6 }, sports: ["surf"], image: null, facing: null, water_type: [], bottom_type: [], level: [], water_character: [], style: [], facilities: null, best_months: null, typical_wind_kt: 12, typical_wave_height_m: null },
];

async function mockBackend(page: import("@playwright/test").Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots") return route.fulfill({ json: spots });
    if (url.pathname === "/spots/version") return route.fulfill({ json: { version: "test-1" } });
    if (url.pathname === "/spots/live") return route.fulfill({ json: [] });
    if (url.pathname === "/auth/me") return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    return route.fulfill({ json: [] });
  });
  await page.route(CARTO_STYLE_URL, (route) => route.fulfill({ json: MINIMAL_STYLE }));
}

test("map renders spots as accessible markers, without a runtime style-repaint flash", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  await mockBackend(page);

  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Surfspot Spot B" })).toBeVisible();

  // The container only becomes visible once `load` fires on the pre-colored
  // style — by the time the markers are visible, the map itself must be too.
  await expect(page.locator(".swd-public-map > div[role='region'] > div").first()).toHaveCSS("opacity", "1");
  expect(consoleErrors).toEqual([]);
});

test("spot markers survive a theme swap (setStyle resets the GeoJSON source's live data)", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Surfspot Spot B" })).toBeVisible();

  await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
});

test("results list opens via its trigger, closes on Escape, and returns focus", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  const trigger = page.getByRole("button", { name: "Als Liste anzeigen" });
  await trigger.click();

  const dialog = page.getByRole("dialog", { name: "Surfspots im Kartenausschnitt als Liste" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Spot A")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("a deep-linked spot is selected on load and the shared position is not overwritten by fitBounds", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map?lat=54&lon=10&z=9&spot=00000000-0000-4000-8000-000000000001");

  const marker = page.getByRole("button", { name: "Surfspot Spot A" });
  await expect(marker).toHaveAttribute("aria-pressed", "true");

  // The shared zoom (9) must survive — a stray `fitBounds` over all spots
  // would pull it back down toward the wide default overview.
  await page.waitForTimeout(600);
  await expect(page).toHaveURL(/z=9(\.\d+)?/);
});

test("back navigation falls back to the homepage when there is no history entry", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await page.getByRole("button", { name: "Zurück" }).click();
  await expect(page).toHaveURL(/\/$/);
});
