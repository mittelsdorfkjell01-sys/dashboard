import type { FieldDisplayMode, FieldLayer } from "./contracts";

/** Public map products share one camera and URL contract. */
export type ExplorerMode = "spots" | "wind" | "waves";

export interface FieldUrlState {
  mode: ExplorerMode;
  center: [number, number];
  zoom: number;
  validAt?: string;
  model?: string;
  display: FieldDisplayMode;
  layer: FieldLayer;
  showSpots: boolean;
}

const DEFAULT_CENTER: [number, number] = [9.3, 48.5];

export function parseFieldUrlState(search: string): FieldUrlState {
  const query = new URLSearchParams(search);
  const requestedMode = query.get("mode");
  const mode: ExplorerMode = requestedMode === "wind" || requestedMode === "waves" ? requestedMode : "spots";
  const lat = Number(query.get("lat"));
  const lon = Number(query.get("lon"));
  const zoom = Number(query.get("z"));
  return {
    mode,
    center:
      Number.isFinite(lat) && lat >= -85 && lat <= 85 && Number.isFinite(lon) && lon >= -180 && lon <= 180
        ? [lon, lat]
        : DEFAULT_CENTER,
    zoom: Number.isFinite(zoom) && zoom >= 1 && zoom <= 18 ? zoom : 3.5,
    validAt: query.get("valid_at") || undefined,
    model: query.get("model") || undefined,
    display: query.get("display") === "arrows" ? "arrows" : "particles",
    layer: (["wind", "waves", "gust", "temperature", "precipitation", "pressure", "clouds"] as FieldLayer[])
      .includes(query.get("layer") as FieldLayer)
      ? query.get("layer") as FieldLayer
      : mode === "waves" ? "waves" : "wind",
    showSpots: query.get("spots") !== "0",
  };
}

export function fieldUrlSearch(search: string, patch: Partial<FieldUrlState>): string {
  const current = parseFieldUrlState(search);
  const next = { ...current, ...patch };
  const query = new URLSearchParams(search);
  query.set("mode", next.mode);
  query.set("lat", next.center[1].toFixed(5));
  query.set("lon", next.center[0].toFixed(5));
  query.set("z", next.zoom.toFixed(2));
  if (next.validAt) query.set("valid_at", next.validAt); else query.delete("valid_at");
  if (next.model) query.set("model", next.model); else query.delete("model");
  query.set("display", next.display);
  if (next.layer === "wind") query.delete("layer"); else query.set("layer", next.layer);
  if (next.showSpots) query.delete("spots"); else query.set("spots", "0");
  if (next.mode !== "spots") query.delete("spot");
  return `?${query}`;
}

/** A link into the weather map, pre-framed on a place. `toggle: false` locks
 *  it to the wind field (no Spots/Wind switch) — what the spot Daten page and
 *  the results page both open. */
export function windMapHref(center: [number, number], zoom: number, options: { toggle?: boolean } = {}): string {
  const query = new URLSearchParams({
    mode: "wind",
    lat: center[1].toFixed(5),
    lon: center[0].toFixed(5),
    z: zoom.toFixed(2),
  });
  if (options.toggle === false) query.set("toggle", "0");
  return `/map?${query}`;
}

export function updateFieldUrl(patch: Partial<FieldUrlState>, replace = true): void {
  const search = fieldUrlSearch(window.location.search, patch);
  const url = `${window.location.pathname}${search}${window.location.hash}`;
  window.history[replace ? "replaceState" : "pushState"](null, "", url);
}
