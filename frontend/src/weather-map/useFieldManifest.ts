import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../lib/api";
import { getActiveWaveField, getActiveWindField } from "./api";
import type { ActiveFieldResponse, FieldViewportBounds } from "./contracts";

export type FieldManifestState =
  | { status: "loading"; data?: ActiveFieldResponse }
  | { status: "ready" | "delayed" | "stale" | "expired"; data: ActiveFieldResponse }
  | { status: "unavailable" | "offline" | "error"; message: string; data?: ActiveFieldResponse };

function hasUsableManifest(data: ActiveFieldResponse, product: "wind" | "waves"): boolean {
  const manifest = data?.manifest;
  const variableNames = Array.isArray(manifest?.variables) ? new Set(manifest.variables.map((variable) => variable.name)) : new Set();
  const coverage = manifest?.coverage;
  return Boolean(
    manifest
      && manifest.contract_version === "weather-field-v2"
      && manifest.publication_id
      && manifest.model
      && manifest.model_run
      && Array.isArray(manifest.valid_times)
      && manifest.valid_times.length > 0
      && manifest.valid_times.every((value) => Number.isFinite(Date.parse(value)))
      && coverage
      && [coverage.west, coverage.south, coverage.east, coverage.north].every(Number.isFinite)
      && coverage.west < coverage.east
      && coverage.south < coverage.north
      && (product === "wind"
        ? variableNames.has("wind_u") && variableNames.has("wind_v")
        : variableNames.has("wave_u") && variableNames.has("wave_v") && variableNames.has("total_wave_height"))
      && manifest.field_template
      && manifest.tile_scheme?.tile_size > 0
      && Array.isArray(manifest.tile_scheme?.lod)
      && manifest.tile_scheme.lod.length > 0,
  );
}

export function useFieldManifest(
  model?: string,
  center?: [number, number],
  bounds?: FieldViewportBounds,
  product: "wind" | "waves" = "wind",
  /** The instant the viewer is looking at, when it matters for which model
   *  can answer (a day beyond the short-range horizon). */
  validAt?: string,
) {
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<FieldManifestState>({ status: "loading" });
  const reload = useCallback(() => setNonce((value) => value + 1), []);
  const centerLongitude = center?.[0];
  const centerLatitude = center?.[1];
  const viewportWest = bounds?.west;
  const viewportSouth = bounds?.south;
  const viewportEast = bounds?.east;
  const viewportNorth = bounds?.north;
  useEffect(() => {
    const controller = new AbortController();
    const requestCenter = centerLongitude !== undefined && centerLatitude !== undefined
      ? [centerLongitude, centerLatitude] as [number, number]
      : undefined;
    setState((current) => ({ status: "loading", data: current.data }));
    const requestBounds = [viewportWest, viewportSouth, viewportEast, viewportNorth].every((value) => value !== undefined)
      ? { west: viewportWest!, south: viewportSouth!, east: viewportEast!, north: viewportNorth! }
      : undefined;
    const getField = product === "waves" ? getActiveWaveField : getActiveWindField;
    getField(model, requestCenter, requestBounds, controller.signal, validAt)
      .then((data) => {
        if ((data as { enabled?: boolean }).enabled !== true) {
          setState({
            status: "unavailable",
            message: product === "waves"
              ? "Der erste validierte DWD-Wellenlauf wird noch vorbereitet."
              : "Das Wetterfeld wird gerade vorbereitet. Die Spotkarte bleibt verfügbar.",
          });
          return;
        }
        if (!hasUsableManifest(data, product)) {
          setState({ status: "error", message: `Das veröffentlichte ${product === "waves" ? "Wellenfeld" : "Windfeld"} ist unvollständig oder nicht kompatibel.` });
          return;
        }
        const freshness = data.status;
        setState((current) => {
          const stableData = current.data?.publication_id === data.publication_id
            && current.data.manifest.model === data.manifest.model
            ? { ...data, manifest: current.data.manifest }
            : data;
          return { status: freshness === "fresh" ? "ready" : freshness, data: stableData };
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const offline = !navigator.onLine || (error instanceof ApiError && error.status === 0);
        const unavailable = error instanceof ApiError && [404, 503].includes(error.status);
        setState((current) => ({
          status: offline ? "offline" : unavailable ? "unavailable" : "error",
          message: offline
            ? "Du bist offline. Bereits geladene Kartendaten bleiben sichtbar."
            : unavailable
              ? "Das Wetterfeld wird gerade vorbereitet. Die Spotkarte bleibt verfügbar."
              : `Das ${product === "waves" ? "Wellenfeld" : "Windfeld"} konnte nicht geladen werden.`,
          data: current.data,
        }));
      });
    return () => controller.abort();
  }, [model, centerLongitude, centerLatitude, viewportWest, viewportSouth, viewportEast, viewportNorth, nonce, product, validAt]);

  useEffect(() => {
    const markOffline = () => setState((current) => ({
      status: "offline",
      message: "Du bist offline. Bereits geladene Kartendaten bleiben sichtbar.",
      data: current.data,
    }));
    const markOnline = () => setNonce((value) => value + 1);
    window.addEventListener("offline", markOffline);
    window.addEventListener("online", markOnline);
    return () => {
      window.removeEventListener("offline", markOffline);
      window.removeEventListener("online", markOnline);
    };
  }, []);

  return { state, reload };
}
