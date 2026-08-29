import { expect, test } from "@playwright/test";

const SPOT_ID = "00000000-0000-4000-8000-000000000010";
const TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

const spotDetail = (overrides: Record<string, unknown> = {}) => ({
  id: SPOT_ID, slug: "spot-map-test", name: "Spot Map Test",
  region_id: "r1", region_name: "Region A", region_country: "DE",
  location: { lat: 54.0, lon: 10.0 },
  sports: ["kitesurf"], image: null, facing: 220,
  water_type: ["sea"], bottom_type: ["sand"], level: ["beginner"], water_character: ["chop"],
  style: [], facilities: null, best_months: null,
  typical_wind_kt: 18, typical_wave_height_m: null,
  editorial: { description: "Test spot." },
  ...overrides,
});

async function mockBackend(page: import("@playwright/test").Page, spot = spotDetail(), coastalNormal: number | null = 220) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === `/spots/${spot.slug}`) return route.fulfill({ json: spot });
    if (url.pathname === `/spots/${SPOT_ID}/live`) {
      return route.fulfill({
        json: {
          spot_id: SPOT_ID, model: "icon_eu", time: "2026-08-24T12:00:00Z",
          coastal_normal_deg: coastalNormal,
          current: { wind: 18, gust: 24, dir: 312, air: 21, sst: 19, swell: 1.2, period: 9, swell_dir: 270, coastal_normal_deg: coastalNormal },
        },
      });
    }
    if (url.pathname === `/spots/${SPOT_ID}/forecast`) return route.fulfill({ json: { spot_id: SPOT_ID, model: "icon_eu", generated_at: "2026-08-24T12:00:00Z", timezone: "UTC", availability: { atmosphere: "available", solar: "available", marine: "not_applicable_inland" }, days: [] } });
    if (url.pathname === `/spots/${SPOT_ID}/tides`) return route.fulfill({ json: { available: false, message: "Keine Gezeiten für diesen Spot.", timezone: null, phase: "unavailable", cycle_position: null, quality: "unavailable", approximate: false, last_calculated_at: null, valid_until: null, events: [] } });
    if (url.pathname === `/spots/${SPOT_ID}/wind-climatology-v3`) return route.fulfill({ status: 404, json: { detail: "not available" } });
    if (url.pathname === "/auth/me" || url.pathname === "/account/me") return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    if (url.pathname === "/account/favorites" || url.pathname === "/account/submissions") return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    return route.fulfill({ json: [] });
  });
  await page.route(/https:\/\/[a-d]\.basemaps\.cartocdn\.com\/.*\.png(?:\?.*)?$/, (route) =>
    route.fulfill({ body: TRANSPARENT_PNG, contentType: "image/png" }),
  );
}

test("spot map renders with real coordinates, mode switch and legend", async ({ page }) => {
  await mockBackend(page);
  await page.goto(`/spot/spot-map-test/daten`);

  const modeSwitch = page.getByRole("group", { name: "Kartenmodus" });
  await expect(modeSwitch.getByRole("button", { name: "Wind", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Wind (kt)")).toBeVisible();
  await expect(page.locator(".swd-spot-map .leaflet-container")).toBeVisible();

  // Nowcast badge shown (no forecast hour scrubbed, no station measurement mocked).
  await expect(page.getByText("Nowcast").first()).toBeVisible();
});

test("switching to Wellen recolors the legend without a page reload", async ({ page }) => {
  await mockBackend(page);
  await page.goto(`/spot/spot-map-test/daten`);
  await expect(page.getByText("Wind (kt)")).toBeVisible();

  const modeSwitch = page.getByRole("group", { name: "Kartenmodus" });
  await modeSwitch.getByRole("button", { name: "Wellen", exact: true }).click();
  await expect(page.getByText("Swell (Primärwelle)")).toBeVisible();
});

test("a spot without coordinates shows an explanatory state instead of an empty map", async ({ page }) => {
  const spot = spotDetail({ location: null });
  await mockBackend(page, spot);
  await page.goto(`/spot/spot-map-test/daten`);

  await expect(page.getByText("Für diesen Spot sind keine Koordinaten hinterlegt")).toBeVisible();
  await expect(page.locator(".swd-spot-map .leaflet-container")).toHaveCount(0);
});

test("spot facing never creates a coastal-orientation toggle", async ({ page }) => {
  const spot = spotDetail({ facing: 220 });
  await mockBackend(page, spot, null);
  await page.goto(`/spot/spot-map-test/daten`);

  await expect(page.locator(".swd-spot-map .leaflet-container")).toBeVisible();
  await expect(page.getByRole("button", { name: /Küstenausrichtung|Nordausrichtung/ })).toHaveCount(0);
});
