import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

const spots = [
  {
    id: "00000000-0000-4000-8000-000000000001",
    slug: "spot-a",
    name: "Spot A",
    region_id: "region-a",
    region_name: "Nordsee",
    region_country: "DE",
    location: { lat: 54, lon: 10 },
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
    typical_wind_kt: 18,
    typical_wave_height_m: null,
  },
  {
    id: "00000000-0000-4000-8000-000000000002",
    slug: "spot-b",
    name: "Spot B",
    region_id: "region-a",
    region_name: "Nordsee",
    region_country: "DE",
    location: { lat: 54.2, lon: 10.2 },
    sports: ["surf"],
    image: null,
    facing: null,
    water_type: [],
    bottom_type: [],
    level: [],
    water_character: [],
    style: [],
    facilities: null,
    best_months: null,
    typical_wind_kt: 14,
    typical_wave_height_m: 1.2,
  },
  {
    id: "00000000-0000-4000-8000-000000000003",
    slug: "spot-c",
    name: "Spot C",
    region_id: "region-a",
    region_name: "Nordsee",
    region_country: "DE",
    location: { lat: 54.4, lon: 10.4 },
    sports: ["wing"],
    image: null,
    facing: null,
    water_type: [],
    bottom_type: [],
    level: [],
    water_character: [],
    style: [],
    facilities: null,
    best_months: null,
    typical_wind_kt: 16,
    typical_wave_height_m: null,
  },
];

const summary = (spot: (typeof spots)[number]) => ({
  id: spot.id,
  slug: spot.slug,
  name: spot.name,
  region_id: spot.region_id,
  region_name: spot.region_name,
  region_country: spot.region_country,
  location: spot.location,
  sports: spot.sports,
  image: null,
  typical_wind_kt: spot.typical_wind_kt,
  typical_wave_height_m: spot.typical_wave_height_m,
});

async function mockPublicData(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots/version") return route.fulfill({ json: { version: "quality-test" } });
    if (url.pathname === "/spots") return route.fulfill({ json: spots });
    if (url.pathname === "/spots/top") return route.fulfill({ json: [spots[0], spots[2]] });
    if (url.pathname === "/spots/live") return route.fulfill({ json: [] });
    if (url.pathname.endsWith("/similar")) {
      return route.fulfill({ json: { results: [summary(spots[0]), summary(spots[1])] } });
    }
    if (url.pathname === "/search") {
      return route.fulfill({
        json: {
          resolved: "entities",
          treffer: 1,
          regionen: [],
          spots: [{ ...summary(spots[0]), score: 0.9 }],
        },
      });
    }
    if (url.pathname === "/regions" || url.pathname === "/search/best-regions") return route.fulfill({ json: [] });
    if (url.pathname === "/auth/me") return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    return route.fulfill({ json: [] });
  });
  await page.route(/https:\/\/[a-d]\.basemaps\.cartocdn\.com\/.*\.png(?:\?.*)?$/, (route) =>
    route.fulfill({ body: TRANSPARENT_PNG, contentType: "image/png" }),
  );
}

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
}

test("landing communicates its value, handles missing measurements and exposes complete metadata", async ({ page }) => {
  await mockPublicData(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1, name: /Finde den Spot/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Aktuelle Top-Spots" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Von der Idee zur passenden Session." })).toBeVisible();
  await expect(page.getByText("—", { exact: true })).toHaveCount(0);
  await expect(page).toHaveTitle("Surfspots finden: Wind, Wellen & Vorhersage | surfwind data");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /Surf-, Kite-, Wing-/);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "index,follow");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://surfwinddata.com/");
  await expectNoSeriousAccessibilityViolations(page);
});

test("map explains its data layer, remains operable and is excluded from indexing", async ({ page }) => {
  await mockPublicData(page);
  await page.goto("/map");

  await expect(page.getByRole("group", { name: "Legende: Wind" })).toBeVisible();
  await expect(page.locator(".swd-map-context")).toContainText("Marker wählen für Vorhersage");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
  await expect(page).toHaveTitle("Surfspot-Karte: Windspots weltweit entdecken | surfwind data");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex,follow");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://surfwinddata.com/map");
  await expectNoSeriousAccessibilityViolations(page);
});

test("search separates result types, removes duplicates and explains every ranking", async ({ page }) => {
  await mockPublicData(page);
  await page.goto("/search?q=Nordsee&sport=kitesurf");

  await expect(page.getByRole("heading", { level: 1, name: "Ergebnisse für „Nordsee“" })).toBeVisible();
  await expect(page.getByLabel("Aktive Suchauswahl").getByText("Kitesurfen", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Passende Spots" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ähnliche Bedingungen" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Aktuell empfohlen" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Spot A/ })).toHaveCount(1);
  await expect(page.getByRole("link", { name: /Spot B/ })).toHaveCount(1);
  await expect(page.getByRole("link", { name: /Spot C/ })).toHaveCount(1);
  await expect(page.getByText(/7-Tage-Windvorhersage, heutigen Bedingungen/)).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex,follow");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://surfwinddata.com/search");
  await expectNoSeriousAccessibilityViolations(page);
});

test("landing and search do not overflow a 320px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await mockPublicData(page);

  for (const path of ["/", "/search?q=Nordsee&sport=kitesurf"]) {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
