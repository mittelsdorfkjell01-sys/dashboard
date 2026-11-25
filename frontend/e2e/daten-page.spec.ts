import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { gzipSync } from "node:zlib";
import type { CommunityImage } from "../src/lib/api";

// Regression coverage for the rebuilt Daten page (Figma Frame 67 / 79): the
// dark instrument composition — meteogram, today summary + 10-day outlook,
// wind-months field. The page carries no map of its own since 2026-10-10: the
// "Karte" button links into the one weather map, framed on the spot and locked
// to the wind field.

const spot = { id: "test", slug: "laboe", name: "Alcyons", region_id: "r1", region_name: "Kieler Bucht", region_country: "DE", location: { lat: 54.4, lon: 10.2 }, sports: ["surf"], water_type: ["sea"], bottom_type: ["sand"], level: ["advanced"], water_character: ["welle_klein"], style: ["wave_riding"], facilities: { parking: { available: true, note: "Direkt am Deich" }, school: { available: true, note: "Kurse vor Ort" }, shower: { available: false, note: null }, food: { available: true, note: "Saisonal geöffnet" } }, status: "published", confidence: null, facing: 45, origin: "community", contributor_name: "Lena K.", editorial_classification: "worth_trip", content_status: "verified", content_reviewed_at: "2026-08-24T00:00:00Z", content_review_due_at: "2027-08-24T00:00:00Z", content_sources: [], image: null, era5_cell: null, model_pref: null, editorial: { description: "Ein vielseitiger Küstenspot mit ausreichend Platz auf dem Wasser und einem gut erreichbaren Einstieg. Bei wechselnden Bedingungen lohnt sich vor der Anfahrt ein genauer Blick auf Windrichtung, Wasserstand und lokale Hinweise. Der Uferbereich kann je nach Wetter deutlich anspruchsvoller werden, deshalb sollten weniger erfahrene Wassersportlerinnen und Wassersportler besonders aufmerksam planen." }, climatology: null, overrides: null, finish_rank: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-08-24T00:00:00Z" };
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
const forecastSummary = {
  spot_id: "test", model: "consensus", generated_at: "2026-09-14T11:55:00Z", timezone: "Europe/Berlin",
  hour: {
    time: "2026-09-14T12:00:00Z", wind: 9, gust: 14, dir: 247, air: 23, sst: 18,
    swell: 2.5, period: 8, swell_dir: 250, precip: 0, quality_tier: "coastal",
    coastal_normal_deg: 67, coastal_profile_reviewed_at: "2026-08-01T08:00:00Z",
    coastal_classification: "offshore", stale: false,
    provenance: {
      contract_version: "weather-v6", source_type: "forecast", observation_type: "forecast",
      source: "model", provider: "Open-Meteo", valid_at: "2026-09-14T12:00:00Z",
      captured_at: "2026-09-14T11:55:00Z", model_run_quality: "capture-time-only",
      spot_timezone: "Europe/Berlin", stale: false, availability: "available",
      quality_tier: "provider_point", uncertainty: "not_determined", data_issues: [],
    },
  },
};

const tideStart = new Date();
tideStart.setUTCMinutes(0, 0, 0);
const tideSeries = Array.from({ length: 73 }, (_, index) => {
  const level = Math.sin((2 * Math.PI * index) / 12.42);
  return {
    time: new Date(tideStart.getTime() + index * 3_600_000).toISOString(),
    level_normalized: (level + 1) / 2,
    level_m: Number((0.72 * level).toFixed(3)),
    phase: level >= 0 ? "rising" : "falling",
  };
});
const tideEvents = Array.from({ length: 10 }, (_, index) => ({
  id: `tide-${index}`,
  event_type: index % 2 === 0 ? "high" : "low",
  time: new Date(tideStart.getTime() + (index * 6 + 3) * 3_600_000).toISOString(),
  uncertainty_minutes: 90,
}));
const modelledTide = {
  available: true,
  product_type: "modelled_sea_level",
  message: "Begrenzte Genauigkeit an Küsten, in Buchten und Flussmündungen.",
  timezone: "Europe/Berlin",
  phase: "rising",
  cycle_position: 0.4,
  quality: "model_only",
  approximate: true,
  last_calculated_at: tideStart.toISOString(),
  valid_until: tideSeries.at(-1)!.time,
  forecast_start: tideSeries[0].time,
  forecast_end: tideSeries.at(-1)!.time,
  horizon_days: 3,
  partial: true,
  datum: "mean_sea_level",
  current_level_m: 0.18,
  navigational: false,
  model_name: "Open-Meteo Marine Best Match",
  model_version: null,
  source_name: "Open-Meteo Marine",
  source_url: "https://open-meteo.com/en/docs/marine-weather-api",
  attribution: "Open-Meteo Marine · Datenquelle: Copernicus Marine / Météo-France",
  events: tideEvents,
  series: tideSeries,
};

function weatherFieldTile(z: number, x: number, y: number): Buffer {
  const width = 130;
  const variables = [
    { name: "wind_u", dtype: "int16", scale: .05, offset: 0, nodata: -32768 },
    { name: "wind_v", dtype: "int16", scale: .05, offset: 0, nodata: -32768 },
    { name: "wind_gust", dtype: "int16", scale: .05, offset: 0, nodata: -32768 },
  ];
  const header = Buffer.from(JSON.stringify({ schema: "swd-field-tile-v2", width, height: width, layout: "planar", byte_order: "little", variables, valid_time: hourly[0].hours[0].time, z, x, y, overlap: 1 }));
  const prefix = Buffer.alloc(8); prefix.write("SWF2", 0); prefix.writeUInt32LE(header.length, 4);
  const cells = width * width;
  const body = Buffer.alloc(cells * 2 * variables.length);
  [100, 40, 160].forEach((value, variable) => { for (let index = 0; index < cells; index += 1) body.writeInt16LE(value, (variable * cells + index) * 2); });
  return gzipSync(Buffer.concat([prefix, header, body]));
}

async function mockApi(page: Page, photos: CommunityImage[] = [], withWeatherField = false) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.startsWith("/media/gallery-")) {
      return route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="800" height="600" fill="#397488"/></svg>',
      });
    }
    if (["/spots/test", "/spots/laboe", "/spots/Alcyons"].includes(path)) return route.fulfill({ json: spot });
    if (path === "/map/pois") return route.fulfill({ json: {
      source: "OpenStreetMap", attribution: "© OpenStreetMap-Mitwirkende", incomplete: true,
      items: [
        { id: "node/1", category: "parking", name: "Strandparkplatz", lat: 54.3995, lon: 10.1995, distance_m: 130, osm_url: "https://www.openstreetmap.org/node/1" },
        { id: "node/2", category: "cafe", name: "Dünen Café", lat: 54.401, lon: 10.201, distance_m: 260, osm_url: "https://www.openstreetmap.org/node/2", opening_hours: "Mo-Fr 09:00-18:00", website: "https://duenen.example/", outdoor_seating: true, cuisine: ["coffee shop"], vegetarian: "yes", vegan: "limited", card_payment: false, instagram: "https://www.instagram.com/duenencafe/" },
        { id: "node/3", category: "bar", name: "Beach Bar", lat: 54.4015, lon: 10.2015, distance_m: 390, osm_url: "https://www.openstreetmap.org/node/3" },
        { id: "node/4", category: "surf_school", name: "Windwerk", lat: 54.402, lon: 10.202, distance_m: 520, osm_url: "https://www.openstreetmap.org/node/4" },
        { id: "node/5", category: "campsite", name: "Küstencamp", lat: 54.4025, lon: 10.2025, distance_m: 650, osm_url: "https://www.openstreetmap.org/node/5" },
      ],
    } });
    if (path === "/regions/r1") return route.fulfill({ json: { id: "r1", slug: "kieler-bucht", name: "Kieler Bucht", country: "DE", center: null, description: null, image: null, season: null, defaults: null, status: "published", updated_at: "2026-08-24T00:00:00Z" } });
    if (path === "/spots/test/forecast") return route.fulfill({ json: forecast });
    if (path === "/spots/test/forecast-summary") return route.fulfill({ json: forecastSummary });
    if (path === "/spots/test/live") return route.fulfill({ json: {
      spot_id: "test", model: "consensus", time: "2026-09-14T12:00:00Z",
      quality_tier: "coastal", coastal_normal_deg: 67,
      current: { wind: 9, gust: 14, dir: 247, air: 23, sst: 18, swell: 2.5, period: 8, swell_dir: 250, coastal_normal_deg: 67, coastal_classification: "offshore" },
      sources: Object.fromEntries(["wind", "air", "marine"].map((kind) => [kind, {
        contract_version: "weather-v6", source_type: "model_nowcast", observation_type: "nowcast",
        source: "model", provider: "Open-Meteo", valid_at: "2026-09-14T12:00:00Z",
        captured_at: "2026-09-14T11:55:00Z", model_run_quality: "capture-time-only",
        spot_timezone: "Europe/Berlin", requested_coordinate: { latitude: 54.4, longitude: 10.2 },
        stale: false, availability: "available", quality_tier: "provider_point",
        attribution: [], uncertainty: "not_determined", data_issues: [],
      }])),
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
    if (withWeatherField && path === "/weather-fields/wind") return route.fulfill({ json: {
      enabled: true, public: true, status: "fresh", publication_id: "publication-test", generation: 1,
      manifest_url: "/weather-field-assets/europe-wind/icon-eu/manifest.json",
      manifest: {
        contract_version: "weather-field-v2", publication_id: "publication-test", provider: "dwd", model: "icon-eu",
        model_run: "2026-09-05T00:00:00Z", published_at: "2026-09-05T01:00:00Z",
        valid_times: hourly.flatMap((day) => day.hours.map((hour) => hour.time)),
        coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
        variables: [
          { name: "wind_u", unit: "m/s", semantic: "eastward", height_m: 10 },
          { name: "wind_v", unit: "m/s", semantic: "northward", height_m: 10 },
          { name: "wind_gust", unit: "m/s", semantic: "magnitude", height_m: 10 },
        ],
        compression: "gzip", quality_status: "validated",
        freshness: { status: "fresh", age_seconds: 3600, expected_next_run_at: "2026-09-05T06:00:00Z" },
        attribution: [{ provider: "Deutscher Wetterdienst", text: "DWD Open Data", url: "https://opendata.dwd.de/", licence: "GeoNutzV" }],
        field_template: "/weather-field-assets/europe-wind/icon-eu/assets/{valid_time}/{z}/{x}/{y}.swf2.gz",
        tile_scheme: { tile_size: 128, overlap: 1, lod: [
          { source_zoom: 4, consumer_zoom_min: 0, consumer_zoom_max: 5, source_decimation: 1 },
          { source_zoom: 5, consumer_zoom_min: 6, consumer_zoom_max: 16, source_decimation: 1 },
        ] },
      },
    } });
    if (withWeatherField && path === "/weather-fields/waves") return route.fulfill({ json: {
      enabled: true, public: true, status: "fresh", publication_id: "wave-publication-test", generation: 1,
      manifest_url: "/weather-field-assets/europe-wave/ewam/manifest.json",
      manifest: {
        contract_version: "weather-field-v2", publication_id: "wave-publication-test", provider: "dwd", model: "ewam",
        model_run: "2026-09-05T00:00:00Z", published_at: "2026-09-05T01:00:00Z",
        valid_times: hourly.flatMap((day) => day.hours.map((hour) => hour.time)),
        coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
        variables: [
          { name: "wave_u", unit: "m/s", semantic: "eastward" },
          { name: "wave_v", unit: "m/s", semantic: "northward" },
          { name: "total_wave_height", unit: "m", semantic: "magnitude" },
        ],
        compression: "gzip", quality_status: "validated",
        freshness: { status: "fresh", age_seconds: 3600, expected_next_run_at: "2026-09-05T06:00:00Z" },
        attribution: [{ provider: "Deutscher Wetterdienst", text: "DWD Open Data", url: "https://opendata.dwd.de/", licence: "GeoNutzV" }],
        field_template: "/weather-field-assets/europe-wave/ewam/assets/{valid_time}/{z}/{x}/{y}.swf2.gz",
        tile_scheme: { tile_size: 128, overlap: 1, lod: [
          { source_zoom: 4, consumer_zoom_min: 0, consumer_zoom_max: 5, source_decimation: 1 },
          { source_zoom: 5, consumer_zoom_min: 6, consumer_zoom_max: 16, source_decimation: 1 },
        ] },
      },
    } });
    if (withWeatherField && path === "/weather-fields/waves/sample") {
      const validAt = new URL(route.request().url()).searchParams.get("valid_at") ?? hourly[0].hours[0].time;
      return route.fulfill({ json: {
        product: "model_wave", publication_id: "wave-publication-test", generation: 1, run_id: "wave-run-test", provider: "dwd", model: "ewam",
        model_run: "2026-09-05T00:00:00Z", valid_at: validAt, latitude: 54.4, longitude: 10.2,
        wave_u: 0.4, wave_v: 0.9, total_wave_height_m: 1.4, total_wave_direction_from_deg: 300, total_wave_period_s: 7,
        wind_sea_height_m: 0.8, wind_sea_direction_from_deg: 290, wind_sea_period_s: 4,
        primary_swell_height_m: 1.1, primary_swell_direction_from_deg: 310, primary_swell_period_s: 9,
        interpolation: "bilinear_uv", freshness: "fresh",
      } });
    }
    if (withWeatherField && path === "/weather-fields/wind/sample") {
      const validAt = new URL(route.request().url()).searchParams.get("valid_at") ?? hourly[0].hours[0].time;
      return route.fulfill({ json: {
        product: "model_wind", publication_id: "publication-test", generation: 1, run_id: "run-test", provider: "dwd", model: "icon-eu",
        model_run: "2026-09-05T00:00:00Z", valid_at: validAt, latitude: 54.4, longitude: 10.2,
        u_ms: 5, v_ms: 2, speed_ms: 5.385, direction_from_deg: 248, gust_ms: 8, interpolation: "bilinear_uv", freshness: "fresh",
      } });
    }
    if (withWeatherField && path.startsWith("/weather-field-assets/")) {
      const match = path.match(/\/(\d+)\/(\d+)\/(\d+)\.swf2\.gz$/);
      if (!match) return route.fulfill({ status: 404 });
      return route.fulfill({ body: weatherFieldTile(Number(match[1]), Number(match[2]), Number(match[3])), contentType: "application/gzip" });
    }
    if (path === "/spots/test/tides") return route.fulfill({ json: modelledTide });
    if (path === "/spots/test/ratings") return route.fulfill({ json: { items: [], aggregate: { count: 0, average: null } } });
    if (path === "/spots/test/tips") return route.fulfill({ json: [] });
    if (path === "/spots/test/images") return route.fulfill({ json: { items: photos } });
    if (path.startsWith("/spots/test/wind-climatology")) return route.fulfill({ status: 404, json: { detail: "none" } });
    return route.fulfill({ status: 404, json: { detail: `mock missing: ${path}` } });
  });
  if (withWeatherField) {
    await page.route(/https:\/\/[a-d]\.basemaps\.cartocdn\.com\/.*\.png(?:\?.*)?$/, (route) => route.fulfill({
      body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64"),
      contentType: "image/png",
    }));
  }
}

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

// The spot map draws OpenFreeMap vector tiles. An empty protobuf is a valid,
// empty tile (and an empty glyph range), so the map settles without network.
async function mockMapTiles(page: Page, options: { failTiles?: () => boolean } = {}) {
  const counts = { tilejson: 0, tiles: 0, glyphs: 0 };
  await page.route(/https:\/\/tiles\.openfreemap\.org\/.*/, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/planet") {
      counts.tilejson += 1;
      return route.fulfill({ json: {
        tilejson: "3.0.0", minzoom: 0, maxzoom: 14,
        tiles: ["https://tiles.openfreemap.org/planet/test/{z}/{x}/{y}.pbf"],
      } });
    }
    if (path.startsWith("/fonts/")) {
      counts.glyphs += 1;
      return route.fulfill({ contentType: "application/x-protobuf", body: Buffer.alloc(0) });
    }
    counts.tiles += 1;
    if (options.failTiles?.()) return route.abort("failed");
    return route.fulfill({ contentType: "application/x-protobuf", body: Buffer.alloc(0) });
  });
  return counts;
}

async function openLocator(page: Page) {
  await mockApi(page);
  await page.goto("/spot/laboe/info");
  const map = page.getByRole("region", { name: "Lage", exact: true });
  await expect(map).toBeAttached();
  await map.evaluate((element) => element.scrollIntoView({ block: "center" }));
  await expect(map.locator(".swd-locator-map .maplibregl-canvas")).toBeVisible();
  return map;
}

async function zoomTo(map: ReturnType<Page["getByRole"]>, target: number) {
  const root = map.locator(".swd-locator-map");
  for (let step = 0; step < 12; step += 1) {
    const current = Number(await root.getAttribute("data-current-zoom"));
    if (current >= target) return;
    await map.getByRole("button", { name: "Vergrößern" }).click();
    await expect.poll(async () => Number(await root.getAttribute("data-current-zoom"))).toBeGreaterThan(current + 0.5);
  }
}

test("Spot-Karte zeigt die Standardkarte mit bloßen Glyphen als Bedienelementen", async ({ page }) => {
  const tiles = await mockMapTiles(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  const map = await openLocator(page);
  const root = map.locator(".swd-locator-map");

  await expect(root).toHaveAttribute("data-visible-ready-ms", /\d/);
  expect(tiles.tilejson).toBeGreaterThan(0);
  expect(tiles.tiles).toBeGreaterThan(0);
  // The spot page no longer shrinks its desktop body with CSS zoom.
  expect(await root.evaluate((element) => Number.parseFloat(getComputedStyle(element).zoom))).toBeCloseTo(1, 5);
  // The map follows the site theme (2026-11-22); it is no longer pinned light.
  await expect(root).not.toHaveClass(/sw-theme-light/);
  await expect(root).toHaveCSS("background-color", "rgb(244, 242, 238)");
  // The spot is /map's small dot (12px, 16px with the house mark), not a halo disc.
  await expect(map.locator(".swd-locator-spot .swd-locator-dot")).toHaveCSS("width", /^(12|16)px$/);
  // Controls are bare dark glyphs, not buttons with a surface.
  const zoomIn = map.getByRole("button", { name: "Vergrößern" });
  await expect(zoomIn).toHaveCSS("color", "rgb(26, 31, 36)");
  await expect(zoomIn).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");

  for (const control of [
    map.getByRole("button", { name: "Vergrößern" }),
    map.getByRole("button", { name: "Verkleinern" }),
    map.getByRole("button", { name: "Dein Standort" }),
    map.getByRole("link", { name: "Route zum Spot in Karten-App öffnen" }),
    map.getByRole("button", { name: "Kartenquellen anzeigen" }),
  ]) {
    const box = await control.boundingBox();
    expect(box?.width).toBeGreaterThanOrEqual(44);
    expect(box?.height).toBeGreaterThanOrEqual(44);
  }
  await expect(map.getByRole("link", { name: "Route zum Spot in Karten-App öffnen" }))
    .toHaveAttribute("href", /destination=54\.4%2C10\.2|daddr=54\.4%2C10\.2/);

  // Locked until clicked: page scroll is never hijacked.
  await map.getByRole("button", { name: "Karte aktivieren" }).click();
  await expect(root).toHaveAttribute("data-map-active", "true");
  await expect(root).toHaveAttribute("data-lenis-prevent", "");
  await expect(map.locator(".maplibregl-canvas")).toBeFocused();

  await map.getByRole("button", { name: "Kartenquellen anzeigen" }).click();
  await expect(map.getByRole("complementary", { name: "Kartenquellen" })).toContainText("OpenFreeMap");
  await expect(map.getByRole("complementary", { name: "Kartenquellen" })).toContainText("OpenStreetMap");
});

test("Spot-Karte blendet Orte gestaffelt ein, ohne sie zu stapeln, und zeigt Details", async ({ page }) => {
  await mockMapTiles(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  // Wednesday 11:00 in Berlin (the spot's zone in the mock): the café is open.
  await page.clock.setFixedTime(new Date("2026-11-18T10:00:00Z"));
  const map = await openLocator(page);
  const root = map.locator(".swd-locator-map");
  const visiblePins = map.locator(".swd-poi:not([hidden])");

  await expect(visiblePins).toHaveCount(0);
  await zoomTo(map, 14.05);
  // Surf school, parking and camping first; café and bar need a closer look.
  await expect(map.locator(".swd-poi-surf_school:not([hidden])")).toHaveCount(1);
  await expect(map.locator(".swd-poi-cafe:not([hidden])")).toHaveCount(0);
  await zoomTo(map, 14.9);
  await expect(visiblePins).toHaveCount(5);
  await expect(map.locator(".swd-poi.has-label")).toHaveCount(0);
  // Names follow from the label zoom; a name never covers another pin.
  await zoomTo(map, 15.6);
  await expect(map.locator(".swd-poi.has-label").first()).toBeVisible();

  // No two visible pins overlap.
  const boxes = await visiblePins.evaluateAll((elements) => elements.map((element) => {
    const rect = element.querySelector(".swd-poi-disc")!.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
  }));
  for (const [index, a] of boxes.entries()) {
    for (const b of boxes.slice(index + 1)) {
      expect(a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top).toBe(false);
    }
  }

  await map.getByRole("button", { name: "Karte aktivieren" }).click();
  await map.getByRole("button", { name: "Café: Dünen Café" }).click();
  const sheet = map.getByRole("complementary", { name: "Café: Dünen Café" });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole("heading", { name: "Dünen Café" })).toBeVisible();
  await expect(sheet.getByText("Mo–Fr 09:00–18:00")).toBeVisible();
  await expect(sheet.getByText("Café · 260 m vom Spot")).toBeVisible();
  // Open/closed sits on the name's line, flush right, in the status green.
  const badge = sheet.getByText("Geöffnet", { exact: true });
  await expect(badge).toHaveCSS("color", "rgb(21, 128, 61)");
  const [badgeBox, titleBox] = [await badge.boundingBox(), await sheet.getByRole("heading", { name: "Dünen Café" }).boundingBox()];
  expect(Math.abs((badgeBox?.y ?? 0) + (badgeBox?.height ?? 0) / 2 - ((titleBox?.y ?? 0) + (titleBox?.height ?? 0) / 2))).toBeLessThan(6);
  expect(badgeBox?.x ?? 0).toBeGreaterThan((titleBox?.x ?? 0) + 100);
  // Minimal card (Variante B, 2026-11-21): name, distance, hours, one hand-off.
  // Chromium is not Safari, so the hand-off is Google Maps.
  await expect(sheet.getByRole("link", { name: "In Google Maps öffnen" })).toHaveAttribute("href", /google\.com\/maps\/search\/\?api=1&query=/);
  await expect(sheet.getByRole("link")).toHaveCount(1);
  for (const gone of ["Website", "Instagram", "Anrufen", "Route", "In OpenStreetMap ansehen"]) {
    await expect(sheet.getByRole("link", { name: gone, exact: true })).toHaveCount(0);
  }
  await expect(sheet.getByText("Nur bar")).toHaveCount(0);
  await expect(sheet.getByText("Daten © OpenStreetMap-Mitwirkende")).toBeVisible();
  await expect(map.locator('.swd-poi[data-selected="true"]')).toHaveCount(1);

  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  for (let step = 0; step < 4; step += 1) await map.getByRole("button", { name: "Verkleinern" }).click();
  await expect.poll(async () => Number(await root.getAttribute("data-current-zoom"))).toBeLessThan(13.5);
  await expect(visiblePins).toHaveCount(0);
});

test("Spot-Karte setzt den eigenen Standort per GPS oder auf der Karte und übergibt die Route", async ({ page, context }) => {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 54.33, longitude: 10.13 });
  await mockMapTiles(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  const map = await openLocator(page);

  await map.getByRole("button", { name: "Dein Standort" }).click();
  const sheet = map.getByRole("complementary", { name: "Dein Standort" });
  await expect(sheet.getByText("Noch nicht festgelegt")).toBeVisible();
  await sheet.getByRole("button", { name: "Aktuellen Standort verwenden" }).click();
  await expect(sheet.getByText(/GPS · \d+,?\d* km zum Spot/)).toBeVisible();
  await expect(map.getByRole("img", { name: "Dein Standort" })).toBeVisible();
  await expect(map.getByRole("link", { name: "Route zum Spot in Karten-App öffnen" })).toHaveAttribute("href", /(origin|saddr)=54\.33%2C10\.13/);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("swd.mapLocation") ?? "null")))
    .toEqual({ lat: 54.33, lon: 10.13, source: "gps" });

  await sheet.getByRole("button", { name: "Auf der Karte wählen" }).click();
  await expect(map.locator(".swd-locator-crosshair")).toBeVisible();
  await map.getByRole("button", { name: "Hier setzen" }).click();
  await expect(map.getByRole("complementary", { name: "Dein Standort" }).getByText(/Auf der Karte gesetzt/)).toBeVisible();

  await map.getByRole("complementary", { name: "Dein Standort" }).getByRole("button", { name: "Entfernen" }).click();
  await expect(map.locator(".swd-locator-user")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("swd.mapLocation"))).toBeNull();
});

test("Spot-Karte öffnet auf dem Handy im Vollbild, mit Touch-Zielen und Reduced Motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockMapTiles(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const map = await openLocator(page);

  await map.getByRole("button", { name: "Karte im Vollbild öffnen" }).click();
  const close = map.getByRole("button", { name: "Vollbild schließen" });
  await expect(close).toBeVisible();
  await expect(close).toBeFocused();
  const canvas = await map.locator(".maplibregl-canvas").boundingBox();
  expect(canvas?.x).toBeLessThanOrEqual(0);
  expect(canvas?.y).toBeLessThanOrEqual(0);
  expect(canvas?.width).toBeGreaterThanOrEqual(390);
  expect(canvas?.height).toBeGreaterThanOrEqual(844);
  for (const control of [close, map.getByRole("button", { name: "Vergrößern" }), map.getByRole("button", { name: "Dein Standort" })]) {
    const box = await control.boundingBox();
    expect(box?.width).toBeGreaterThanOrEqual(44);
    expect(box?.height).toBeGreaterThanOrEqual(44);
  }
  // The spot pin opens its own card with the maps-app hand-off.
  await map.getByRole("button", { name: "Spot Alcyons" }).click();
  const spotSheet = map.getByRole("complementary", { name: "Spot Alcyons" });
  const openLink = spotSheet.getByRole("link", { name: "In Google Maps öffnen" });
  await expect(openLink).toBeVisible();
  expect((await openLink.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  const sheetBox = await spotSheet.boundingBox();
  expect((sheetBox?.x ?? 0) + (sheetBox?.width ?? 0)).toBeLessThanOrEqual(390);
  // Card and map follow the site theme: dark mode subdues the ground and turns
  // the glyphs light; the card stays a step darker than the land.
  const mapRoot = map.locator(".swd-locator-map");
  await expect(spotSheet).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  await expect(spotSheet).toHaveCSS("background-color", "rgb(26, 31, 36)");
  await expect(mapRoot).toHaveCSS("background-color", "rgb(38, 42, 46)");
  await expect(map.getByRole("button", { name: "Vergrößern" })).toHaveCSS("color", "rgb(230, 226, 220)");
  // In dark mode the spot dot carries the dark ring, as on /map.
  await expect(map.locator(".swd-locator-spot .swd-locator-dot")).toHaveCSS("color", "rgb(14, 17, 20)");
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));

  await page.keyboard.press("Escape");
  await expect(spotSheet).toHaveCount(0);
  await close.click();
  await expect(map.getByRole("button", { name: "Karte im Vollbild öffnen" })).toBeFocused();
});

test("Spot-Karte meldet fehlende Kartenkacheln und lädt sie erneut", async ({ page }) => {
  let failing = true;
  await mockMapTiles(page, { failTiles: () => failing });
  await page.setViewportSize({ width: 1280, height: 900 });
  const map = await openLocator(page);

  await expect(map.getByRole("alert")).toContainText("Karte unvollständig");
  failing = false;
  await map.getByRole("button", { name: "Erneut laden" }).click();
  await expect(map.getByRole("alert")).toHaveCount(0);
  await expect(map.locator(".swd-locator-map")).toHaveAttribute("data-visible-ready-ms", /\d/);
});

test("Daten-Seite zeigt Meteogramm und Ausblick", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  // Meteogram row labels + the direction/time axes (rendered capitalised, shown
  // uppercase via CSS — assert the DOM text).
  await expect(page.getByText("Welle", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Richt", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" })).toBeVisible();
  await expect(page.locator("[data-meteogram-row-label]").first()).toHaveCSS("font-size", "10px");
  await expect(page.locator(".swd-meteogram-temperature").first()).toHaveCSS("font-size", "12px");
  await expect(page.locator(".swd-today-low").first()).toHaveCSS("font-weight", "400");
  await expect(page.locator(".swd-today-low").first()).toHaveCSS("opacity", "1");
  // The complete 10-day outlook renders through the last hourly day.
  await expect(page.locator("#spot-meteogram-scroll [data-forecast-day]")).toHaveCount(10);
});

test("Daten-Seite kennzeichnet den kostenlosen Meeresspiegel-Fallback eindeutig", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/daten");

  const tide = page.getByRole("region", { name: "Gezeitenvorhersage" });
  await tide.scrollIntoViewIfNeeded();
  await expect(tide.getByRole("heading", { name: "Modellierter Meeresspiegel" })).toBeVisible();
  // One week as a plain chart; how the value is made (model, not for
  // navigation, source) is explained on "Daten & Fragen", linked from here.
  const curve = tide.getByRole("slider", { name: /Verlauf der nächsten 7 Tage/ });
  await expect(curve).toBeVisible();
  // Scrubbing: the arrow keys (like a finger along the curve) pick an hour,
  // and its level is read out with the time.
  await curve.focus();
  await page.keyboard.press("ArrowRight");
  await expect(curve).toHaveAttribute("aria-valuenow", "1");
  await expect(curve).toHaveAttribute("aria-valuetext", /Uhr, /);
  await expect(tide.getByRole("link", { name: "Wie entsteht der Wert?" })).toHaveAttribute("href", "/fragen");
});

test("Die Daten-Seite hat keine eigene Karte mehr, sondern führt auf die Wetterkarte", async ({ page }) => {
  // One map for the whole site: the spot's own MapLibre/Leaflet overlay was
  // deleted (2026-10-10). "Karte" now opens the shared weather map, framed on
  // the spot and locked to the wind field — nothing to toggle to on a spot.
  await mockApi(page);
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();

  await expect(page.locator(".leaflet-container")).toHaveCount(0);
  await expect(page.locator(".swd-spot-field-map")).toHaveCount(0);
  await expect(page.getByRole("dialog", { name: "Windkarte und aktuelle Bedingungen" })).toHaveCount(0);

  const link = page.getByRole("link", { name: "Karte öffnen" });
  const href = await link.getAttribute("href");
  expect(href).toContain("mode=wind");
  expect(href).toContain("toggle=0");

  await link.click();
  await expect(page).toHaveURL(/\/map\?/);
  // The redesigned /map always carries its mode pill (Single Surface Map
  // Rule); "toggle=0" was the retired map's switch-off and is ignored. The old
  // "no mode switch" check only passed when it ran before the lazy map mounted.
  // What matters is that the spot's entry lands in wind mode.
  const modes = page.getByRole("group", { name: "Kartenmodus" });
  await expect(modes.getByRole("button", { name: "Wind" })).toHaveAttribute("aria-pressed", "true");
  // From a spot the map offers the weather only: Wind and Wellen, no Spots.
  await expect(modes.getByRole("button", { name: "Wellen" })).toBeVisible();
  await expect(modes.getByRole("button", { name: "Spots", exact: true })).toHaveCount(0);
});

test("Meteogramm zeigt Temperatur nur als Zahl ohne Balken", async ({ page }) => {
  await mockApi(page);
  await page.goto("/spot/test/daten");

  const temperatures = page.locator(".swd-meteogram-temperature");
  await expect.poll(() => temperatures.count()).toBeGreaterThan(0);
  await expect(temperatures.first()).toContainText(/\d+°/);
  await expect(temperatures.first()).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
});

test("Info-Locator bleibt statisch und nutzt genau einen schlanken Forecast-Abruf", async ({ page }) => {
  let liveRequests = 0;
  let forecastRequests = 0;
  let forecastSummaryRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/spots/test/live") liveRequests += 1;
    if (new URL(request.url()).pathname === "/spots/test/forecast") forecastRequests += 1;
    if (new URL(request.url()).pathname === "/spots/test/forecast-summary") forecastSummaryRequests += 1;
  });
  await mockApi(page);
  await page.goto("/spot/test/info");
  await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
  // The desktop locator is intentionally lazy-rendered. Scroll its stable
  // semantic slot into view first so the IntersectionObserver may mount the
  // map; waiting on the lazy child itself can never trigger that observer.
  // A synchronous DOM scroll also avoids Playwright waiting for the tab's
  // entrance animation while React legitimately rerenders the lazy slot.
  const locatorRegion = page.getByRole("region", { name: "Lage", exact: true });
  await expect(locatorRegion).toBeAttached();
  await locatorRegion.evaluate((element) => element.scrollIntoView({ block: "center" }));
  await expect(page.locator(".swd-locator-map")).toBeVisible();
  await expect(page.locator(".swd-locator-map [data-observation-type]")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Sicherheit", exact: true })).toBeVisible();
  await expect(page.getByText("Eine Reise wert")).toBeVisible();
  await expect(page.getByText(/Community · Lena K\./)).toBeVisible();
  // Air and water are cells in the safety card's foot, each a label over
  // its value — not one joined sentence.
  const safetyCard = page.getByRole("region", { name: "Sicherheit", exact: true });
  await expect(safetyCard.getByText("Luft", { exact: true })).toBeVisible();
  await expect(safetyCard.getByText("23 °C", { exact: true })).toBeVisible();
  await expect(safetyCard.getByText("Wasser", { exact: true })).toBeVisible();
  await expect(safetyCard.getByText("18 °C", { exact: true })).toBeVisible();
  expect(liveRequests).toBe(0);
  // Since 2026-11-25 the Info tab warms the Daten tab's forecast once the
  // page is idle ("Daten-Tab vorladen") — at most one request, never a poll.
  expect(forecastRequests).toBeLessThanOrEqual(1);
  expect(forecastSummaryRequests).toBe(1);
});

test("Region und Land stehen neben dem Spotnamen, nicht als Brotkrume darüber", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockApi(page);
  await page.goto("/spot/test/info");
  const title = page.getByRole("heading", { name: "Alcyons", level: 1 });
  await expect(title).toBeVisible();
  const region = page.getByRole("link", { name: "Kieler Bucht" });
  await expect(region).toBeVisible();
  await expect(page.getByText("Deutschland", { exact: true })).toBeVisible();

  // Beside the name, on its baseline — not on a line above it.
  const [titleBox, regionBox] = await Promise.all([title.boundingBox(), region.boundingBox()]);
  expect(titleBox).not.toBeNull();
  expect(regionBox).not.toBeNull();
  expect(regionBox!.x).toBeGreaterThan(titleBox!.x + titleBox!.width - 1);
  const titleBottom = titleBox!.y + titleBox!.height;
  const regionBottom = regionBox!.y + regionBox!.height;
  expect(Math.abs(regionBottom - titleBottom)).toBeLessThanOrEqual(6);
});

test("Info-Hinweise bleiben auf kleinen Displays ohne Seitenüberlauf lesbar", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await mockApi(page);
  await page.goto("/spot/test/info");
  await expect(page.getByRole("region", { name: "Sicherheit", exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("Beschreibung und Hinweise bleiben links, während die Galerie beim Ausklappen stabil bleibt", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockApi(page);
  // From `lg` the collapsed description takes whatever height the column has
  // left, so a text that fits is simply not clipped and offers no toggle. This
  // test is about the toggle, so it needs a description long enough to overrun
  // a column as tall as the gallery.
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/spots\/(test|laboe|Alcyons)$/, (route) =>
    route.fulfill({
      json: {
        ...spot,
        editorial: {
          ...spot.editorial,
          description: `${spot.editorial.description} ${spot.editorial.description} ${spot.editorial.description} ${spot.editorial.description}`,
        },
      },
    }));
  await page.goto("/spot/test/info");

  // The tile only: the gallery container also carries the action row below it.
  const gallery = page.locator(".spot-gallery-compact > div:first-child");
  const details = page.getByRole("region", { name: "Spotbeschreibung und Hinweise" });
  const profile = page.getByRole("complementary", { name: "Spotprofil und Ausstattung" });
  const more = details.getByRole("button", { name: "Mehr anzeigen" });
  await expect(gallery).toBeVisible();
  await expect(details).toBeVisible();
  await expect(profile).toBeVisible();
  await expect(more).toBeVisible();
  // No visible heading: a red glyph and the sentence are the whole block.
  await expect(details.getByRole("heading", { name: "Sicherheit", exact: true })).toHaveCount(0);
  const hintsCard = details.getByRole("region", { name: "Sicherheit", exact: true });
  // Flat on the page, no panel of its own (DESIGN.md, The No Tile Background
  // Rule). This used to assert the opposite — a tinted band.
  await expect(hintsCard).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(profile.getByRole("region", { name: "Sicherheit", exact: true })).toHaveCount(0);
  await expect(profile.getByRole("heading", { name: "Spotprofil" })).toHaveCount(0);
  await expect(profile.getByText(/Ein vielseitiger Küstenspot/)).toHaveCount(0);
  // On desktop the actions hang under the gallery, not in either column.
  await expect(profile.getByRole("button", { name: "Zu Favoriten hinzufügen" })).toHaveCount(0);
  await expect(details.getByRole("button", { name: "Zu Favoriten hinzufügen" })).toHaveCount(0);
  await expect(profile).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");

  const [collapsedGallery, collapsedProfile] = await Promise.all([gallery.boundingBox(), profile.boundingBox()]);
  expect(collapsedGallery).not.toBeNull();
  expect(collapsedProfile).not.toBeNull();
  expect(collapsedGallery!.width / collapsedGallery!.height).toBeCloseTo(2 / 3, 2);
  expect(Math.abs(collapsedProfile!.height - collapsedGallery!.height)).toBeLessThanOrEqual(1);
  const facilityTable = profile.getByRole("table", { name: "Ausstattung am Spot" });
  await expect(facilityTable.getByRole("row")).toHaveCount(7);
  // Present and absent are glyphs; "nobody has checked" is a word. The mock
  // leaves toilet and changing room unset, so exactly two rows say so.
  await expect(facilityTable.getByText("Unbekannt", { exact: true })).toHaveCount(2);
  await expect(facilityTable.getByText("Camping")).toHaveCount(0);
  await expect(facilityTable.getByText("Direkt am Deich")).toHaveCount(0);
  const profileContent = await profile.locator(":scope > *").evaluateAll((elements) => {
    const first = elements[0].getBoundingClientRect();
    const last = elements[elements.length - 1].getBoundingClientRect();
    return { top: first.top, bottom: last.bottom };
  });
  const freeAbove = profileContent.top - collapsedProfile!.y;
  const freeBelow = collapsedProfile!.y + collapsedProfile!.height - profileContent.bottom;
  expect(Math.abs(freeAbove - freeBelow)).toBeLessThanOrEqual(6);
  // The action row: one copy, under the gallery, centred on it.
  const actions = page.locator(".spot-detail-content-grid").getByRole("button", { name: "Zu Favoriten hinzufügen" });
  await expect(actions).toHaveCount(1);
  const actionsBox = await actions.boundingBox();
  expect(actionsBox).not.toBeNull();
  expect(actionsBox!.y).toBeGreaterThanOrEqual(collapsedGallery!.y + collapsedGallery!.height);
  const actionsRow = await page.locator(".spot-gallery-compact > div:last-child").boundingBox();
  const galleryCentre = collapsedGallery!.x + collapsedGallery!.width / 2;
  expect(Math.abs(actionsRow!.x + actionsRow!.width / 2 - galleryCentre)).toBeLessThanOrEqual(1);
  await more.click();
  const less = details.getByRole("button", { name: "Weniger anzeigen" });
  await expect(less).toBeVisible();
  const expandedGallery = await gallery.boundingBox();
  expect(expandedGallery).not.toBeNull();
  expect(Math.abs(expandedGallery!.height - collapsedGallery!.height)).toBeLessThanOrEqual(1);
  // Expanded, the text needs the column's height, so the safety card gives it
  // up — and is hidden from assistive technology while it is invisible.
  await expect(details.getByRole("region", { name: "Sicherheit", exact: true })).toHaveCount(0);

  await less.click();
  await expect(more).toBeVisible();
  const description = details.getByText(/Ein vielseitiger Küstenspot/);
  const hints = details.getByRole("region", { name: "Sicherheit", exact: true });
  const [descriptionBox, hintsBox] = await Promise.all([description.boundingBox(), hints.boundingBox()]);
  expect(descriptionBox).not.toBeNull();
  expect(hintsBox).not.toBeNull();
  expect(hintsBox!.y).toBeGreaterThanOrEqual(descriptionBox!.y + descriptionBox!.height);
});

test("Aktionen stehen auf dem Handy oben bei den Spotdaten, nicht unten bei der Galerie", async ({ page }) => {
  // On a phone the gallery is the fourth block, below the locator map. The
  // action row must not travel down there with it, and it must exist exactly
  // once — the desktop position is a move, not a CSS-hidden second copy.
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/info");
  const grid = page.locator(".spot-detail-content-grid");
  const profile = page.getByRole("complementary", { name: "Spotprofil und Ausstattung" });
  const favorite = grid.getByRole("button", { name: "Zu Favoriten hinzufügen" });
  await expect(favorite).toHaveCount(1);
  await expect(profile.getByRole("button", { name: "Zu Favoriten hinzufügen" })).toBeVisible();

  const [actions, galleryColumn, locator] = await Promise.all([
    favorite.boundingBox(),
    page.locator(".spot-gallery-compact").boundingBox(),
    page.getByRole("region", { name: "Lage", exact: true }).boundingBox(),
  ]);
  expect(actions).not.toBeNull();
  expect(actions!.y).toBeLessThan(locator!.y);
  expect(actions!.y).toBeLessThan(galleryColumn!.y);
});

test("Die Gültigkeit der Vorhersage liegt eingeklappt hinter einem Marker", async ({ page }) => {
  // The timestamp belongs on the page — a reading without one is a claim
  // without a date — but it waits until it is asked for.
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page);
  await page.goto("/spot/test/info");
  const hints = page.getByRole("region", { name: "Sicherheit", exact: true });
  await expect(hints).toBeVisible();
  await expect(hints.getByText(/^Vorhersage · /)).toHaveCount(0);

  const marker = hints.getByRole("button", { name: "Gültigkeit der Vorhersage anzeigen" });
  await expect(marker).toHaveAttribute("aria-expanded", "false");
  await marker.click();
  await expect(hints.getByText(/^Vorhersage · /)).toBeVisible();
  await expect(
    hints.getByRole("button", { name: "Gültigkeit der Vorhersage ausblenden" }),
  ).toHaveAttribute("aria-expanded", "true");
});

test("Level, Gewässer, Untergrund und Windrichtung stehen auf dem Handy als zwei mal zwei Kacheln", async ({ page }) => {
  await mockApi(page);
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/spots\/(test|laboe|Alcyons)$/, (route) =>
    route.fulfill({ json: { ...spot, best_wind_directions: ["nw", "w"] } }));

  // The tiles themselves, not their labels: a label can wrap to a second line
  // without that saying anything about where its tile sits.
  const boxes = async () => {
    const profile = page.getByRole("complementary", { name: "Spotprofil und Ausstattung" });
    return Promise.all(
      ["Level", "Gewässer", "Untergrund", "Beste Windrichtung"].map((label) =>
        profile
          .locator("dl")
          .filter({ has: page.getByRole("term").filter({ hasText: new RegExp(`^${label}$`, "i") }) })
          .boundingBox(),
      ),
    );
  };

  // Two per row, two rows — at every phone width. Four across fit the width
  // but not the words: every long German value broke into syllables.
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/spot/test/info");
    await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
    const tiles = await boxes();
    expect(tiles.every((box) => box !== null)).toBe(true);
    expect(Math.abs(tiles[1]!.y - tiles[0]!.y)).toBeLessThanOrEqual(1);
    expect(tiles[1]!.x).toBeGreaterThan(tiles[0]!.x);
    expect(tiles[2]!.y).toBeGreaterThan(tiles[0]!.y);
    expect(Math.abs(tiles[3]!.y - tiles[2]!.y)).toBeLessThanOrEqual(1);
    expect(tiles[3]!.x).toBeGreaterThan(tiles[2]!.x);
  }
});

for (const width of [320, 375, 768, 1280, 1440]) {
  test(`Daten-Seite bleibt bei ${width}px innerhalb der Seite`, async ({ page }) => {
    await page.setViewportSize({ width, height: width < 500 ? 720 : 900 });
    await mockApi(page);
    await page.goto("/spot/test/daten");
    await expect(page.getByRole("heading", { name: "Alcyons" })).toBeVisible();
    const navigator = page.getByRole("group", { name: "Tagesübersicht — Tag im Stundenforecast anzeigen" });
    await expect(navigator.getByRole("button")).toHaveCount(10);
    const navigatorMetrics = await navigator.evaluate((element) => ({
      overflow: element.scrollWidth - element.clientWidth,
      clientWidth: element.clientWidth,
    }));
    if (width >= 1024) {
      // Desktop (lg): all ten days fit as a grid — no internal scroll.
      expect(navigatorMetrics.overflow).toBeLessThanOrEqual(1);
    } else {
      // Mobile/tablet: the day strip is a horizontal snap scroller, so internal
      // overflow is expected; what matters is its visible box fits the viewport
      // and it doesn't widen the page (asserted below via the document overflow).
      expect(navigatorMetrics.clientWidth).toBeLessThanOrEqual(width);
    }
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
  await navigator.getByRole("button", { name: /Mo 14\.09/i }).click();

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
  // The Windmonate module keeps its wind window in the query string, so pin the
  // path and allow whatever selection it has synced.
  await expect(page).toHaveURL(/\/spot\/laboe\/daten(\?|$)/);
  await expect(page.getByRole("group", { name: "Meteogramm — Zeitpunkt wählen" })).toBeVisible();
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => window.scrollY)).toBe(infoScrollY);

  const datenScrollY = await page.evaluate(() => window.scrollY);
  await page.getByRole("tab", { name: "Info" }).click();
  await expect(page).toHaveURL(/\/spot\/laboe\/info(\?|$)/);
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

test("Beim Runterscrollen bleibt oben links ein Zurück-Pfeil, auf Info und Daten", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const tab of ["info", "daten"] as const) {
    await page.goto(`/spot/test/${tab}`);
    // One arrow (2026-11-25): it stands where the header puts it and simply
    // stays there while the page scrolls — no second arrow sliding in.
    const back = page.locator("[data-page-back]");
    await expect(back).toHaveCount(1);
    await expect(back).toBeVisible();
    await expect(back).toHaveClass(/back-glyph-on-photo/);
    const top = (await back.boundingBox())!;
    await page.mouse.wheel(0, 1200);
    await expect(back).toHaveClass(/back-glyph-disc/);
    const scrolled = (await back.boundingBox())!;
    expect(Math.round(scrolled.x)).toBe(Math.round(top.x));
    expect(Math.round(scrolled.y)).toBe(Math.round(top.y));
    expect(scrolled.width).toBeGreaterThanOrEqual(44);
  }
  await page.locator("[data-page-back]").click();
  await expect(page).toHaveURL(/\/$/);
});

test("Änderung vorschlagen: beschriftete Felder, Senden bleibt bei kleiner Höhe erreichbar", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  let sent: Record<string, unknown> | null = null;
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/submissions$/, async (route) => {
    sent = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { id: "s1", status: "pending" } });
  });
  await page.goto("/spot/test/info");
  await page.getByRole("button", { name: "Änderung vorschlagen" }).click();
  const dialog = page.getByRole("dialog", { name: "Änderung vorschlagen" });
  await expect(dialog).toBeVisible();
  // Every field carries a real label, not just a placeholder.
  await expect(dialog.getByLabel("Welcher Bereich?")).toBeVisible();
  await expect(dialog.getByLabel("Name (optional)")).toBeVisible();
  await expect(dialog.getByLabel("E-Mail (optional)")).toBeVisible();
  const area = dialog.getByLabel("Welcher Bereich?");
  await expect(area.locator("option")).toHaveText([
    "Name des Spots", "Region / Land", "Sportarten", "Beschreibung", "Sicherheit und Gefahren",
    "Spotprofil (Level, Gewässer, Untergrund, Windrichtung)", "Ausstattung", "Lage auf der Karte", "Fotos", "Sonstiges",
  ]);
  // Phone: a sheet on the bottom edge.
  const card = await dialog.boundingBox();
  expect(Math.round(card!.y + card!.height)).toBeGreaterThan(844 - 40);

  // A keyboard-sized viewport: the card shrinks, the fields scroll, and the
  // submit button stays on screen.
  await page.setViewportSize({ width: 390, height: 380 });
  await dialog.getByLabel(/Deine Änderung/).fill("Der Parkplatz ist seit 2026 kostenpflichtig.");
  const submit = dialog.getByRole("button", { name: "Vorschlag senden" });
  await expect(submit).toBeInViewport();
  const sendBox = await submit.boundingBox();
  expect(sendBox!.y + sendBox!.height).toBeLessThanOrEqual(380);
  expect(sendBox!.height).toBeGreaterThanOrEqual(44);
  const closeBox = await dialog.getByRole("button", { name: "Schließen" }).boundingBox();
  expect(closeBox!.height).toBeGreaterThanOrEqual(44);

  await area.selectOption("hazards");
  await submit.click();
  await expect(dialog.getByRole("status")).toContainText("Danke");
  expect(sent).toMatchObject({ payload: { kind: "spot_edit_suggestion", field: "hazards", message: "Der Parkplatz ist seit 2026 kostenpflichtig." } });
});

test("Antworten sind nur eingerückt, ohne Thread-Linie, und die Aktionszeile bleibt einzeilig", async ({ page }) => {
  const iso = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();
  await mockApi(page);
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\/spots\/test\/tips$/, (route) => route.fulfill({ json: { items: [
    { id: "a1", body: "Bei Levante ab 20 kn wird es am Strand sehr voll.", title: null, author_name: "Lena M", created_at: iso(300), parent_id: null, upvotes: 4 },
    { id: "r1", body: "Stimmt, morgens ist es deutlich entspannter.", title: null, author_name: "Jonas K", created_at: iso(200), parent_id: "a1", upvotes: 12 },
  ] } }));
  // 320 only on the touch profile: a desktop window that narrow (400% zoom)
  // also loses 15px to the scrollbar, and there a reply's row may wrap.
  const widths = test.info().project.name.includes("mobile") ? [320, 390, 1024, 1280] : [360, 390, 1024, 1280];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/spot/test/info");
    await page.getByRole("button", { name: "1 Antwort ansehen" }).click();
    const parent = page.getByText("Lena M", { exact: true });
    const reply = page.getByText("Jonas K", { exact: true });
    await expect(reply).toBeVisible();
    const thread = page.locator("article").filter({ hasText: "Lena M" });
    // No rail and no elbow: nothing in the thread draws a vertical line.
    expect(await thread.locator(".w-px, .border-l").count()).toBe(0);
    // The reply starts further in than its parent's name.
    const [p, r] = [await parent.boundingBox(), await reply.boundingBox()];
    expect(r!.x).toBeGreaterThan(p!.x + 20);
    // Each action row (time · Antworten · …) fits on one line; the vote has
    // its own column at the right edge.
    for (const row of await thread.locator("time").evaluateAll((times) => times.map((t) => t.parentElement!.getBoundingClientRect().height))) {
      expect(row, `meta row at ${width}px`).toBeLessThanOrEqual(56);
    }
  }
});

test("Der Daten-Tab lässt sich für die Welle auslegen", async ({ page }) => {
  await mockApi(page);
  await page.goto("/spot/test/daten");
  const focus = page.getByRole("group", { name: "Daten ausgelegt für" });
  await expect(focus.getByRole("button", { name: "Wind" })).toHaveAttribute("aria-pressed", "true");
  await focus.getByRole("button", { name: "Welle" }).click();
  await expect(focus.getByRole("button", { name: "Welle" })).toHaveAttribute("aria-pressed", "true");
  // The link carries the focus, and the meteogram leads with the sea.
  await expect.poll(() => new URL(page.url()).searchParams.get("fokus")).toBe("welle");
  const labels = page.locator("[data-meteogram-row-label]");
  await expect(labels.first()).toHaveText("Welle");
  await expect(labels.nth(1)).toHaveText("Periode");
  await expect(page.getByRole("slider", { name: /Welle des Tages/ })).toBeVisible();
  // Remembered for the next visit without the link.
  await page.goto("/spot/test/daten");
  await expect(page.getByRole("group", { name: "Daten ausgelegt für" }).getByRole("button", { name: "Welle" }))
    .toHaveAttribute("aria-pressed", "true");
});

test("Ein Schalter, der in den Link schreibt, lässt die Seite an ihrer Stelle", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 700 });
  await mockApi(page);
  await page.goto("/spot/test/daten");
  const focus = page.getByRole("group", { name: "Daten ausgelegt für" });
  await expect(focus).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 300));
  await expect.poll(() => page.evaluate(() => Math.round(window.scrollY))).toBe(300);
  await focus.getByRole("button", { name: "Welle" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("fokus")).toBe("welle");
  // Only the query changed: no jump to the top.
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => Math.round(window.scrollY))).toBe(300);
});
