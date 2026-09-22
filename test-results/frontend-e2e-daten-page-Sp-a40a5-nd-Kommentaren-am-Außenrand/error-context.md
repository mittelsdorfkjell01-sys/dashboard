# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend\e2e\daten-page.spec.ts >> Spot-Info nutzt die volle Desktopbreite mit Profil rechts der Galerie und Kommentaren am Außenrand
- Location: frontend\e2e\daten-page.spec.ts:96:1

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/spot/test/info", waiting until "load"

```

# Test source

```ts
  1   | import AxeBuilder from "@axe-core/playwright";
  2   | import { expect, test, type Page } from "@playwright/test";
  3   | import type { CommunityImage } from "../src/lib/api";
  4   | 
  5   | // Regression coverage for the rebuilt Daten page (Figma Frame 67): the dark
  6   | // instrument composition — meteogram, today summary + 10-day outlook, map +
  7   | // live-wind sidebar, wind-months field. Replaces the retired
  8   | // meteogram-accessibility / public-tides specs, whose subjects (hourly
  9   | // meteogram controls, data table, direction-compass card, tide panel) were
  10  | // intentionally removed in the rebuild.
  11  | 
  12  | const spot = { id: "test", slug: "laboe", name: "Alcyons", region_id: "r1", location: { lat: 54.4, lon: 10.2 }, sports: ["surf"], water_type: ["sea"], bottom_type: ["sand"], level: ["advanced"], water_character: ["welle_klein"], style: ["wave_riding"], facilities: { parking: { available: true, note: "Am Strand" }, shower: { available: false } }, status: "published", confidence: null, facing: 45, image: null, era5_cell: null, model_pref: null, editorial: { description: "Testspot" }, climatology: null, overrides: null, finish_rank: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-08-24T00:00:00Z" };
  13  | const conditions = ["clear", "partly_cloudy", "rain", "snow", "thunderstorm", "overcast", "drizzle", "mainly_clear"] as const;
  14  | const summary = (i: number) => ({ wind_avg: 12, wind_max: 18, gust_max: 24, air_min: 16 + i, air_max: 24 + i, swell_max: 1.8, apparent_temperature_max_c: 23, precipitation_sum_mm: 0.5, uv_index_max: 9, weather_condition: conditions[i % conditions.length] });
  15  | const forecastDates = ["2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13", "2026-09-14"];
  16  | const hourly = forecastDates.map((date, day) => ({
  17  |   date,
  18  |   local_date: date,
  19  |   detail: "hourly",
  20  |   confidence: day < 2 ? "hoch" : day < 6 ? "mittel" : "niedrig",
  21  |   summary: summary(day),
  22  |   hours: Array.from({ length: 24 }, (_, h) => ({
  23  |     time: `${date}T${String(h).padStart(2, "0")}:00:00Z`,
  24  |     wind: 8 + ((h * 7) % 28),
  25  |     gust: 14 + ((h * 7) % 28),
  26  |     dir: (180 + h * 23) % 360,
  27  |     air: 17 + Math.round(6 * Math.sin(h / 3)),
  28  |     precip: h === 12 ? 0.4 : 0,
  29  |     swell: 0.4 + ((h * 3) % 9) / 10,
  30  |     period: 7 + h / 4,
  31  |     swell_dir: 270,
  32  |     sst: 18,
  33  |     uv_index: Math.max(0, 8 - Math.abs(h - 12)),
  34  |     apparent_temperature_c: 23,
  35  |     coastal_normal_deg: 180,
  36  |     coastal_classification: "onshore",
  37  |     weather_condition: conditions[h % conditions.length],
  38  |     is_day: h >= 7 && h <= 20,
  39  |   })),
  40  | }));
  41  | const forecast = { spot_id: "test", model: "consensus", product: "Surfwinddata Forecast", generated_at: "2026-09-05T08:00:00Z", updated_at: "2026-09-05T08:00:00Z", timezone: "Europe/Berlin", stale: false, availability: { atmosphere: "available", solar: "available", marine: "available" }, days: hourly };
  42  | 
  43  | async function mockApi(page: Page, photos: CommunityImage[] = []) {
  44  |   await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
  45  |     const path = new URL(route.request().url()).pathname;
  46  |     if (path.startsWith("/media/gallery-")) {
  47  |       return route.fulfill({
  48  |         contentType: "image/svg+xml",
  49  |         body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="800" height="600" fill="#397488"/></svg>',
  50  |       });
  51  |     }
  52  |     if (["/spots/test", "/spots/laboe", "/spots/Alcyons"].includes(path)) return route.fulfill({ json: spot });
  53  |     if (path === "/regions/r1") return route.fulfill({ json: { id: "r1", slug: "kieler-bucht", name: "Kieler Bucht", country: "DE", center: null, description: null, image: null, season: null, defaults: null, status: "published", updated_at: "2026-08-24T00:00:00Z" } });
  54  |     if (path === "/spots/test/forecast") return route.fulfill({ json: forecast });
  55  |     if (path === "/spots/test/live") return route.fulfill({ json: { spot_id: "test", model: "consensus", time: "2026-08-24T12:00:00Z", current: { wind: 9, gust: 14, dir: 247, air: 23, sst: 18, swell: 2.5, period: 8, swell_dir: 250, coastal_normal_deg: 180, coastal_classification: "cross_onshore" } } });
  56  |     if (path === "/spots/test/tides") return route.fulfill({ status: 404, json: { detail: "none" } });
  57  |     if (path === "/spots/test/ratings") return route.fulfill({ json: { items: [], aggregate: { count: 0, average: null } } });
  58  |     if (path === "/spots/test/tips") return route.fulfill({ json: [] });
  59  |     if (path === "/spots/test/images") return route.fulfill({ json: { items: photos } });
  60  |     if (path.startsWith("/spots/test/wind-climatology")) return route.fulfill({ status: 404, json: { detail: "none" } });
  61  |     return route.fulfill({ status: 404, json: { detail: `mock missing: ${path}` } });
  62  |   });
  63  | }
  64  | 
  65  | test("Galeriebilder werden vor dem Öffnen geladen und liegen im ersten Overlay-Frame bereit", async ({ page }) => {
  66  |   const photos: CommunityImage[] = [1, 2].map((id) => ({
  67  |     id: `gallery-${id}`,
  68  |     url: `/media/gallery-${id}.svg`,
  69  |     kind: "gallery",
  70  |     width: 800,
  71  |     height: 600,
  72  |     credit: null,
  73  |     created_at: "2026-09-08T12:00:00Z",
  74  |     source: "community",
  75  |     license_name: null,
  76  |     license_url: null,
  77  |     source_url: null,
  78  |   }));
  79  |   const requested = new Set<string>();
  80  |   page.on("request", (request) => {
  81  |     if (request.url().includes("/media/gallery-")) requested.add(request.url());
  82  |   });
  83  | 
  84  |   await page.setViewportSize({ width: 390, height: 900 });
  85  |   await mockApi(page, photos);
  86  |   await page.goto("/spot/test/info");
  87  |   await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  88  |   await expect.poll(() => requested.size).toBe(2);
  89  |   await expect(page.locator(".spot-media-frame img")).toHaveJSProperty("complete", true);
  90  | 
  91  |   await page.getByRole("button", { name: "Fotogalerie öffnen" }).click();
  92  |   await expect(page.getByRole("heading", { name: "Fotogalerie" })).toBeVisible();
  93  |   await expect(page.locator('[role="dialog"] button.group img')).toHaveCount(2);
  94  | });
  95  | 
  96  | test("Spot-Info nutzt die volle Desktopbreite mit Profil rechts der Galerie und Kommentaren am Außenrand", async ({ page }) => {
  97  |   await page.setViewportSize({ width: 1600, height: 1000 });
  98  |   await mockApi(page);
> 99  |   await page.goto("/spot/test/info");
      |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  100 |   await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  101 | 
  102 |   const gallery = page.locator('[data-spot-layout="gallery"]');
  103 |   const profile = page.locator('[data-spot-layout="profile"]');
  104 |   const comments = page.locator('[data-spot-layout="comments"]');
  105 |   const map = page.locator('[data-spot-layout="map"]');
  106 |   const [galleryBox, profileBox, commentsBox, mapBox] = await Promise.all([
  107 |     gallery.boundingBox(),
  108 |     profile.boundingBox(),
  109 |     comments.boundingBox(),
  110 |     map.boundingBox(),
  111 |   ]);
  112 | 
  113 |   expect(galleryBox).not.toBeNull();
  114 |   expect(profileBox).not.toBeNull();
  115 |   expect(commentsBox).not.toBeNull();
  116 |   expect(mapBox).not.toBeNull();
  117 |   expect(profileBox!.x).toBeGreaterThan(galleryBox!.x + galleryBox!.width);
  118 |   expect(commentsBox!.x).toBeGreaterThan(profileBox!.x + profileBox!.width);
  119 |   expect(mapBox!.x + mapBox!.width).toBeLessThanOrEqual(commentsBox!.x + 1);
  120 |   await expect(profile).toHaveCSS("border-radius", "14px");
  121 |   await expect(map).toHaveCSS("border-radius", "14px");
  122 | 
  123 |   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  124 |   expect(overflow).toBeLessThanOrEqual(1);
  125 | });
  126 | 
  127 | test("Daten-Seite zeigt Meteogramm, Ausblick und Livewind", async ({ page }) => {
  128 |   await page.setViewportSize({ width: 1280, height: 900 });
  129 |   await mockApi(page);
  130 |   await page.goto("/spot/test/daten");
  131 |   await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  132 |   // Meteogram row labels + the direction/time axes.
  133 |   await expect(page.getByText("WELLE", { exact: true }).first()).toBeVisible();
  134 |   await expect(page.getByText("RICHT.", { exact: true })).toBeVisible();
  135 |   await expect(page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" })).toBeVisible();
  136 |   // The complete 10-day outlook renders through the last hourly day.
  137 |   await expect(page.getByText("SA 05.09", { exact: true })).toBeVisible();
  138 |   await expect(page.getByText("MO 14.09", { exact: true })).toBeVisible();
  139 |   await expect(page.locator("#spot-meteogram-scroll [data-forecast-day]")).toHaveCount(10);
  140 |   // Live-wind sidebar metrics.
  141 |   await expect(page.getByText("UV INDEX", { exact: true })).toBeVisible();
  142 |   await expect(page.getByText("GEFÜHLT", { exact: true })).toBeVisible();
  143 | });
  144 | 
  145 | for (const width of [320, 375, 768, 1280, 1440]) {
  146 |   test(`Daten-Seite bleibt bei ${width}px innerhalb der Seite`, async ({ page }) => {
  147 |     await page.setViewportSize({ width, height: width < 500 ? 720 : 900 });
  148 |     await mockApi(page);
  149 |     await page.goto("/spot/test/daten");
  150 |     await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  151 |     const outlook = page.locator(".forecast-weather-grid");
  152 |     await expect(outlook.getByRole("button")).toHaveCount(10);
  153 |     const navigator = page.getByRole("group", { name: "Tagesübersicht — Tag im Stundenforecast anzeigen" });
  154 |     await expect(navigator.getByRole("button")).toHaveCount(10);
  155 |     const navigatorOverflow = await navigator.evaluate((element) => element.scrollWidth - element.clientWidth);
  156 |     expect(navigatorOverflow).toBeLessThanOrEqual(1);
  157 |     const [bodyEdgeBox, outlookBox] = await Promise.all([
  158 |       page.locator("#spot-meteogramm").boundingBox(),
  159 |       outlook.boundingBox(),
  160 |     ]);
  161 |     expect(bodyEdgeBox).not.toBeNull();
  162 |     expect(outlookBox).not.toBeNull();
  163 |     expect(Math.abs((bodyEdgeBox!.x + bodyEdgeBox!.width) - (outlookBox!.x + outlookBox!.width))).toBeLessThanOrEqual(1);
  164 |     const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  165 |     expect(overflow).toBeLessThanOrEqual(1);
  166 |   });
  167 | }
  168 | 
  169 | test("Meteogramm-Auswahl per Pointer aktualisiert die geteilte Auswahl", async ({ page }) => {
  170 |   await page.setViewportSize({ width: 1280, height: 900 });
  171 |   await mockApi(page);
  172 |   await page.goto("/spot/test/daten");
  173 |   const strip = page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" });
  174 |   await strip.click({ position: { x: 30, y: 90 } });
  175 |   // The live-region summary reflects a concrete selected hour.
  176 |   await expect(page.getByText(/Ausgewählt 2026-09-05/)).toBeAttached();
  177 | });
  178 | 
  179 | test("Tag zehn springt in seinen Stundenforecast", async ({ page }) => {
  180 |   await page.setViewportSize({ width: 1280, height: 900 });
  181 |   await mockApi(page);
  182 |   await page.goto("/spot/test/daten");
  183 | 
  184 |   const navigator = page.getByRole("group", { name: "Tagesübersicht — Tag im Stundenforecast anzeigen" });
  185 |   await navigator.getByRole("button", { name: /MO 14\.09/ }).click();
  186 | 
  187 |   await expect(page.getByText(/Ausgewählt 2026-09-14 06:00/)).toBeAttached();
  188 |   await expect.poll(async () => page.locator("#spot-meteogram-scroll").evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  189 | });
  190 | 
  191 | test("Info und Daten behalten beim Tabwechsel dieselbe Scrollhöhe", async ({ page }) => {
  192 |   await page.setViewportSize({ width: 1280, height: 900 });
  193 |   await mockApi(page);
  194 |   await page.goto("/spot/test/info");
  195 |   await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  196 | 
  197 |   // Native programmatic scrolling is deterministic under both the desktop
  198 |   // Lenis layer and touch emulation; wheel events depend on runner timing.
  199 |   await expect
```