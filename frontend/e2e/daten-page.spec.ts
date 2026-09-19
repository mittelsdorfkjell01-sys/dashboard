import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import type { CommunityImage } from "../src/lib/api";

// Regression coverage for the rebuilt Daten page (Figma Frame 67): the dark
// instrument composition — meteogram, today summary + 10-day outlook, map +
// live-wind sidebar, wind-months field. Replaces the retired
// meteogram-accessibility / public-tides specs, whose subjects (hourly
// meteogram controls, data table, direction-compass card, tide panel) were
// intentionally removed in the rebuild.

const spot = { id: "test", slug: "laboe", name: "Alcyons", region_id: "r1", location: { lat: 54.4, lon: 10.2 }, sports: ["surf"], water_type: ["sea"], bottom_type: ["sand"], level: ["advanced"], water_character: ["welle_klein"], style: ["wave_riding"], facilities: null, status: "published", confidence: null, facing: 45, image: null, era5_cell: null, model_pref: null, editorial: { description: "Testspot" }, climatology: null, overrides: null, finish_rank: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-08-24T00:00:00Z" };
const conditions = ["clear", "partly_cloudy", "rain", "snow", "thunderstorm", "overcast", "drizzle", "mainly_clear"] as const;
const summary = (i: number) => ({ wind_avg: 12, wind_max: 18, gust_max: 24, air_min: 16 + i, air_max: 24 + i, swell_max: 1.8, apparent_temperature_max_c: 23, precipitation_sum_mm: 0.5, uv_index_max: 9, weather_condition: conditions[i % conditions.length] });
const forecastDates = ["2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13", "2026-09-14"];
const hourly = forecastDates.map((date, day) => ({
  date,
  local_date: date,
  detail: "hourly",
  confidence: day < 2 ? "hoch" : day < 6 ? "mittel" : "niedrig",
  summary: summary(day),
  hours: Array.from({ length: 24 }, (_, h) => ({
    time: `${date}T${String(h).padStart(2, "0")}:00:00Z`,
    wind: 8 + ((h * 7) % 28),
    gust: 14 + ((h * 7) % 28),
    dir: (180 + h * 23) % 360,
    air: 17 + Math.round(6 * Math.sin(h / 3)),
    precip: h === 12 ? 0.4 : 0,
    swell: 0.4 + ((h * 3) % 9) / 10,
    period: 7 + h / 4,
    swell_dir: 270,
    sst: 18,
    uv_index: Math.max(0, 8 - Math.abs(h - 12)),
    apparent_temperature_c: 23,
    coastal_normal_deg: 180,
    coastal_classification: "onshore",
    weather_condition: conditions[h % conditions.length],
    is_day: h >= 7 && h <= 20,
  })),
}));
const forecast = { spot_id: "test", model: "consensus", product: "Surfwinddata Forecast", generated_at: "2026-09-05T08:00:00Z", updated_at: "2026-09-05T08:00:00Z", timezone: "Europe/Berlin", stale: false, availability: { atmosphere: "available", solar: "available", marine: "available" }, days: hourly };

async function mockApi(page: Page, photos: CommunityImage[] = []) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.startsWith("/media/gallery-")) {
      return route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="800" height="600" fill="#397488"/></svg>',
      });
    }
    if (path === "/spots/version") return route.fulfill({ json: { version: "navigation-test" } });
    if (path === "/spots" || path === "/spots/top") return route.fulfill({ json: [spot] });
    if (path === "/spots/live") return route.fulfill({ json: [] });
    if (["/spots/test", "/spots/laboe", "/spots/Alcyons"].includes(path)) return route.fulfill({ json: spot });
    if (path === "/regions/r1") return route.fulfill({ json: { id: "r1", slug: "kieler-bucht", name: "Kieler Bucht", country: "DE", center: null, description: null, image: null, season: null, defaults: null, status: "published", updated_at: "2026-08-24T00:00:00Z" } });
    if (path === "/spots/test/forecast") return route.fulfill({ json: forecast });
    if (path === "/spots/test/live") return route.fulfill({ json: {
      spot_id: "test", model: "consensus", time: "2026-09-14T12:00:00Z",
      current: { wind: 9, gust: 14, dir: 247, air: 23, sst: 18, swell: 2.5, period: 8, swell_dir: 250, coastal_normal_deg: 180, coastal_classification: "cross_onshore" },
      live_wind: {
        contract_version: "live-wind-v1", product_type: "live_wind", status: "station_adjusted",
        analyzed_at: "2026-09-14T12:05:00Z", valid_at: "2026-09-14T12:00:00Z",
        wind_speed_ms: 10, wind_direction_from_deg: 278, wind_u_ms: 9.99, wind_v_ms: -0.35,
        gust: null, model_version: "consensus-v1", analysis_version: "regional-live-wind-uv-v1",
        station_count: 3, uncertainty_ms: 1, confidence: 0.8,
        sources: [{ source_type: "station_residual", source: "residual:test" }],
        applied_physics_version: "physics-v1", fallback_reason: null,
      },
      measurement: {
        observation_type: "measurement", station_id: "station-test", provider: "DWD", provider_station_id: "01234",
        station_name: "Küstenstation", observed_at: "2026-09-14T11:58:00Z", age_seconds: 420,
        distance_km: 3.2, wind_speed_ms: 7, wind_gust_ms: 9, wind_direction_from_deg: 260, quality: 1,
      },
    } });
    if (path === "/spots/test/tides") return route.fulfill({ status: 404, json: { detail: "none" } });
    if (path === "/spots/test/ratings") return route.fulfill({ json: { items: [], aggregate: { count: 0, average: null } } });
    if (path === "/spots/test/tips") return route.fulfill({ json: [] });
    if (path === "/spots/test/images") return route.fulfill({ json: { items: photos } });
    if (path.startsWith("/spots/test/wind-climatology")) return route.fulfill({ status: 404, json: { detail: "none" } });
    return route.fulfill({ status: 404, json: { detail: `mock missing: ${path}` } });
  });
}

test("Zurück verlässt den Spot auch nach dem Wechsel auf Daten", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/");

  await page.getByRole("link", { name: /Alcyons/ }).last().click();
  await expect(page).toHaveURL(/\/spot\/laboe\/info$/);
  await page.getByRole("tab", { name: "Daten" }).click();
  await expect(page).toHaveURL(/\/spot\/laboe\/daten$/);

  await page.getByRole("button", { name: "Zurück" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("Direkter Spot-Einstieg fällt nach dem Tabwechsel auf die Karte zurück", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/info");

  await expect(page).toHaveURL(/\/spot\/laboe\/info$/);
  await page.getByRole("tab", { name: "Daten" }).click();
  await expect(page).toHaveURL(/\/spot\/laboe\/daten$/);
  await page.getByRole("button", { name: "Zurück" }).click();

  await expect(page).toHaveURL(/\/map$/);
});

test("Galeriebilder werden vor dem Öffnen geladen und liegen im ersten Overlay-Frame bereit", async ({ page }) => {
  const photos: CommunityImage[] = [1, 2].map((id) => ({
    id: `gallery-${id}`,
    url: `/media/gallery-${id}.svg`,
    kind: "gallery",
    width: 800,
    height: 600,
    credit: null,
    created_at: "2026-09-08T12:00:00Z",
    source: "community",
    license_name: null,
    license_url: null,
    source_url: null,
  }));
  const requested = new Set<string>();
  page.on("request", (request) => {
    if (request.url().includes("/media/gallery-")) requested.add(request.url());
  });

  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page, photos);
  await page.goto("/spot/test/info");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  await expect.poll(() => requested.size).toBe(2);
  await expect(page.locator(".spot-media-frame img")).toHaveJSProperty("complete", true);

  await page.getByRole("button", { name: "Fotogalerie öffnen" }).click();
  await expect(page.getByRole("heading", { name: "Fotogalerie" })).toBeVisible();
  await expect(page.locator('[role="dialog"] button.group img')).toHaveCount(2);
});

test("Spot-Karte bleibt beim Herauszoomen randgefüllt und ohne Kachelnähte", async ({ page }) => {
  let delayReplacementTiles = false;
  await page.route("https://server.arcgisonline.com/**", async (route) => {
    if (delayReplacementTiles) await new Promise((resolve) => setTimeout(resolve, 650));
    await route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#73919a"/></svg>',
    });
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/laboe/info");

  const map = page.getByRole("region", { name: "Lage" });
  await expect(map).toBeAttached();
  await map.scrollIntoViewIfNeeded();
  const tile = map.locator(".leaflet-tile").first();
  await expect(tile).toBeVisible();
  await expect(tile).toHaveCSS("filter", "none");
  await expect(tile).toHaveCSS("outline-width", "1px");
  await expect(tile).toHaveCSS("outline-style", "solid");
  await expect(tile).toHaveCSS("outline-color", "rgba(0, 0, 0, 0)");
  const mapZoom = await map.locator(".swd-locator-map").evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).zoom),
  );
  expect(mapZoom).toBeCloseTo(1 / 0.85, 5);
  await expect(map.locator(".leaflet-tile-pane")).not.toHaveCSS("filter", "none");
  const edgeBlend = await map.locator(".swd-locator-map").evaluate((element) =>
    getComputedStyle(element, "::after").boxShadow,
  );
  expect(edgeBlend).toBe("none");

  // A slow replacement level must not uncover the map while several wheel
  // inputs are still being animated. The already loaded level stays scaled
  // beneath it until the new tiles are ready.
  await expect(map.locator(".leaflet-tile-loaded").first()).toBeVisible();
  delayReplacementTiles = true;
  await map.getByRole("button", { name: "Karte aktivieren" }).click();
  await expect(map.locator(".swd-locator-map")).toHaveAttribute("data-lenis-prevent", "");
  const box = await map.locator(".leaflet-container").boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.wheel(0, 120);
  await page.waitForTimeout(35);
  await page.mouse.wheel(0, 120);
  await page.waitForTimeout(80);

  const uncoveredSamples = await map.locator(".leaflet-container").evaluate((container) => {
    const mapRect = container.getBoundingClientRect();
    const tiles = [...container.querySelectorAll<HTMLElement>(".leaflet-tile-loaded")]
      .filter((tile) => {
        const level = tile.closest<HTMLElement>(".leaflet-tile-container");
        return getComputedStyle(tile).visibility !== "hidden" && (!level || Number.parseFloat(getComputedStyle(level).opacity) > 0);
      })
      .map((tile) => tile.getBoundingClientRect());
    const samples = [0.01, 0.25, 0.5, 0.75, 0.99].flatMap((x) =>
      [0.01, 0.5, 0.99].map((y) => ({
        x: mapRect.left + mapRect.width * x,
        y: mapRect.top + mapRect.height * y,
      })),
    );
    return samples.filter((point) => !tiles.some((tile) =>
      point.x >= tile.left && point.x <= tile.right && point.y >= tile.top && point.y <= tile.bottom,
    ));
  });
  expect(uncoveredSamples).toEqual([]);
});

test("Daten-Seite zeigt Meteogramm, Ausblick und Livewind", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  // Meteogram row labels + the direction/time axes.
  await expect(page.getByText("WELLE", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("RICHT.", { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" })).toBeVisible();
  // The complete 10-day outlook renders through the last hourly day.
  await expect(page.getByText("SA 05.09", { exact: true })).toBeVisible();
  await expect(page.getByText("MO 14.09", { exact: true })).toBeVisible();
  await expect(page.locator("#spot-meteogram-scroll [data-forecast-day]")).toHaveCount(10);
  // Live-wind sidebar metrics.
  await expect(page.getByText("UV INDEX", { exact: true })).toBeVisible();
  await expect(page.getByText("GEFÜHLT", { exact: true })).toBeVisible();
  const current = page.locator('[data-weather-time-mode="now"]');
  await expect(current).toHaveAttribute("data-live-wind-status", "station_adjusted");
  await expect(current.getByText("Aktuelle Bedingungen", { exact: true })).toBeVisible();
  await expect(current.getByText("Stationskorrigiert", { exact: true })).toBeVisible();
  await expect(current.getByText("Relevante Stationen", { exact: true })).toBeVisible();
  await expect(current.getByText("Küstenstation", { exact: false })).toBeVisible();
  await expect(current.getByText(/Gemessen .*11:58/)).toBeVisible();
  await expect(page.locator(".swd-spot-map")).toHaveAttribute("data-observation-type", "live_wind");
});

test("Forecast-Scrubbing ersetzt LiveWind nur im Forecastmodus und Jetzt stellt es wieder her", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");

  const map = page.locator(".swd-spot-map");
  await expect(map).toHaveAttribute("data-observation-type", "live_wind");
  const navigator = page.getByRole("group", { name: "Tagesübersicht — Tag im Stundenforecast anzeigen" });
  await navigator.getByRole("button").first().click();

  await expect(map).toHaveAttribute("data-observation-type", "forecast");
  const forecastSidebar = page.locator('[data-weather-time-mode="forecast"]');
  await expect(forecastSidebar.getByRole("heading", { name: "Forecast" })).toBeVisible();
  await expect(forecastSidebar.getByText("Referenzmessung", { exact: false })).toHaveCount(0);

  await forecastSidebar.getByRole("button", { name: "Jetzt" }).click();
  await expect(map).toHaveAttribute("data-observation-type", "live_wind");
  await expect(page.locator('[data-weather-time-mode="now"]')).toBeVisible();
});

test("Offline bleibt die letzte Analyse sichtbar und wird ehrlich gekennzeichnet", async ({ page, context }) => {
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.locator('[data-live-wind-status="station_adjusted"]')).toBeVisible();
  await context.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  await expect(page.getByText("Offline: Die zuletzt geladene Analyse wird weiter angezeigt.")).toBeVisible();
});

test("fehlendes LiveWind fällt sichtbar auf den Modell-Nowcast zurück", async ({ page }) => {
  await mockApi(page);
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/spots\/test\/live$/, (route) => route.fulfill({ json: {
    spot_id: "test", model: "consensus", time: "2026-09-14T12:00:00Z",
    current: { wind: 9, gust: 14, dir: 247, air: 23, sst: 18, swell: 2.5, period: 8, swell_dir: 250 },
    live_wind: {
      contract_version: "live-wind-v1", product_type: "live_wind", status: "unavailable",
      analyzed_at: null, valid_at: null, wind_speed_ms: null, wind_direction_from_deg: null,
      wind_u_ms: null, wind_v_ms: null, gust: null, model_version: null, analysis_version: null,
      station_count: 0, uncertainty_ms: null, confidence: null, sources: [],
      applied_physics_version: null, fallback_reason: "station_residuals_unavailable",
    },
  } }));
  await page.goto("/spot/test/daten");
  await expect(page.locator(".swd-spot-map")).toHaveAttribute("data-observation-type", "nowcast");
  await expect(page.locator('[data-live-wind-status="baseline"]')).toBeVisible();
  await expect(page.getByText(/keine ausreichend aktuellen Stationsresiduen/)).toBeVisible();
});

test("Info-Locator bleibt statisch und lädt kein LiveWind", async ({ page }) => {
  let liveRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/spots/test/live") liveRequests += 1;
  });
  await mockApi(page);
  await page.goto("/spot/test/info");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  // The desktop locator is intentionally lazy-rendered. Scroll its stable
  // semantic slot into view first so the IntersectionObserver may mount the
  // map; waiting on the lazy child itself can never trigger that observer.
  // A synchronous DOM scroll also avoids Playwright waiting for the tab's
  // entrance animation while React legitimately rerenders the lazy slot.
  const locatorRegion = page.getByRole("region", { name: "Lage" });
  await expect(locatorRegion).toBeAttached();
  await locatorRegion.evaluate((element) => element.scrollIntoView({ block: "center" }));
  await expect(page.locator(".swd-locator-map")).toBeVisible();
  await expect(page.locator(".swd-locator-map [data-observation-type]")).toHaveCount(0);
  expect(liveRequests).toBe(0);
});

for (const width of [320, 375, 768, 1280, 1440]) {
  test(`Daten-Seite bleibt bei ${width}px innerhalb der Seite`, async ({ page }) => {
    await page.setViewportSize({ width, height: width < 500 ? 720 : 900 });
    await mockApi(page);
    await page.goto("/spot/test/daten");
    await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
    const outlook = page.locator(".forecast-weather-grid");
    await expect(outlook.getByRole("button")).toHaveCount(10);
    const navigator = page.getByRole("group", { name: "Tagesübersicht — Tag im Stundenforecast anzeigen" });
    await expect(navigator.getByRole("button")).toHaveCount(10);
    const navigatorOverflow = await navigator.evaluate((element) => element.scrollWidth - element.clientWidth);
    expect(navigatorOverflow).toBeLessThanOrEqual(1);
    const [bodyEdgeBox, outlookBox] = await Promise.all([
      page.locator("#spot-meteogramm").boundingBox(),
      outlook.boundingBox(),
    ]);
    expect(bodyEdgeBox).not.toBeNull();
    expect(outlookBox).not.toBeNull();
    expect(Math.abs((bodyEdgeBox!.x + bodyEdgeBox!.width) - (outlookBox!.x + outlookBox!.width))).toBeLessThanOrEqual(1);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test("Meteogramm-Auswahl per Pointer aktualisiert die geteilte Auswahl", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  const strip = page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" });
  await strip.scrollIntoViewIfNeeded();
  const box = await strip.boundingBox();
  expect(box).not.toBeNull();
  await strip.dispatchEvent("pointerdown", {
    pointerId: 1,
    clientX: box!.x + 30,
    clientY: box!.y + 90,
  });
  // The live-region summary reflects a concrete selected hour.
  await expect(page.getByText(/Ausgewählt 2026-09-05/)).toBeAttached();
});

test("Tag zehn springt in seinen Stundenforecast", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");

  const navigator = page.getByRole("group", { name: "Tagesübersicht — Tag im Stundenforecast anzeigen" });
  await navigator.getByRole("button", { name: /MO 14\.09/ }).click();

  await expect(page.getByText(/Ausgewählt 2026-09-14 06:00/)).toBeAttached();
  await expect.poll(async () => page.locator("#spot-meteogram-scroll").evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
});

test("Info und Daten behalten beim Tabwechsel dieselbe Scrollhöhe", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/info");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();

  // Native programmatic scrolling is deterministic under both the desktop
  // Lenis layer and touch emulation; wheel events depend on runner timing.
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight))
    .toBeGreaterThan(480);
  await page.evaluate(() => window.scrollTo(0, 480));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  const infoScrollY = await page.evaluate(() => window.scrollY);
  await page.getByRole("tab", { name: "Daten" }).click();
  await expect(page).toHaveURL(/\/spot\/laboe\/daten$/);
  await expect(page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" })).toBeVisible();
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => window.scrollY)).toBe(infoScrollY);

  const datenScrollY = await page.evaluate(() => window.scrollY);
  await page.getByRole("tab", { name: "Info" }).click();
  await expect(page).toHaveURL(/\/spot\/laboe\/info$/);
  await expect(page.getByRole("heading", { name: "Alcyons" })).toHaveCount(1);
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => window.scrollY)).toBe(datenScrollY);
});

test("Daten-Seite ist axe-konform (mobil)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
