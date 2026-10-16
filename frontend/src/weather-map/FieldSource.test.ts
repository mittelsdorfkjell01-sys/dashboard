import { afterEach, describe, expect, it, vi } from "vitest";
import { FieldSource } from "./FieldSource";
import type { FieldManifest } from "./contracts";
import type { DecodedFieldTile } from "./fieldTile";

vi.mock("./fieldTile", async (importOriginal) => {
  const original = await importOriginal<typeof import("./fieldTile")>();
  return {
    ...original,
    decodeFieldTile: vi.fn(async (key: string) => ({
      key,
      header: { schema: "swd-field-tile-v2", width: 2, height: 2, overlap: 0, z: 4, x: 8, y: 5, valid_time: "2026-10-03T12:00:00Z", variables: [] },
      arrays: { wind_u: new Float32Array(4), wind_v: new Float32Array(4) },
    })),
  };
});

const manifest = {
  tile_scheme: { lod: [{ source_zoom: 4, consumer_zoom_min: 0, consumer_zoom_max: 5, source_decimation: 1 }] },
} as FieldManifest;

describe("FieldSource", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("selects the frozen source LOD", () => {
    expect(new FieldSource(manifest).sourceZoom(3)).toBe(4);
  });

  it("bilinearly samples paired u/v from the same decoded tile", () => {
    const width = 4;
    const tile: DecodedFieldTile = {
      key: "sample",
      header: { schema: "swd-field-tile-v2", width, height: width, overlap: 1, z: 1, x: 1, y: 0, valid_time: "2026-10-03T12:00:00Z", variables: [] },
      arrays: {
        wind_u: new Float32Array(width * width).fill(4),
        wind_v: new Float32Array(width * width).fill(3),
        wind_gust: new Float32Array(width * width).fill(8),
      },
    };
    expect(new FieldSource(manifest).sample([tile], 45, 45)).toEqual({ u: 4, v: 3, gust: 8 });
  });

  it("does not reuse a pending tile request whose signal was replaced", async () => {
    let request = 0;
    vi.stubGlobal("window", { location: { origin: "http://localhost" } });
    vi.stubGlobal("fetch", vi.fn((_url: string | URL | Request, init?: RequestInit) => {
      request += 1;
      if (request === 1) {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(init.signal?.reason ?? new DOMException("Aborted", "AbortError")), { once: true });
        });
      }
      return Promise.resolve(new Response(new Uint8Array([1]), { status: 200 }));
    }));
    const source = new FieldSource({
      ...manifest,
      coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
      field_template: "/fields/{valid_time}/{z}/{x}/{y}.swf2.gz",
    });
    const bounds = {
      getWest: () => 10,
      getEast: () => 11,
      getSouth: () => 53,
      getNorth: () => 54,
    } as Parameters<FieldSource["loadViewport"]>[0];
    const firstController = new AbortController();
    const first = source.loadViewport(bounds, 4, "2026-10-03T12:00:00Z", firstController.signal).catch(() => []);
    firstController.abort();

    const replacement = source.loadViewport(bounds, 4, "2026-10-03T12:00:00Z", new AbortController().signal);

    await expect(replacement).resolves.toHaveLength(1);
    await first;
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("reuses a low-priority prefetched tile for the next visible timestep", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost" } });
    let resolveFetch: ((response: Response) => void) | undefined;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    })));
    const source = new FieldSource({
      ...manifest,
      coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
      field_template: "/fields/{valid_time}/{z}/{x}/{y}.swf2.gz",
    });
    const bounds = {
      getWest: () => 10,
      getEast: () => 11,
      getSouth: () => 53,
      getNorth: () => 54,
    } as Parameters<FieldSource["loadViewport"]>[0];
    const validAt = "2026-10-03T15:00:00Z";
    const prefetched = source.prefetchViewport(bounds, 4, validAt);
    const visible = source.loadViewport(bounds, 4, validAt, new AbortController().signal);

    expect(fetch).toHaveBeenCalledTimes(1);
    resolveFetch?.(new Response(new Uint8Array([1]), { status: 200 }));
    await expect(visible).resolves.toHaveLength(1);
    await prefetched;
  });

  it("loads a one-tile safety ring for fast pan and zoom transitions", async () => {
    vi.stubGlobal("window", { location: { origin: "http://localhost" } });
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(
      new Response(new Uint8Array([1]), { status: 200 }),
    )));
    const source = new FieldSource({
      ...manifest,
      coverage: { west: -23.5, south: 29.5, east: 45, north: 70.5 },
      field_template: "/fields/{valid_time}/{z}/{x}/{y}.swf2.gz",
    });
    const bounds = {
      getWest: () => 10,
      getEast: () => 11,
      getSouth: () => 53,
      getNorth: () => 54,
    } as Parameters<FieldSource["loadViewport"]>[0];

    const tiles = await source.loadViewport(
      bounds,
      4,
      "2026-10-03T12:00:00Z",
      undefined,
      1,
    );

    expect(tiles).toHaveLength(9);
    expect(fetch).toHaveBeenCalledTimes(9);
  });
});
