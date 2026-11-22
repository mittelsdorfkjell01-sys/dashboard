// Backend fixtures for the redesigned public map (e2e/public-map.spec.ts).
// Copied from e2e/map.spec.ts so the old map's spec can retire on its own.
import type { Page } from "@playwright/test";
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
  page: Page,
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
