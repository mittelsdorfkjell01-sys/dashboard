import { expect, test } from "@playwright/test";
import { gzipSync } from "node:zlib";

const TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

const spots = [
  { id: "00000000-0000-4000-8000-000000000001", slug: "spot-a", name: "Spot A", region_id: null, region_name: "Region A", region_country: "DE", location: { lat: 54, lon: 10 }, sports: ["kitesurf"], image: null, facing: null, water_type: [], bottom_type: [], level: [], water_character: [], style: [], facilities: null, best_months: null, typical_wind_kt: 18, typical_wave_height_m: null },
  { id: "00000000-0000-4000-8000-000000000002", slug: "spot-b", name: "Spot B", region_id: null, region_name: "Region B", region_country: "FR", location: { lat: 43, lon: 6 }, sports: ["surf"], image: null, facing: null, water_type: [], bottom_type: [], level: [], water_character: [], style: [], facilities: null, best_months: null, typical_wind_kt: 12, typical_wave_height_m: null },
];

export async function mockBackend(
  page: import("@playwright/test").Page,
  onTileRequest?: (url: URL) => void,
  withWindField = false,
  windOptions: { freshness?: "fresh" | "delayed" | "stale" | "expired"; endpointStatus?: number; invalidManifest?: boolean; emptyForecast?: boolean; withWaves?: boolean; validTimes?: string[]; longRangeTo?: string; onFieldRequest?: (url: URL) => void } = {},
) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/spots") return route.fulfill({ json: spots });
    if (url.pathname === "/spots/landing") return route.fulfill({ json: { spots, total: spots.length, version: "test-1" } });
    if (url.pathname === "/spots/version") return route.fulfill({ json: { version: "test-1" } });
    if (url.pathname === "/spots/live") return route.fulfill({ json: [] });
    if (withWindField && url.pathname === "/weather-fields/wind") {
      if (windOptions.endpointStatus) return route.fulfill({ status: windOptions.endpointStatus, json: { detail: "field unavailable" } });
      windOptions.onFieldRequest?.(url);
      const response = windFieldResponse(windOptions.freshness, windOptions.validTimes, windOptions.longRangeTo);
      if (windOptions.invalidManifest) response.manifest.valid_times = [];
      return route.fulfill({ json: response });
    }
    if (withWindField && url.pathname === "/weather-fields/wind/sample") return route.fulfill({ json: {
      product: "model_wind", publication_id: "publication-test", generation: 1, run_id: "run-test", provider: "dwd", model: "icon-eu",
      model_run: "2026-10-03T12:00:00Z", valid_at: "2026-10-03T12:00:00Z", latitude: 50, longitude: 8,
      u_ms: 5, v_ms: 2, speed_ms: 5.385, direction_from_deg: 248, gust_ms: 8, interpolation: "bilinear_uv", freshness: "fresh",
    } });
    if (withWindField && url.pathname === "/weather-fields/wind/sample/series") {
      if (windOptions.validTimes) return route.fulfill({ json: {
        samples: windOptions.validTimes.map((validAt, index) => ({
          product: "model_wind", publication_id: "publication-test", generation: 1, run_id: "run-test", provider: "dwd", model: "icon-eu",
          model_run: windOptions.validTimes![0], valid_at: validAt, latitude: 50, longitude: 8,
          u_ms: 5, v_ms: 2, speed_ms: 5 + (index % 5), direction_from_deg: 248, gust_ms: 8 + (index % 5), temperature_c: 14,
          interpolation: "bilinear_uv", freshness: "fresh",
        })),
      } });
      return route.fulfill({ json: {
      samples: [
        { product: "model_wind", publication_id: "publication-test", generation: 1, run_id: "run-test", provider: "dwd", model: "icon-eu", model_run: "2026-10-03T12:00:00Z", valid_at: "2026-10-03T12:00:00Z", latitude: 50, longitude: 8, u_ms: 5, v_ms: 2, speed_ms: 5.385, direction_from_deg: 248, gust_ms: 8, temperature_c: 14, interpolation: "bilinear_uv", freshness: "fresh" },
        { product: "model_wind", publication_id: "publication-test", generation: 1, run_id: "run-test", provider: "dwd", model: "icon-eu", model_run: "2026-10-03T12:00:00Z", valid_at: "2026-10-03T13:00:00Z", latitude: 50, longitude: 8, u_ms: 6, v_ms: 2, speed_ms: 6.3, direction_from_deg: 250, gust_ms: 9, temperature_c: 15, interpolation: "bilinear_uv", freshness: "fresh" },
      ],
    } });
    }
    if (withWindField && windOptions.withWaves && url.pathname === "/weather-fields/waves") {
      return route.fulfill({ json: waveFieldResponse(windOptions.freshness) });
    }
    if (withWindField && windOptions.withWaves && url.pathname === "/weather-fields/waves/sample/series") {
      return route.fulfill({ json: { samples: waveSampleSeries() } });
    }
    if (withWindField && url.pathname === "/weather-fields/wind/compare") return route.fulfill({ json: {
      product: "model_wind_comparison", valid_at: "2026-10-03T12:00:00Z", latitude: 50, longitude: 8,
      samples: [], spread: { model_count: 1, speed_min_ms: 5.385, speed_max_ms: 5.385, speed_spread_ms: 0, gust_min_ms: 8, gust_max_ms: 8, gust_spread_ms: 0 },
    } });
    if (withWindField && url.pathname.startsWith("/weather-field-assets/")) {
      const match = url.pathname.match(/\/(\d+)\/(\d+)\/(\d+)\.swf2\.gz$/);
      if (!match) return route.fulfill({ status: 404 });
      const tile = url.pathname.includes("/europe-waves/")
        ? waveTile(Number(match[1]), Number(match[2]), Number(match[3]))
        : windTile(Number(match[1]), Number(match[2]), Number(match[3]));
      return route.fulfill({ body: tile, contentType: "application/gzip" });
    }
    if (/^\/spots\/[^/]+\/live$/.test(url.pathname)) return route.fulfill({ json: spotLiveResponse() });
    if (/^\/spots\/[^/]+\/forecast$/.test(url.pathname)) {
      return route.fulfill({ json: windOptions.emptyForecast ? { ...spotForecastResponse(), days: [] } : spotForecastResponse() });
    }
    if (url.pathname === "/auth/me" || url.pathname === "/account/me") return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
    return route.fulfill({ json: [] });
  });
  await page.route(/https:\/\/[a-d]\.basemaps\.cartocdn\.com\/.*\.png(?:\?.*)?$/, (route) => {
    onTileRequest?.(new URL(route.request().url()));
    return route.fulfill({ body: TRANSPARENT_PNG, contentType: "image/png" });
  });
}

function spotLiveResponse() {
  return {
    spot_id: spots[0].id, model: "icon-eu", time: "2026-10-03T12:00:00Z",
    current: {
      wind: 12, gust: 27, dir: 287, air: 21, sst: 17,
      swell: 0.5, period: 7, swell_dir: 280,
      waves: { total_wave: { significant_height_m: 1.3 }, primary_swell: { significant_height_m: 0.5 } },
    },
  };
}

function spotForecastResponse() {
  const day = (date: string, startHour: number) => ({
    date, local_date: date, confidence: "hoch", detail: "hourly",
    summary: { wind_avg: 12, wind_max: 18, gust_max: 27, air_min: 15, air_max: 23, swell_max: 1.4, sunshine_duration_hours: 12, uv_index_max: 5 },
    hours: Array.from({ length: 24 }, (_, h) => ({
      time: `${date}T${String(h).padStart(2, "0")}:00:00Z`,
      wind: 8 + ((h + startHour) % 12), gust: 14 + ((h + startHour) % 12),
      dir: 280 + (h % 20), air: 18 + (h % 6),
      swell: 0.3 + (h % 4) / 10, period: 7, swell_dir: 280,
      waves: { total_wave: { significant_height_m: 0.3 + (h % 4) / 10 } },
      precip: 0.1, sst: 17, apparent_temperature_c: 20 + (h % 5),
      cloud_cover_pct: 30, uv_index: h % 7,
    })),
  });
  return {
    spot_id: spots[0].id, model: "icon-eu", generated_at: "2026-10-03T11:00:00Z",
    timezone: "UTC",
    days: [day("2026-10-03", 0), day("2026-10-04", 3), day("2026-10-05", 6)],
  };
}

function windFieldResponse(
  freshness: "fresh" | "delayed" | "stale" | "expired" = "fresh",
  validTimes?: string[],
  longRangeTo?: string,
) {
  return {
    enabled: true, public: true, status: freshness, publication_id: "publication-test", generation: 1,
    manifest_url: "/weather-field-assets/europe-wind/icon-eu/manifest.json",
    manifest: {
      contract_version: "weather-field-v2", publication_id: "publication-test", provider: "dwd", model: "icon-eu",
      model_run: "2026-10-03T12:00:00Z", published_at: "2026-10-03T13:00:00Z",
      valid_times: validTimes ?? ["2026-10-03T12:00:00Z", "2026-10-03T13:00:00Z"],
      coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
      variables: [
        { name: "wind_u", unit: "m/s", semantic: "eastward", height_m: 10 },
        { name: "wind_v", unit: "m/s", semantic: "northward", height_m: 10 },
        { name: "wind_gust", unit: "m/s", semantic: "magnitude", height_m: 10 },
      ],
      compression: "gzip", quality_status: "validated",
      freshness: { status: freshness, age_seconds: 3600, expected_next_run_at: "2026-10-03T18:00:00Z" },
      attribution: [{ provider: "Deutscher Wetterdienst", text: "DWD Open Data", url: "https://opendata.dwd.de/", licence: "GeoNutzV" }],
      field_template: "/weather-field-assets/europe-wind/icon-eu/assets/{valid_time}/{z}/{x}/{y}.swf2.gz",
      tile_scheme: { tile_size: 128, overlap: 1, lod: [
        { source_zoom: 4, consumer_zoom_min: 0, consumer_zoom_max: 5, source_decimation: 1 },
        { source_zoom: 5, consumer_zoom_min: 6, consumer_zoom_max: 8, source_decimation: 1 },
      ] },
    },
    // What the models could answer, beside what the active run holds. The
    // short-range model is the active one; the long-range one is what the
    // clock's later days have to reach for.
    available_models: [
      {
        key: "icon-d2", name: "ICON-D2", provider: "dwd", primary: false, priority: 5, freshness: "fresh",
        covers_point: true, covers_viewport: true, model_run: "2026-10-03T12:00:00Z",
        coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
        valid_from: (validTimes ?? ["2026-10-03T12:00:00Z"])[0],
        valid_to: (validTimes ?? ["2026-10-03T13:00:00Z"]).slice(-1)[0],
      },
      ...(longRangeTo
        ? [{
            key: "icon-eu", name: "ICON-EU", provider: "dwd", primary: true, priority: 10, freshness: "fresh",
            covers_point: true, covers_viewport: true, model_run: "2026-10-03T12:00:00Z",
            coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
            valid_from: (validTimes ?? ["2026-10-03T12:00:00Z"])[0],
            valid_to: longRangeTo,
          }]
        : []),
    ],
  };
}

function waveFieldResponse(freshness: "fresh" | "delayed" | "stale" | "expired" = "fresh", validTimes?: string[]) {
  return {
    enabled: true, public: true, status: freshness, publication_id: "wave-publication-test", generation: 1,
    manifest_url: "/weather-field-assets/europe-waves/dwd-ewam/manifest.json",
    manifest: {
      contract_version: "weather-field-v2", publication_id: "wave-publication-test", provider: "dwd", model: "dwd-ewam",
      model_run: "2026-10-03T12:00:00Z", published_at: "2026-10-03T13:00:00Z",
      valid_times: validTimes ?? ["2026-10-03T12:00:00Z", "2026-10-03T13:00:00Z"],
      coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
      variables: [
        { name: "wave_u", unit: "m", semantic: "wave_eastward", height_m: null },
        { name: "wave_v", unit: "m", semantic: "wave_northward", height_m: null },
        { name: "total_wave_height", unit: "m", semantic: "wave_height", height_m: null },
        { name: "total_wave_direction", unit: "°", semantic: "direction_from", height_m: null },
        { name: "total_wave_period", unit: "s", semantic: "wave_period", height_m: null },
      ],
      compression: "gzip", quality_status: "validated",
      freshness: { status: freshness, age_seconds: 3600, expected_next_run_at: "2026-10-03T18:00:00Z" },
      attribution: [{ provider: "Deutscher Wetterdienst", text: "DWD Open Data", url: "https://opendata.dwd.de/", licence: "GeoNutzV" }],
      field_template: "/weather-field-assets/europe-waves/dwd-ewam/assets/{valid_time}/{z}/{x}/{y}.swf2.gz",
      tile_scheme: { tile_size: 128, overlap: 1, lod: [
        { source_zoom: 4, consumer_zoom_min: 0, consumer_zoom_max: 5, source_decimation: 1 },
        { source_zoom: 5, consumer_zoom_min: 6, consumer_zoom_max: 8, source_decimation: 1 },
      ] },
    },
  };
}

function waveSampleSeries() {
  return ["2026-10-03T12:00:00Z", "2026-10-03T13:00:00Z"].map((validAt, index) => ({
    product: "model_wave", publication_id: "wave-publication-test", generation: 1, run_id: "wave-run-test",
    provider: "dwd", model: "dwd-ewam", model_run: "2026-10-03T12:00:00Z", valid_at: validAt,
    latitude: 54, longitude: 5, wave_u: 1, wave_v: 0.4,
    total_wave_height_m: 1.8 + index / 10, total_wave_direction_from_deg: 248, total_wave_period_s: 8 + index,
    wind_sea_height_m: 0.7, wind_sea_direction_from_deg: 250, wind_sea_period_s: 5,
    primary_swell_height_m: 1.5, primary_swell_direction_from_deg: 245, primary_swell_period_s: 9,
    interpolation: "bilinear_wave", freshness: "fresh",
  }));
}

function windTile(z: number, x: number, y: number): Buffer {
  const width = 130;
  const variables = [
    { name: "wind_u", dtype: "int16", scale: .05, offset: 0, nodata: -32768 },
    { name: "wind_v", dtype: "int16", scale: .05, offset: 0, nodata: -32768 },
    { name: "wind_gust", dtype: "int16", scale: .05, offset: 0, nodata: -32768 },
  ];
  const header = Buffer.from(JSON.stringify({ schema: "swd-field-tile-v2", width, height: width, layout: "planar", byte_order: "little", variables, valid_time: "2026-10-03T12:00:00Z", z, x, y, overlap: 1 }));
  const prefix = Buffer.alloc(8); prefix.write("SWF2", 0); prefix.writeUInt32LE(header.length, 4);
  const cells = width * width;
  const body = Buffer.alloc(cells * 2 * variables.length);
  [100, 40, 160].forEach((value, variable) => { for (let index = 0; index < cells; index += 1) body.writeInt16LE(value, (variable * cells + index) * 2); });
  return gzipSync(Buffer.concat([prefix, header, body]));
}

function waveTile(z: number, x: number, y: number): Buffer {
  const width = 130;
  const variables = [
    { name: "wave_u", dtype: "int16", scale: .01, offset: 0, nodata: -32768 },
    { name: "wave_v", dtype: "int16", scale: .01, offset: 0, nodata: -32768 },
    { name: "total_wave_height", dtype: "int16", scale: .01, offset: 0, nodata: -32768 },
    { name: "total_wave_direction", dtype: "int16", scale: .1, offset: 0, nodata: -32768 },
    { name: "total_wave_period", dtype: "int16", scale: .1, offset: 0, nodata: -32768 },
  ];
  const header = Buffer.from(JSON.stringify({ schema: "swd-field-tile-v2", width, height: width, layout: "planar", byte_order: "little", variables, valid_time: "2026-10-03T12:00:00Z", z, x, y, overlap: 1 }));
  const prefix = Buffer.alloc(8); prefix.write("SWF2", 0); prefix.writeUInt32LE(header.length, 4);
  const cells = width * width;
  const body = Buffer.alloc(cells * 2 * variables.length);
  [100, 40, 180, 2480, 850].forEach((value, variable) => { for (let index = 0; index < cells; index += 1) body.writeInt16LE(value, (variable * cells + index) * 2); });
  return gzipSync(Buffer.concat([prefix, header, body]));
}

test("map loads Leaflet layout and renders spots as accessible markers", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    // A logged-out visitor's session probe (/account/me) answers 401, which
    // Chromium logs as a failed-resource console error. That is expected here;
    // keep it out of the assertion while still catching every real error.
    if (/\/(account|auth)\/me\b/.test(msg.location()?.url ?? "")) return;
    consoleErrors.push(msg.text());
  });
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

  // The sources sit behind a small bare `i` that unfolds to its LEFT.
  const attribution = page.locator("main.swd-public-map").getByRole("button", { name: "Kartenquellen anzeigen" });
  await expect(attribution).toHaveAttribute("aria-expanded", "false");
  await expect(attribution).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  expect((await attribution.boundingBox())!.width).toBeLessThanOrEqual(28);
  await attribution.click();
  const sources = page.locator("main.swd-public-map").getByRole("complementary", { name: "Kartenquellen" });
  await expect(sources).toContainText("CARTO");
  // The label flips on open, so hold on to the glyph by its class — scoped to
  // the spot map, since the wind explorer stays mounted beside it and brings
  // its own sources glyph.
  const [glyphBox, panelBox] = [
    await page.locator("main.swd-public-map .swd-map-sources-glyph").boundingBox(),
    await sources.boundingBox(),
  ];
  expect(panelBox!.x + panelBox!.width).toBeLessThanOrEqual(glyphBox!.x + 1);
  expect(Math.abs((panelBox!.y + panelBox!.height / 2) - (glyphBox!.y + glyphBox!.height / 2))).toBeLessThan(14);
  expect(consoleErrors).toEqual([]);
});

test("back and zoom controls stay above the tiles and use bare map glyphs", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  const back = page.getByRole("button", { name: "Zurück" });
  const zoomIn = page.getByRole("button", { name: "Vergrößern" });
  const zoomOut = page.getByRole("button", { name: "Verkleinern" });
  for (const control of [back, zoomIn, zoomOut]) {
    await expect(control).toBeVisible();
    await expect(control).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(control).toHaveCSS("border-top-width", "0px");
    expect(await control.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)?.closest("button") === element;
    })).toBe(true);
  }

  const before = Number(new URL(page.url()).searchParams.get("z"));
  await zoomIn.click();
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("z"))).toBeGreaterThan(before);
  await zoomOut.click();
  await expect(zoomIn).toBeVisible();
  await expect(zoomOut).toBeVisible();
});

test("the initial overview requests only its final fitted tile zoom", async ({ page }) => {
  const tileZooms: number[] = [];
  await mockBackend(page, (url) => {
    // `@2x` since 2026-10-12: the grounds ask for CARTO's retina raster on a
    // high-DPR screen, and this project runs as a Pixel 5 too.
    const match = url.pathname.match(/\/(\d+)\/-?\d+\/-?\d+(?:@2x)?\.png$/);
    if (match) tileZooms.push(Number(match[1]));
  });

  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
  await expect.poll(() => tileZooms.length).toBeGreaterThan(0);

  // A provisional world zoom followed by fitBounds used to request two full
  // tile sets here. The catalogue-aware initialisation must start directly at
  // the final fitted level.
  expect(new Set(tileZooms).size).toBe(1);
});

test("the map keeps its own light palette and markers whatever the site theme is", async ({ page }) => {
  // Light again since 2026-10-12 (the dark ground was tried for a day and read
  // as too dark): the map pins the light token set itself, so it does not
  // follow the site into dark mode.
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  const tokens = async () => page.locator("main.swd-public-map").evaluate((el) => ({
    surface: getComputedStyle(el).getPropertyValue("--sw-surface").trim().toUpperCase(),
    mark: getComputedStyle(el).getPropertyValue("--map-spot").trim().toUpperCase(),
  }));

  for (const theme of ["dark", "light"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
    await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Surfspot Spot B" })).toBeVisible();
    expect(await tokens()).toEqual({ surface: "#FFFFFF", mark: "#1A1F24" });
  }

  // The ground is Voyager's own travel palette, with no colour filter over it.
  const tiles = await page.locator(".swd-public-map .leaflet-tile").first().getAttribute("src");
  expect(tiles).toContain("voyager_nolabels");
  const tint = await page.locator(".swd-public-map .leaflet-tile-pane").evaluate((el) => getComputedStyle(el).filter);
  expect(tint).toBe("none");
});

test("the list trigger shows Landing-style tiles in a bottom row, not a text list or a dark overlay", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map");
  await expect(page.getByRole("button", { name: "Surfspot Spot A" })).toBeVisible();

  const trigger = page.getByRole("button", { name: "Spots im Ausschnitt anzeigen" });
  await trigger.click();
  // The glyph is the switch for the row, so it stays put and reads as pressed
  // (2026-10-11 feedback: it used to disappear on the first tap).
  await expect(trigger).toBeVisible();
  await expect(trigger).toHaveAttribute("aria-pressed", "true");

  // A single horizontal row docked at the bottom (2026-10-06 feedback) — not
  // the old full-height right-hand sidebar that covered the screen.
  const panel = page.locator("#swd-map-list-panel .swd-map-row-scroll");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("link", { name: /Spot A/ })).toBeVisible();
  await expect(panel.getByRole("link", { name: /Spot B/ })).toBeVisible();
  // The dock must sit inside the frame, not blanket it: its top stays well
  // below the top of the map so the map remains visible and pannable above.
  const { panelTop, mapHeight } = await page.evaluate(() => ({
    panelTop: document.querySelector("#swd-map-list-panel")!.getBoundingClientRect().top,
    mapHeight: document.querySelector("main.swd-public-map")!.getBoundingClientRect().height,
  }));
  expect(panelTop).toBeGreaterThan(mapHeight * 0.4);

  // No modal/dialog role and no dark scrim — the map underneath must stay
  // interactive (still pannable) while the panel is open.
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".swd-public-map .leaflet-container")).toBeVisible();

  // Half the map's height at most, and the full width of it.
  const { panelBox, mapBox } = await page.evaluate(() => ({
    panelBox: document.querySelector("#swd-map-list-panel .swd-map-panel")!.getBoundingClientRect().toJSON(),
    mapBox: document.querySelector("main.swd-public-map")!.getBoundingClientRect().toJSON(),
  }));
  expect(panelBox.height).toBeLessThanOrEqual(mapBox.height / 2);
  expect(Math.round(panelBox.width)).toBe(Math.round(mapBox.width));

  // The tiles are the landing card, trimmed: name and place, no wind, no
  // wave, no sport line.
  const tile = panel.locator(".swd-map-row-item").filter({ hasText: "Spot A" });
  await expect(tile).toContainText("Region A · Deutschland");
  await expect(tile).not.toContainText("kn");
  await expect(tile).not.toContainText("Kitesurfen");
  await expect(tile.getByText("—", { exact: true })).toHaveCount(0);

  // The dock has to be ON TOP of the map, not behind it: Leaflet's own panes
  // sit at z-index 200–700, so a bare z-10 left the row invisible under the
  // tiles while still passing a visibility check (2026-10-11 bug).
  const dockOnTop = await page.evaluate(() => {
    const box = document.querySelector("#swd-map-list-panel .swd-map-row-scroll")!.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + 20, box.top + 20);
    return Boolean(hit?.closest("#swd-map-list-panel"));
  });
  expect(dockOnTop).toBe(true);

  await trigger.click();
  await expect(panel).toBeHidden();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
});

test("overlay marks read dark on the light ground, dots are one dark mark", async ({ page }) => {
  // The dots are not tinted by live wind — one dark disc (#1A1F24) with no
  // ring at all (2026-10-12: no white strokes anywhere on the map) — and the
  // overlay marks carry that same ink on both public maps.
  await mockBackend(page);
  await page.goto("/map?lat=54&lon=10&z=9");
  await expect(page.locator(".swd-map-dot").first()).toBeVisible();

  const dot = await page.locator(".swd-map-dot").first().evaluate((node) => ({
    background: getComputedStyle(node).backgroundColor,
    border: getComputedStyle(node).borderTopWidth,
  }));
  expect(dot).toEqual({ background: "rgb(26, 31, 36)", border: "0px" });
  const list = await page.getByRole("button", { name: "Spots im Ausschnitt anzeigen" }).evaluate((node) => getComputedStyle(node).color);
  expect(list).toBe("rgb(26, 31, 36)");
  const active = await page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Spots", exact: true })
    .evaluate((node) => getComputedStyle(node).color);
  expect(active).toBe("rgb(26, 31, 36)");

  // Every dot is the same mark, whatever the live reading says.
  const distinct = await page.locator(".swd-map-dot").evaluateAll((nodes) =>
    [...new Set(nodes.map((node) => getComputedStyle(node).backgroundColor))]);
  expect(distinct).toEqual(["rgb(26, 31, 36)"]);
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

test("spot overview exposes the top-level mode switch without legacy layer chrome", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/map?lat=0&lon=-150&z=10");
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await expect(page.getByRole("group", { name: "Kartenmodus" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Spots", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".swd-map-legend")).toHaveCount(0);
  await expect(page.locator(".swd-map-status")).toHaveCount(0);
  await expect(page.getByText("Keine Spots in diesem Kartenausschnitt", { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/mode=/);
});

test("the wind map carries the same overlay furniture as the spot map", async ({ page }, testInfo) => {
  const tileRequests: URL[] = [];
  await mockBackend(page, (url) => tileRequests.push(url), true);
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");

  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
  await expect(page.locator(".swd-weather-map-labels .maplibregl-canvas")).toBeVisible();
  await expect(page.locator(".swd-country-label", { hasText: "Deutschland" })).toBeVisible();
  expect(tileRequests.some((url) => url.pathname.includes("/rastertiles/voyager_only_labels/"))).toBe(false);
  await expect(page.locator(".swd-field-webgl")).toBeVisible();

  // Same marks, same places, same sizes as the spot map — back + zoom left,
  // the mode switch centred, one glyph right (here: the search).
  const back = page.getByRole("button", { name: "Zurück" });
  const zoomIn = page.getByRole("button", { name: "Vergrößern" });
  await expect(back).toBeVisible();
  await expect(zoomIn).toBeVisible();
  await expect(page.getByRole("button", { name: "Verkleinern" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Wind" }))
    .toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".swd-wx-search").getByRole("button", { name: "Ort, Region oder Spot" })).toBeVisible();

  // The same dark tone as on the spot map, lifted off the field by a halo.
  const backColor = await back.evaluate((node) => getComputedStyle(node).color);
  expect(backColor).toBe("rgb(26, 31, 36)");
  // Same box as the spot map's bare glyphs.
  expect((await back.boundingBox())!.width).toBe(44);

  // Nothing else: no control bar, no layer picker, no legend, no scrubber, no
  // bottom search bar, and no second zoom control from MapLibre itself.
  await expect(page.locator(".swd-wind-bar")).toHaveCount(0);
  await expect(page.locator(".swd-field-timeline")).toHaveCount(0);
  await expect(page.locator(".swd-field-legend")).toHaveCount(0);
  await expect(page.locator(".maplibregl-ctrl-group")).toHaveCount(0);
  await expect(page.locator(".swd-wx-sheet")).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Wetterebene" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Jetzt suchen" })).toHaveCount(0);

  // The zoom glyphs drive the camera.
  const zoomBefore = Number(new URL(page.url()).searchParams.get("z"));
  await zoomIn.click();
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("z"))).toBeGreaterThan(zoomBefore);
  while (Number(new URL(page.url()).searchParams.get("z")) < 8) await zoomIn.click();
  await expect.poll(() => tileRequests.some((url) => url.pathname.includes("/rastertiles/voyager_only_labels/"))).toBe(true);
  await expect(page.locator(".swd-country-label", { hasText: "Deutschland" })).toBeHidden();

  await page.screenshot({
    path: `../.impeccable/review/${testInfo.project.name === "chromium-mobile" ? "mobile" : "desktop"}.png`,
    fullPage: true,
  });
});

test("the wind map's clock runs one day at a time, continuously, from now", async ({ page }) => {
  // A publication on the hour, like the real models publish.
  const now = new Date().setMinutes(0, 0, 0);
  const hours = Array.from({ length: 8 * 6 }, (_, i) => new Date(now + i * 3 * 3_600_000).toISOString());
  await mockBackend(page, undefined, true, { validTimes: hours });
  // Open water, away from the fixture's two spots, so a tap asks the field.
  await page.goto("/map?mode=wind&lat=20&lon=-30&z=4");
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();

  const clock = page.locator(".swd-wx-time");
  const slider = clock.getByRole("slider");
  await expect(slider).toBeVisible();

  // It sits clear of the bottom edge.
  const [clockBox, mapHeight] = [await clock.boundingBox(), await page.evaluate(() => window.innerHeight)];
  expect(mapHeight - (clockBox!.y + clockBox!.height)).toBeGreaterThan(40);

  // The track is today, from now to the end of the day — and it is
  // continuous, not stepped.
  const span = await slider.evaluate((node: HTMLInputElement) => ({ min: +node.min, max: +node.max, value: +node.value, step: node.step }));
  expect(span.value).toBe(span.min);
  expect(span.step).toBe("any");
  expect(Math.abs(span.min - Date.now())).toBeLessThan(5 * 60_000);
  expect(new Date(span.max).getDate()).toBe(new Date(span.min).getDate());
  expect(new Date(span.max).getHours()).toBe(23);
  await expect(clock.locator(".swd-wx-time-marks span").first()).toHaveText("jetzt");
  await expect(clock.locator(".swd-wx-time-value")).toContainText("Heute");

  // Arrows switch the day, and only five days are offered.
  const label = clock.locator(".swd-wx-time-value");
  const atNow = await label.innerText();
  const forward = clock.getByRole("button", { name: "Nächster Tag" });
  await expect(clock.getByRole("button", { name: "Vorheriger Tag" })).toBeDisabled();
  for (let day = 0; day < 4; day += 1) await forward.click();
  await expect(forward).toBeDisabled();
  await expect(label).not.toHaveText(atNow);
  // A later day runs midnight to midnight.
  const laterDay = await slider.evaluate((node: HTMLInputElement) => ({ min: +node.min, value: +node.value }));
  expect(new Date(laterDay.min).getHours()).toBe(0);
  expect(laterDay.value).toBe(laterDay.min);

  await clock.getByRole("button", { name: "Jetzt" }).click();
  await expect(label).toHaveText(atNow);

  // Any moment is a valid position — including one the model never published.
  // Half way along today's track: a fixed 97 minutes fell past midnight when
  // the suite ran late in the evening, and the slider clamped (2026-10-12).
  const between = Math.round(span.min + (span.max - span.min) / 2);
  await slider.evaluate((node: HTMLInputElement, target) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    setter.call(node, String(target));
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
  }, between);
  await expect.poll(() => slider.evaluate((node: HTMLInputElement) => +node.value)).toBe(between);
  await expect(label).toContainText(new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" }).format(new Date(between)));

  // One clock for the map: picking an hour in the forecast sheet moves it.
  await page.locator(".swd-weather-map-base .maplibregl-canvas").click({ position: { x: 220, y: 200 } });
  const sheet = page.locator(".swd-wx-sheet");
  await expect(sheet.locator('[data-wind-bar="wind"]').first()).toBeVisible();
  const bar = sheet.getByRole("group", { name: /Stundenvorhersage/ }).getByRole("button").nth(1);
  const barHour = (await bar.getAttribute("aria-label"))!.slice(0, 5);
  await bar.click();
  await expect(bar).toHaveAttribute("aria-pressed", "true");
  await expect(label).toContainText(barHour);
});

test("the clock reaches five days even when the drawn model only publishes two", async ({ page }) => {
  // The live bug (2026-10-11): over Germany the map draws ICON-D2, whose run
  // ends after two days, so the day arrow went dead on day two. The days come
  // from what the MODELS can answer, and picking a later one asks the backend
  // for that instant so it can switch model.
  const now = new Date().setMinutes(0, 0, 0);
  const shortRun = Array.from({ length: 17 }, (_, i) => new Date(now + i * 3 * 3_600_000).toISOString());
  const asked: Array<string | null> = [];
  await mockBackend(page, undefined, true, {
    validTimes: shortRun,
    longRangeTo: new Date(now + 5 * 24 * 3_600_000).toISOString(),
    onFieldRequest: (url) => asked.push(url.searchParams.get("valid_at")),
  });
  await page.goto("/map?mode=wind&lat=20&lon=-30&z=4");
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();

  const clock = page.locator(".swd-wx-time");
  const next = clock.getByRole("button", { name: "Nächster Tag" });
  const label = clock.locator(".swd-wx-time-value");
  await expect(next).toBeEnabled();

  // Four steps forward — the short run alone would have stopped after one.
  for (let day = 0; day < 4; day += 1) {
    await expect(next).toBeEnabled();
    await next.click();
    await page.waitForTimeout(150);
  }
  await expect(next).toBeDisabled();
  await expect(label).not.toContainText("Heute");

  // The later day was asked for by instant, so the backend can pick a model
  // whose horizon reaches it.
  await expect.poll(() => asked.filter(Boolean).length).toBeGreaterThan(0);
});

test("the wind map's mode switch returns to the spot map, and back goes home", async ({ page }) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();

  await page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Spots", exact: true }).click();
  await expect(page.locator(".swd-public-map .leaflet-container")).toBeVisible();

  await page.goBack();
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
  await page.getByRole("button", { name: "Zurück" }).click();
  await expect(page).toHaveURL(/\/$|\/\?/);
});

test("Spots, Wind and Wellen switch without remounting the map stage", async ({ page }) => {
  await mockBackend(page, undefined, true, { withWaves: true });
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
  const weatherCanvas = page.locator(".swd-weather-map-base .maplibregl-canvas");
  await expect(weatherCanvas).toBeVisible();
  await weatherCanvas.evaluate((node) => { node.setAttribute("data-retained-canvas", "yes"); });
  const camera = () => {
    const query = new URL(page.url()).searchParams;
    return { lat: Number(query.get("lat")), lon: Number(query.get("lon")), zoom: Number(query.get("z")) };
  };
  const expectSameCamera = async (expected: ReturnType<typeof camera>) => {
    await expect.poll(() => camera().zoom).toBeCloseTo(expected.zoom, 2);
    await expect.poll(() => camera().lat).toBeCloseTo(expected.lat, 1);
    await expect.poll(() => camera().lon).toBeCloseTo(expected.lon, 1);
  };
  await page.waitForTimeout(250);
  const openingCamera = camera();

  await page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Spots", exact: true }).click();
  await expect(page.locator(".swd-public-map .leaflet-container")).toBeVisible();
  await expect(page.locator('[data-retained-canvas="yes"]')).toHaveCount(1);
  await expectSameCamera(openingCamera);

  await page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Wind", exact: true }).click();
  await expect(page.locator('[data-retained-canvas="yes"]')).toBeVisible();
  await expectSameCamera(openingCamera);
  await page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Wellen", exact: true }).click();

  await expect(page.locator('[data-retained-canvas="yes"]')).toBeVisible();
  await expect(page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Wellen", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
  await expectSameCamera(openingCamera);
  await expect(page.locator(".swd-field-loading")).toHaveCount(0);
  expect(await page.evaluate(() => performance.getEntriesByType("navigation").length)).toBe(1);
});

test("a tap on open water opens the forecast sheet for that coordinate", async ({ page }, testInfo) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
  const canvas = page.locator(".swd-weather-map-base .maplibregl-canvas");
  await expect(canvas).toBeVisible();

  await canvas.click({ position: { x: 300, y: 260 } });
  const sheet = page.locator(".swd-wx-sheet");
  await expect(sheet).toBeVisible();

  // Says WHERE as a coordinate (no spot to name), and draws the same wind
  // bars as the Spot-Daten forecast, with the hour's temperature above them.
  await expect(sheet).toContainText(/°\s*[NS]/);
  await expect(sheet.locator('[data-wind-bar="wind"]').first()).toBeVisible();
  await expect(sheet.locator('[data-wind-bar="gust"]').first()).toBeVisible();
  await expect(sheet.getByRole("status")).toContainText(/kn/);
  await expect(sheet.getByText(/Sonntag|Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag/).first()).toBeVisible();

  // The map sheet uses the exact Spot-Daten meteogram geometry and puts both
  // readings inside the coloured bands.
  const windBars = sheet.locator('[data-wind-bar="wind"]');
  await expect(windBars.first()).toHaveCSS("width", "22px");
  await expect(windBars.first()).not.toHaveText("");
  await expect(sheet.locator('[data-wind-bar="gust"]').first()).not.toHaveText("");
  const gustHeights = await sheet.locator('[data-wind-bar="gust"]').evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
  expect(Math.max(...gustHeights)).toBeCloseTo(testInfo.project.name === "chromium-mobile" ? 79 : 87, 0);

  // One bottom dock: forecast above, global time regulator immediately below.
  const clock = page.locator(".swd-wx-time");
  const [sheetBox, clockBox] = [await sheet.boundingBox(), await clock.boundingBox()];
  expect(sheetBox!.y + sheetBox!.height).toBeLessThanOrEqual(clockBox!.y + 2);

  await page.screenshot({
    path: `../.impeccable/review/${testInfo.project.name === "chromium-mobile" ? "mobile-sheet" : "desktop-sheet"}.png`,
    fullPage: true,
  });

  // Picking an hour moves the selection, it does not reload the sheet.
  const hours = sheet.getByRole("group", { name: /Stundenvorhersage/ }).getByRole("button");
  await hours.nth(1).click();
  await expect(hours.nth(1)).toHaveAttribute("aria-pressed", "true");

  await sheet.getByRole("button", { name: "Vorhersage schließen" }).click();
  await expect(page.locator(".swd-wx-sheet")).toHaveCount(0);

  // Escape dismisses it too, like every other dismissible surface.
  await canvas.click({ position: { x: 300, y: 260 } });
  await expect(page.locator(".swd-wx-sheet")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".swd-wx-sheet")).toHaveCount(0);
});

test("a tap near a spot dot opens that spot's own forecast, linked to its page", async ({ page }) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=54&lon=10&z=12");
  const canvas = page.locator(".swd-weather-map-base .maplibregl-canvas");
  await expect(canvas).toBeVisible();

  // Spot A sits at the centre; the tap lands beside the dot, not on it — a
  // finger is wider than a 6px circle, and a near miss must still open the
  // spot instead of falling through to the bare coordinate.
  // Poll on the spot's own sheet rather than on "a sheet opened": until the
  // dot layer is live the same tap legitimately opens the point forecast.
  const sheet = page.locator(".swd-wx-sheet");
  const link = sheet.getByRole("link", { name: "Spot A" });
  await expect.poll(async () => {
    const box = (await canvas.boundingBox())!;
    await canvas.click({ position: { x: box.width / 2 + 11, y: box.height / 2 - 9 } });
    if (await link.count()) return "spot";
    await page.keyboard.press("Escape");
    return "point";
  }, { timeout: 15_000 }).toBe("spot");

  await expect(link).toBeVisible();
  expect(await link.getAttribute("href")).toContain("/daten");
  await expect(sheet.locator('[data-wind-bar="wind"]').first()).toBeVisible();
});

test("a spot without hourly forecast says so instead of showing empty bars", async ({ page }) => {
  await mockBackend(page, undefined, true, { emptyForecast: true });
  await page.goto("/map?mode=wind&lat=54&lon=10&z=12");
  const canvas = page.locator(".swd-weather-map-base .maplibregl-canvas");
  await expect(canvas).toBeVisible();

  // Poll on the spot's own sheet, not on "a sheet opened": until the dot
  // layer is live, a tap on the same pixel legitimately opens the point
  // forecast instead, and that used to make this test race.
  const sheet = page.locator(".swd-wx-sheet");
  await expect.poll(async () => {
    const box = (await canvas.boundingBox())!;
    await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });
    const text = await sheet.first().textContent().catch(() => null);
    if (text?.includes("Keine Vorhersage")) return "spot";
    await page.keyboard.press("Escape");
    return text ?? "none";
  }, { timeout: 15_000 }).toBe("spot");

  await expect(sheet.getByRole("status")).toContainText("Keine Vorhersage");
  await expect(sheet.locator('[data-wind-bar="wind"]')).toHaveCount(0);
});

test("keyboard users open the forecast for the point at the map centre", async ({ page }) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
  const canvas = page.locator(".swd-weather-map-base .maplibregl-canvas");
  await canvas.focus();
  await canvas.press("Enter");
  await expect(page.locator(".swd-wx-sheet").locator('[data-wind-bar="wind"]').first()).toBeVisible();
});

test("the map's search is place-only, zooms instead of leaving, and opens the spot's forecast", async ({ page }) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();

  // ONE search surface on every viewport: the glyph opens the site's sheet.
  await expect(page.getByRole("button", { name: "Suchen", exact: true })).toHaveCount(0);
  const glyph = page.locator(".swd-wx-search").getByRole("button", { name: "Ort, Region oder Spot" });
  await expect(glyph).toHaveText("");
  await glyph.click();

  const searchSheet = page.getByRole("dialog", { name: "Suche" });
  await expect(searchSheet).toBeVisible();
  // Place-only: the time and sport axes are not offered on the map.
  await expect(searchSheet.getByText("Wann?", { exact: true })).toHaveCount(0);
  await expect(searchSheet.getByText("Welche Sportart?", { exact: true })).toHaveCount(0);

  await searchSheet.getByText("Wohin?", { exact: true }).click();
  await searchSheet.getByRole("textbox", { name: "Region oder Spot suchen" }).fill("Spot A");
  await searchSheet.getByText("Spot A", { exact: true }).first().click();
  await page.getByRole("button", { name: "Suchen" }).click();

  // Stays on the map and flies to the spot, forecast opened.
  await expect(page).not.toHaveURL(/\/search/);
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("z"))).toBeGreaterThan(8);
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("lat"))).toBeCloseTo(54, 0);
  await expect(page.locator(".swd-wx-sheet").getByRole("link", { name: "Spot A" })).toBeVisible();
});

test("a wave-map link opens the wave field and keeps its shared camera", async ({ page }) => {
  await mockBackend(page, undefined, true, { withWaves: true });
  await page.goto("/map?mode=waves&lat=54&lon=5&z=4");

  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
  await expect(page.getByRole("group", { name: "Kartenmodus" }).getByRole("button", { name: "Wellen" }))
    .toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("lat"))).toBeCloseTo(54, 1);
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("lon"))).toBeCloseTo(5, 1);
});

test("the pre-framed wind entry opens the same bare map", async ({ page }) => {
  // What the spot Daten page and the results page both open. `toggle=0` is a
  // leftover of the removed switch and must simply be harmless.
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&toggle=0&lat=54.4&lon=10.2&z=11");

  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
  await expect(page.locator(".swd-wind-bar")).toHaveCount(0);
  // Pre-framed or not, the map wears the same overlay — `toggle=0` is a
  // leftover of the removed wind-only lock and no longer hides anything.
  await expect(page.locator(".swd-wx-search")).toBeVisible();
  await expect(page.getByRole("group", { name: "Kartenmodus" })).toBeVisible();
});

test("wind mode keeps a close spot zoom, and stops where the field goes flat", async ({ page }) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=54&lon=10&z=12");
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("z"))).toBeGreaterThan(8);

  // Past the published pyramid the screen sits inside a couple of model
  // cells — flat colour, parallel streaks. The map clamps instead
  // (2026-10-11: "wenn ich nah ranzoome, wird kein Wind mehr aufgelöst").
  await page.goto("/map?mode=wind&lat=54&lon=10&z=16");
  await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
  // 14 in the shared URL camera = the canvas' own 13: MapLibre counts one
  // level closer than Leaflet at the same number (2026-10-12).
  await expect.poll(() => Number(new URL(page.url()).searchParams.get("z"))).toBeLessThanOrEqual(14);
});

for (const freshness of ["delayed", "stale", "expired"] as const) {
  test(`${freshness} field publications do not add a stale-run banner`, async ({ page }) => {
    await mockBackend(page, undefined, true, { freshness });
    await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
    await expect(page.locator(".swd-weather-map-base .maplibregl-canvas")).toBeVisible();
    await expect(page.getByText(/nur zur Orientierung/)).toHaveCount(0);
  });
}

test("an offline transition keeps the already loaded wind field visible", async ({ page, context }) => {
  await mockBackend(page, undefined, true);
  await page.goto("/map?mode=wind&lat=50&lon=8&z=4");
  await expect(page.locator(".swd-field-webgl")).toBeVisible();
  // Wait until the manifest has actually settled: going offline while the
  // first request is still in flight races the loading state and makes this
  // test flaky under a loaded worker.
  await expect(page.locator(".swd-field-loading")).toHaveCount(0);
  await context.setOffline(true);
  await expect(page.getByText("Offline · bereits geladene Felddaten")).toBeVisible();
  await expect(page.locator(".swd-field-webgl")).toBeVisible();
  await context.setOffline(false);
});

test("an invalid field publication states the problem and offers a retry", async ({ page }) => {
  await mockBackend(page, undefined, true, { invalidManifest: true });
  await page.goto("/map?mode=wind");
  await expect(page.getByRole("alert")).toContainText("unvollständig oder nicht kompatibel");
  await expect(page.getByRole("button", { name: "Erneut versuchen" })).toBeVisible();
  // The way to the spot map is the spot map's own entry, not a button here.
  await expect(page.getByRole("button", { name: "Spotkarte öffnen" })).toHaveCount(0);
});

for (const [endpointStatus, message] of [[503, "wird gerade vorbereitet"], [500, "konnte nicht geladen werden"]] as const) {
  test(`field endpoint status ${endpointStatus} has a recoverable error state`, async ({ page }) => {
    await mockBackend(page, undefined, true, { endpointStatus });
    await page.goto("/map?mode=wind");
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByRole("button", { name: "Erneut versuchen" })).toBeVisible();
  });
}
