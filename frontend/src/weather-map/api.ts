import { API_BASE, request } from "../lib/api";
import type { ActiveFieldResponse, FieldComparison, FieldObservation, FieldSample, FieldSampleSeries, FieldViewportBounds, WaveFieldSample } from "./contracts";

export const getActiveWindField = (
  model?: string,
  center?: [number, number],
  bounds?: FieldViewportBounds,
  signal?: AbortSignal,
  /** The moment the clock stands on. The short-range model only publishes two
   *  days, so asking for day four has to select a model that reaches it. */
  validAt?: string,
) => {
  const query = new URLSearchParams();
  if (model) query.set("model", model);
  if (validAt) query.set("valid_at", validAt);
  if (center) {
    query.set("lon", center[0].toFixed(5));
    query.set("lat", center[1].toFixed(5));
  }
  if (bounds) {
    query.set("west", bounds.west.toFixed(5));
    query.set("south", bounds.south.toFixed(5));
    query.set("east", bounds.east.toFixed(5));
    query.set("north", bounds.north.toFixed(5));
  }
  const suffix = query.size ? `?${query}` : "";
  return request<ActiveFieldResponse>(`/weather-fields/wind${suffix}`, { signal, timeoutMs: 12_000 });
};

export const getActiveWaveField = (
  model?: string,
  center?: [number, number],
  bounds?: FieldViewportBounds,
  signal?: AbortSignal,
) => {
  const query = new URLSearchParams();
  if (model) query.set("model", model);
  if (center) { query.set("lon", center[0].toFixed(5)); query.set("lat", center[1].toFixed(5)); }
  if (bounds) {
    query.set("west", bounds.west.toFixed(5)); query.set("south", bounds.south.toFixed(5));
    query.set("east", bounds.east.toFixed(5)); query.set("north", bounds.north.toFixed(5));
  }
  const suffix = query.size ? `?${query}` : "";
  return request<ActiveFieldResponse>(`/weather-fields/waves${suffix}`, { signal, timeoutMs: 12_000 });
};

export function getActiveWindSample(
  latitude: number,
  longitude: number,
  validAt: string,
  model?: string,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    lat: latitude.toFixed(6),
    lon: longitude.toFixed(6),
    valid_at: validAt,
  });
  if (model) query.set("model", model);
  return request<FieldSample>(`/weather-fields/wind/sample?${query}`, {
    signal,
    timeoutMs: 12_000,
  });
}

/** One point across every published instant, in a single request — the data
 *  behind the map's bottom forecast sheet for a tapped coordinate. */
export function getActiveWindSampleSeries(latitude: number, longitude: number, model?: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ lat: latitude.toFixed(6), lon: longitude.toFixed(6) });
  if (model) query.set("model", model);
  return request<FieldSampleSeries>(`/weather-fields/wind/sample/series?${query}`, { signal, timeoutMs: 12_000 });
}

export function getActiveWaveSample(latitude: number, longitude: number, validAt: string, model?: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ lat: latitude.toFixed(6), lon: longitude.toFixed(6), valid_at: validAt });
  if (model) query.set("model", model);
  return request<WaveFieldSample>(`/weather-fields/waves/sample?${query}`, { signal, timeoutMs: 12_000 });
}

export function getActiveWaveSampleSeries(latitude: number, longitude: number, model?: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ lat: latitude.toFixed(6), lon: longitude.toFixed(6) });
  if (model) query.set("model", model);
  return request<FieldSampleSeries>(`/weather-fields/waves/sample/series?${query}`, { signal, timeoutMs: 12_000 });
}

export function getActiveWindComparison(
  latitude: number,
  longitude: number,
  validAt: string,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    lat: latitude.toFixed(6),
    lon: longitude.toFixed(6),
    valid_at: validAt,
  });
  return request<FieldComparison>(`/weather-fields/wind/compare?${query}`, {
    signal,
    timeoutMs: 12_000,
  });
}

export function resolveFieldAssetUrl(value: string): string {
  if (/^https?:\/\//i.test(value)) return value;
  const api = new URL(API_BASE, window.location.origin);
  return new URL(value, api.origin).toString();
}

export const getWindObservations = (signal?: AbortSignal) =>
  request<{ observations: FieldObservation[] }>("/weather-fields/wind/observations", {
    signal,
    timeoutMs: 12_000,
  });
