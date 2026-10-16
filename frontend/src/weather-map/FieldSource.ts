import type { LngLatBounds } from "maplibre-gl";
import type { FieldManifest } from "./contracts";
import { resolveFieldAssetUrl } from "./api";
import { decodeFieldSeries, decodeFieldTile, type DecodedFieldTile } from "./fieldTile";

const MAX_CACHE_TILES = 320;

interface PendingTile {
  promise: Promise<DecodedFieldTile>;
  signal?: AbortSignal;
  token: symbol;
}

function tileX(longitude: number, zoom: number): number {
  return Math.max(0, Math.min(2 ** zoom - 1, Math.floor(((longitude + 180) / 360) * 2 ** zoom)));
}

function tileY(latitude: number, zoom: number): number {
  const clamped = Math.max(-85.05112878, Math.min(85.05112878, latitude));
  const value = (1 - Math.asinh(Math.tan((clamped * Math.PI) / 180)) / Math.PI) / 2;
  return Math.max(0, Math.min(2 ** zoom - 1, Math.floor(value * 2 ** zoom)));
}

function validTimeKey(value: string): string {
  const date = new Date(value);
  return `${date.getUTCFullYear()}${String(date.getUTCMonth() + 1).padStart(2, "0")}${String(date.getUTCDate()).padStart(2, "0")}T${String(date.getUTCHours()).padStart(2, "0")}Z`;
}

/** Linear blend of two decoded tiles of the same cell, written into `out`. */
function blendInto(out: DecodedFieldTile, lower: DecodedFieldTile, upper: DecodedFieldTile, alpha: number): DecodedFieldTile {
  for (const [name, lowerValues] of Object.entries(lower.arrays)) {
    const upperValues = upper.arrays[name];
    if (!upperValues || upperValues.length !== lowerValues.length) continue;
    let target = out.arrays[name];
    if (!target || target.length !== lowerValues.length) {
      target = new Float32Array(lowerValues.length);
      out.arrays[name] = target;
    }
    for (let index = 0; index < lowerValues.length; index += 1) {
      // NaN (no data) in either end stays NaN — a cell is never half-invented.
      target[index] = lowerValues[index] + (upperValues[index] - lowerValues[index]) * alpha;
    }
  }
  return out;
}

export class FieldSource {
  private readonly cache = new Map<string, DecodedFieldTile>();
  private readonly pending = new Map<string, PendingTile>();
  /** Reused output buffers for the blended field, one per tile cell: the time
   *  slider re-blends on every step and must not allocate megabytes per drag. */
  private readonly blended = new Map<string, DecodedFieldTile>();

  constructor(readonly manifest: FieldManifest) {}

  /** Published instants, ascending. */
  private get publishedTimes(): string[] {
    return [...this.manifest.valid_times].sort((a, b) => Date.parse(a) - Date.parse(b));
  }

  /**
   * The two published instants around an arbitrary time, and how far between
   * them it lies. The map's clock is continuous while the field is published
   * every few hours, so everything in between is interpolated — the same
   * linear u/v blend the backend already applies when it samples a point
   * (`temporal_uv` in app/spatial_fields/serving.py), just applied to whole
   * tiles here because tiles are published per instant.
   */
  bracket(target: string): { lower: string; upper?: string; alpha: number } {
    const times = this.publishedTimes;
    const at = Date.parse(target);
    if (!times.length) return { lower: target, alpha: 0 };
    if (at <= Date.parse(times[0])) return { lower: times[0], alpha: 0 };
    const last = times[times.length - 1];
    if (at >= Date.parse(last)) return { lower: last, alpha: 0 };
    const upperIndex = times.findIndex((time) => Date.parse(time) >= at);
    const upper = times[upperIndex];
    if (Date.parse(upper) === at) return { lower: upper, alpha: 0 };
    const lower = times[upperIndex - 1];
    const span = Date.parse(upper) - Date.parse(lower);
    return { lower, upper, alpha: span > 0 ? (at - Date.parse(lower)) / span : 0 };
  }

  sourceZoom(consumerZoom: number): number {
    const lod = this.manifest.tile_scheme.lod.find(
      (item) => consumerZoom >= item.consumer_zoom_min && consumerZoom <= item.consumer_zoom_max,
    );
    return lod?.source_zoom ?? this.manifest.tile_scheme.lod[this.manifest.tile_scheme.lod.length - 1]?.source_zoom ?? 5;
  }

  private url(validAt: string, z: number, x: number, y: number): string {
    const value = this.manifest.field_template
      .replace("{valid_time}", validTimeKey(validAt))
      .replace("{z}", String(z))
      .replace("{x}", String(x))
      .replace("{y}", String(y));
    return resolveFieldAssetUrl(value);
  }

  private seriesUrl(z: number, x: number, y: number): string | null {
    if (!this.manifest.series_template) return null;
    return resolveFieldAssetUrl(
      this.manifest.series_template
        .replace("{z}", String(z))
        .replace("{x}", String(x))
        .replace("{y}", String(y)),
    );
  }

  private async load(validAt: string, z: number, x: number, y: number, signal?: AbortSignal) {
    const key = `${validAt}/${z}/${x}/${y}`;
    const cached = this.cache.get(key);
    if (cached) {
      this.cache.delete(key);
      this.cache.set(key, cached);
      return cached;
    }
    const existing = this.pending.get(key);
    // A promise bound to an older AbortSignal must never be inherited by a
    // replacement viewport request. Otherwise rapid time changes can surface
    // the previous request's AbortError as a failure of the new field.
    if (
      existing
      && !signal?.aborted
      && (existing.signal === signal || existing.signal === undefined)
    ) return existing.promise;
    const token = Symbol(key);
    const promise = fetch(this.url(validAt, z, x, y), { signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Windfeld-Tile nicht verfügbar (${response.status}).`);
        return response.arrayBuffer();
      })
      .then((payload) => decodeFieldTile(key, payload))
      .then((tile) => {
        this.cache.set(key, tile);
        while (this.cache.size > MAX_CACHE_TILES) {
          const oldest = this.cache.keys().next().value as string | undefined;
          if (!oldest) break;
          this.cache.delete(oldest);
        }
        return tile;
      })
      .finally(() => {
        // An older request may finish after its replacement. It may only
        // remove itself, never the newer in-flight entry for the same tile.
        if (this.pending.get(key)?.token === token) this.pending.delete(key);
      });
    const entry: PendingTile = { promise, signal, token };
    this.pending.set(key, entry);
    return promise;
  }

  async loadViewport(bounds: LngLatBounds, consumerZoom: number, validAt: string, signal?: AbortSignal, bufferTiles = 0) {
    const tasks = this.viewportTasks(bounds, consumerZoom, validAt, signal, bufferTiles);
    // One unavailable cell must not blank the whole field: a viewport at the
    // edge of the published grid, or a prefetch buffer tile the run never
    // wrote, used to reject the entire `Promise.all` and leave the map empty
    // (2026-10-12). Draw every cell that answered; only report a failure when
    // nothing did.
    const settled = await Promise.allSettled(tasks);
    const tiles = settled.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []));
    if (!tiles.length && tasks.length) {
      const reason = settled.find((result) => result.status === "rejected");
      const error = reason && reason.status === "rejected" ? reason.reason : undefined;
      throw error instanceof Error ? error : new Error("Windfeld konnte nicht geladen werden.");
    }
    return tiles;
  }

  /** The field at an arbitrary instant: the published tiles when the time is
   *  one of them, the blend of the two surrounding ones otherwise. */
  async loadViewportAt(bounds: LngLatBounds, consumerZoom: number, target: string, signal?: AbortSignal, bufferTiles = 0): Promise<DecodedFieldTile[]> {
    const { lower, upper, alpha } = this.bracket(target);
    if (!upper || alpha <= 0) return this.loadViewport(bounds, consumerZoom, lower, signal, bufferTiles);
    const [lowerTiles, upperTiles] = await Promise.all([
      this.loadViewport(bounds, consumerZoom, lower, signal, bufferTiles),
      this.loadViewport(bounds, consumerZoom, upper, signal, bufferTiles),
    ]);
    const upperByCell = new Map(upperTiles.map((tile) => [`${tile.header.z}/${tile.header.x}/${tile.header.y}`, tile]));
    return lowerTiles.map((tile) => {
      const cell = `${tile.header.z}/${tile.header.x}/${tile.header.y}`;
      const counterpart = upperByCell.get(cell);
      if (!counterpart) return tile;
      let out = this.blended.get(cell);
      if (!out || out.header.width !== tile.header.width || out.header.height !== tile.header.height) {
        out = { key: `${cell}@blend`, header: { ...tile.header }, arrays: {} };
        this.blended.set(cell, out);
      }
      out.header = { ...tile.header, valid_time: target };
      return blendInto(out, tile, counterpart, alpha);
    });
  }

  /** True when every tile the viewport needs for this instant is already
   *  decoded — the clock then moves without a loading state. */
  hasViewportAt(bounds: LngLatBounds, consumerZoom: number, target: string, bufferTiles = 0): boolean {
    const { lower, upper, alpha } = this.bracket(target);
    const needed = alpha > 0 && upper ? [lower, upper] : [lower];
    const z = this.sourceZoom(consumerZoom);
    const west = Math.max(this.manifest.coverage.west, bounds.getWest());
    const east = Math.min(this.manifest.coverage.east, bounds.getEast());
    const south = Math.max(this.manifest.coverage.south, bounds.getSouth());
    const north = Math.min(this.manifest.coverage.north, bounds.getNorth());
    if (west >= east || south >= north) return true;
    const xStart = Math.max(tileX(this.manifest.coverage.west, z), tileX(west, z) - bufferTiles);
    const xEnd = Math.min(tileX(this.manifest.coverage.east, z), tileX(east, z) + bufferTiles);
    const yStart = Math.max(tileY(this.manifest.coverage.north, z), tileY(north, z) - bufferTiles);
    const yEnd = Math.min(tileY(this.manifest.coverage.south, z), tileY(south, z) + bufferTiles);
    for (const time of needed) {
      for (let y = yStart; y <= yEnd; y += 1) {
        for (let x = xStart; x <= xEnd; x += 1) {
          if (!this.cache.has(`${time}/${z}/${x}/${y}`)) return false;
        }
      }
    }
    return true;
  }

  async prefetchViewport(bounds: LngLatBounds, consumerZoom: number, validAt: string, bufferTiles = 0) {
    await Promise.allSettled(this.viewportTasks(bounds, consumerZoom, validAt, undefined, bufferTiles));
  }

  private viewportTasks(
    bounds: LngLatBounds,
    consumerZoom: number,
    validAt: string,
    signal?: AbortSignal,
    bufferTiles = 0,
  ) {
    const z = this.sourceZoom(consumerZoom);
    const west = Math.max(this.manifest.coverage.west, bounds.getWest());
    const east = Math.min(this.manifest.coverage.east, bounds.getEast());
    const south = Math.max(this.manifest.coverage.south, bounds.getSouth());
    const north = Math.min(this.manifest.coverage.north, bounds.getNorth());
    if (west >= east || south >= north) return [];
    const xStart = Math.max(tileX(this.manifest.coverage.west, z), tileX(west, z) - bufferTiles);
    const xEnd = Math.min(tileX(this.manifest.coverage.east, z), tileX(east, z) + bufferTiles);
    const yStart = Math.max(tileY(this.manifest.coverage.north, z), tileY(north, z) - bufferTiles);
    const yEnd = Math.min(tileY(this.manifest.coverage.south, z), tileY(south, z) + bufferTiles);
    const tasks: Array<Promise<DecodedFieldTile>> = [];
    for (let y = yStart; y <= yEnd; y += 1) {
      for (let x = xStart; x <= xEnd; x += 1) {
        tasks.push(this.load(validAt, z, x, y, signal));
      }
    }
    return tasks;
  }

  sample(tiles: DecodedFieldTile[], longitude: number, latitude: number): { u: number; v: number; gust?: number } | null {
    for (const tile of tiles) {
      const z = tile.header.z;
      const worldX = ((longitude + 180) / 360) * 2 ** z;
      const clamped = Math.max(-85.05112878, Math.min(85.05112878, latitude));
      const worldY = ((1 - Math.asinh(Math.tan((clamped * Math.PI) / 180)) / Math.PI) / 2) * 2 ** z;
      if (Math.floor(worldX) !== tile.header.x || Math.floor(worldY) !== tile.header.y) continue;
      const overlap = tile.header.overlap ?? 0;
      const inner = tile.header.width - overlap * 2;
      const px = overlap + (worldX - tile.header.x) * inner - 0.5;
      const py = overlap + (worldY - tile.header.y) * inner - 0.5;
      const x0 = Math.floor(px), y0 = Math.floor(py), x1 = x0 + 1, y1 = y0 + 1;
      if (x0 < 0 || y0 < 0 || x1 >= tile.header.width || y1 >= tile.header.height) return null;
      const interpolate = (array: Float32Array | undefined) => {
        if (!array) return undefined;
        const values = [array[y0 * tile.header.width + x0], array[y0 * tile.header.width + x1], array[y1 * tile.header.width + x0], array[y1 * tile.header.width + x1]];
        if (values.some((value) => !Number.isFinite(value))) return undefined;
        const dx = px - x0, dy = py - y0;
        return (values[0] * (1 - dx) + values[1] * dx) * (1 - dy) + (values[2] * (1 - dx) + values[3] * dx) * dy;
      };
      const u = interpolate(tile.arrays.wind_u ?? tile.arrays.wave_u);
      const v = interpolate(tile.arrays.wind_v ?? tile.arrays.wave_v);
      if (u === undefined || v === undefined) return null;
      return { u, v, gust: interpolate(tile.arrays.wind_gust) };
    }
    return null;
  }


  async samplePointSeries(
    longitude: number,
    latitude: number,
    signal?: AbortSignal,
  ): Promise<Array<{ validAt: string; values: Record<string, number | undefined> }>> {
    const z = Math.max(...this.manifest.tile_scheme.lod.map((item) => item.source_zoom));
    const x = tileX(longitude, z);
    const y = tileY(latitude, z);
    const url = this.seriesUrl(z, x, y);
    if (!url) throw new Error("Diese Publikation enthält noch keine Zeitreihen-Kacheln.");
    const response = await fetch(url, { signal });
    if (!response.ok) throw new Error(`Forecast-Zeitreihe nicht verfügbar (${response.status}).`);
    const entries = decodeFieldSeries(await response.arrayBuffer());
    const samples: Array<{ validAt: string; values: Record<string, number | undefined> }> = [];
    for (const entry of entries) {
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
      const tile = await decodeFieldTile(`${entry.validTime}/${z}/${x}/${y}`, entry.payload);
      const values = this.sampleValues(tile, longitude, latitude);
      if (values) samples.push({ validAt: tile.header.valid_time, values });
    }
    return samples;
  }

  private sampleValues(
    tile: DecodedFieldTile,
    longitude: number,
    latitude: number,
  ): Record<string, number | undefined> | null {
    const z = tile.header.z;
    const worldX = ((longitude + 180) / 360) * 2 ** z;
    const clamped = Math.max(-85.05112878, Math.min(85.05112878, latitude));
    const worldY = ((1 - Math.asinh(Math.tan((clamped * Math.PI) / 180)) / Math.PI) / 2) * 2 ** z;
    if (Math.floor(worldX) !== tile.header.x || Math.floor(worldY) !== tile.header.y) return null;
    const overlap = tile.header.overlap ?? 0;
    const inner = tile.header.width - overlap * 2;
    const px = overlap + (worldX - tile.header.x) * inner - 0.5;
    const py = overlap + (worldY - tile.header.y) * inner - 0.5;
    const x0 = Math.floor(px), y0 = Math.floor(py), x1 = x0 + 1, y1 = y0 + 1;
    if (x0 < 0 || y0 < 0 || x1 >= tile.header.width || y1 >= tile.header.height) return null;
    const values: Record<string, number | undefined> = {};
    for (const [name, array] of Object.entries(tile.arrays)) {
      const neighbours = [array[y0 * tile.header.width + x0], array[y0 * tile.header.width + x1], array[y1 * tile.header.width + x0], array[y1 * tile.header.width + x1]];
      if (neighbours.some((value) => !Number.isFinite(value))) {
        values[name] = undefined;
        continue;
      }
      const dx = px - x0, dy = py - y0;
      values[name] = (neighbours[0] * (1 - dx) + neighbours[1] * dx) * (1 - dy)
        + (neighbours[2] * (1 - dx) + neighbours[3] * dx) * dy;
    }
    const vectorNames = values.wave_u !== undefined ? ["wave_u", "wave_v"] : ["wind_u", "wind_v"];
    return values[vectorNames[0]] === undefined || values[vectorNames[1]] === undefined ? null : values;
  }
}
