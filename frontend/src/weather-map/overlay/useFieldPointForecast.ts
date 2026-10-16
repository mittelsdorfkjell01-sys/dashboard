import { useEffect, useRef, useState } from "react";
import { getActiveWaveSampleSeries, getActiveWindSampleSeries } from "../api";
import { FieldSource } from "../FieldSource";
import type { FieldManifest } from "../contracts";
import { fieldSampleSlots, fieldTileSeriesSlots, type MapForecastSlot } from "./slots";

/**
 * The hourly forecast at one tapped coordinate: every published instant of the
 * active wind field in a single request, mapped onto the sheet's slots. A new
 * point (or none) aborts the request in flight, so a run of taps leaves exactly
 * one answer behind.
 */
export function useFieldPointForecast(
  point: [number, number] | null,
  manifests: FieldManifest[] = [],
  product: "wind" | "waves" = "wind",
): { slots: MapForecastSlot[]; loading: boolean } {
  const [slots, setSlots] = useState<MapForecastSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  const longitude = point?.[0];
  const latitude = point?.[1];

  useEffect(() => {
    request.current?.abort();
    if (longitude === undefined || latitude === undefined) {
      request.current = null;
      setSlots([]);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setSlots([]);
    setLoading(true);
    const staticManifests = manifests.filter((item) => item.series_template);
    const load = staticManifests.length
      ? Promise.all(staticManifests.map((item) => (
          new FieldSource(item).samplePointSeries(longitude, latitude, controller.signal)
        ))).then((groups) => {
          const merged = new Map<string, (typeof groups)[number][number]>();
          for (const group of groups) for (const sample of group) {
            if (!merged.has(sample.validAt)) merged.set(sample.validAt, sample);
          }
          return fieldTileSeriesSlots([...merged.values()], product);
        })
      : (product === "waves" ? getActiveWaveSampleSeries : getActiveWindSampleSeries)(
          latitude,
          longitude,
          manifests[0]?.model,
          controller.signal,
        ).then((result) => fieldSampleSlots(result.samples));
    load
      .then((result) => { if (!controller.signal.aborted) setSlots(result); })
      .catch(() => { if (!controller.signal.aborted) setSlots([]); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [longitude, latitude, manifests, product]);

  return { slots, loading };
}
