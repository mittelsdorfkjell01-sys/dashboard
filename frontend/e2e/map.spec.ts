import { expect, test } from "@playwright/test";

const TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

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
  await page.route(/https:\/\/[a-d]\.basemaps\.cartocdn\.com\/.*\.png(?:\?.*)?$/, (route) =>
    route.fulfill({ body: TRANSPARENT_PNG, contentType: "image/png" }),
  );
}

test("map loads Leaflet layout and renders spots as accessible markers", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  await mockBackend(page);

  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Surfspot Spot B" })).toBeVisible();

  const map = page.locator(".swd-public-map .leaflet-container");
  await expect(map).toBeVisible();
  await expect(page.locator(".swd-map-canvas")).toHaveCSS("opacity", "1");
  // This rule comes from Leaflet's base stylesheet. Without the global import,
  // panes and tiles fall into normal document flow on direct /map visits.
  await expect(map.locator(".leaflet-map-pane")).toHaveCSS("position", "absolute");
  expect(consoleErrors).toEqual([]);
});

test("the map stays on its light palette and keeps its markers regardless of the site's dark mode (2026-08-22 feedback)", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Surfspot Spot B" })).toBeVisible();
  // The rail's `--sw-*` tokens must stay pinned to their light values even
  // though the rest of the site is in dark mode.
  const background = await page.locator("main.swd-public-map").evaluate((el) => getComputedStyle(el).getPropertyValue("--sw-surface").trim());
  expect(background.toUpperCase()).toBe("#FFFFFF");

  await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
});

test("the list trigger shows two Landing-style tiles inline, not a text list or a dark overlay", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  const trigger = page.getByRole("button", { name: "Spots im Ausschnitt anzeigen" });
  await trigger.click();
  await expect(trigger).toBeHidden();

  const panel = page.locator(".swd-map-tile-grid");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("link", { name: /Spot A/ })).toBeVisible();
  await expect(panel.getByRole("link", { name: /Spot B/ })).toBeVisible();

  // No modal/dialog role and no dark scrim — the map underneath must stay
  // interactive (still pannable) while the panel is open.
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".swd-public-map .leaflet-container")).toBeVisible();

  await page.getByRole("button", { name: "Schließen" }).click();
  await expect(panel).toBeHidden();
  await expect(page.getByRole("button", { name: "Spots im Ausschnitt anzeigen" })).toHaveAttribute("aria-expanded", "false");
});

test("selecting a marker shows its chart panel with a plain-X close and a link to the full spot page", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map?lat=54&lon=10&z=9");
  const marker = page.getByRole("button", { name: "Surfspot Spot A" });
  await expect(marker).toBeVisible();
  await marker.click();
  await expect(marker).toHaveAttribute("aria-pressed", "true");

  // The desktop marker popup also renders a "Spot A" tile, so scope this to
  // the bottom chart panel specifically.
  const chartPanel = page.locator(".swd-map-panel");
  await expect(chartPanel.getByText("Spot A", { exact: true })).toBeVisible();
  const spotLink = page.getByRole("link", { name: "Zum Spot" });
  await expect(spotLink).toHaveAttribute("href", /\/spot\/spot-a/);

  const closeButton = page.getByRole("button", { name: "Schließen" });
  await expect(closeButton).toBeVisible();
  await closeButton.click();
  await expect(marker).toHaveAttribute("aria-pressed", "false");
  await expect(spotLink).toBeHidden();
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

test("overview omits mode controls, legend and the bottom empty hint", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map?lat=0&lon=-150&z=10&mode=waves");
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await expect(page.getByRole("group", { name: "Kartenmodus" })).toHaveCount(0);
  await expect(page.locator(".swd-map-legend")).toHaveCount(0);
  await expect(page.locator(".swd-map-status")).toHaveCount(0);
  await expect(page.getByText("Keine Spots in diesem Kartenausschnitt", { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/mode=/);
});
