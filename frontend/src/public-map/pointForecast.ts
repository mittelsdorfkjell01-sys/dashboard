import { useEffect, useState } from "react";
import type { ForecastConfidence, ForecastDay, ForecastHour, ForecastSeries } from "../lib/api";
import { normalizeForecast, type NormalizedForecastSeries } from "../lib/forecastNormalization";
import { getActiveWaveSampleSeries, getActiveWindField, getActiveWindSampleSeries } from "../weather-map/api";
import type { FieldSample, WaveFieldSample } from "../weather-map/contracts";
import { MS_TO_KN } from "./fieldSample";

/**
 * The forecast of an arbitrary point on the map (2026-11-21: "ein Punkt auf
 * der Karte … soll unten einen Forecast wie auf der Datenseite zeigen").
 *
 * A spot has its own calibrated forecast (`/spots/{id}/forecast`); a tapped
 * point has only the published FIELDS. This turns the two point series the
 * backend already serves (`/weather-fields/wind|waves/sample/series`) into the
 * Daten page's forecast shape, so the very same meteogram can draw it. Only
 * what the fields carry is filled in — no weather glyph, no confidence, no
 * spread — and the model and run travel along so the source stays visible.
 */

const finite = (value: number | null | undefined): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);

function localDate(at: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(at));
}

export function pointSeries(wind: FieldSample[], waves: WaveFieldSample[], timeZone: string): ForecastSeries | null {
  const byTime = new Map<string, { wind?: FieldSample; wave?: WaveFieldSample }>();
  const key = (at: string) => new Date(at).toISOString();
  for (const sample of wind) byTime.set(key(sample.valid_at), { ...byTime.get(key(sample.valid_at)), wind: sample });
  for (const sample of waves) byTime.set(key(sample.valid_at), { ...byTime.get(key(sample.valid_at)), wave: sample });
  if (!byTime.size) return null;

  const days = new Map<string, ForecastHour[]>();
  for (const [time, { wind: w, wave }] of [...byTime.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const height = finite(wave?.total_wave_height_m);
    const hour: ForecastHour = {
      time,
      wind: w ? w.speed_ms * MS_TO_KN : null,
      gust: w && finite(w.gust_ms) != null ? w.gust_ms! * MS_TO_KN : null,
      wind_ms: w?.speed_ms ?? null,
      gust_ms: finite(w?.gust_ms),
      dir: finite(w?.direction_from_deg),
      air: finite(w?.temperature_c),
      precip: finite(w?.precipitation_mm),
      cloud_cover_pct: finite(w?.cloud_cover_percent),
      pressure_msl_hpa: finite(w?.pressure_hpa),
      swell: height,
      period: finite(wave?.total_wave_period_s),
      swell_dir: finite(wave?.total_wave_direction_from_deg),
      waves: wave ? {
        total_wave: { significant_height_m: height, mean_period_s: finite(wave.total_wave_period_s), mean_direction_from_deg: finite(wave.total_wave_direction_from_deg) },
        primary_swell: { significant_height_m: finite(wave.primary_swell_height_m), mean_period_s: finite(wave.primary_swell_period_s), mean_direction_from_deg: finite(wave.primary_swell_direction_from_deg) },
        wind_sea: { significant_height_m: finite(wave.wind_sea_height_m), mean_period_s: finite(wave.wind_sea_period_s), mean_direction_from_deg: finite(wave.wind_sea_direction_from_deg) },
      } : null,
      sst: null,
      observation_type: "forecast",
    };
    const date = localDate(time, timeZone);
    days.set(date, [...(days.get(date) ?? []), hour]);
  }

  const model = [...new Set([...wind.map((sample) => sample.model), waves[0]?.model].filter(Boolean))].join(" + ");
  const forecastDays: ForecastDay[] = [...days.entries()].map(([date, hours]) => ({
    date,
    local_date: date,
    // The fields publish no confidence; the normaliser turns this into "none".
    confidence: null as unknown as ForecastConfidence,
    summary: { wind_avg: null, wind_max: null, gust_max: null, air_min: null, air_max: null, swell_max: null },
    hours,
    detail: "hourly",
  }));
  return {
    spot_id: "",
    model,
    generated_at: wind[0]?.model_run ?? waves[0]?.model_run ?? new Date().toISOString(),
    days: forecastDays,
    timezone: timeZone,
    availability: {
      atmosphere: wind.length ? "available" : "unavailable_provider",
      solar: "unavailable_provider",
      marine: waves.some((sample) => finite(sample.total_wave_height_m) != null) ? "available" : "unavailable_out_of_range",
    },
  };
}

/**
 * Wind for a point across the whole map clock (2026-11-21): the default
 * series is the short-range model (ICON-D2, ~48 h), while the map's clock
 * runs on to the long-range model's horizon. So: the default series first,
 * then every other model that covers the point and reaches further, each
 * filling only the hours still missing — the finest model wins wherever it
 * exists, and no hour is invented.
 */
async function windSeries(lat: number, lng: number, signal: AbortSignal): Promise<FieldSample[]> {
  const base = (await getActiveWindSampleSeries(lat, lng, undefined, signal)).samples as FieldSample[];
  const last = base.reduce((max, sample) => Math.max(max, Date.parse(sample.valid_at)), 0);
  let models: Array<{ key: string; valid_to?: string | null; covers_point: boolean; priority: number }>;
  try {
    models = (await getActiveWindField(undefined, [lng, lat], undefined, signal)).available_models ?? [];
  } catch { return base; }
  const used = new Set(base.map((sample) => sample.model));
  const further = models
    .filter((model) => model.covers_point !== false && !used.has(model.key) && model.valid_to && Date.parse(model.valid_to) > last)
    .sort((a, b) => a.priority - b.priority);
  const merged = new Map(base.map((sample) => [Date.parse(sample.valid_at), sample]));
  for (const model of further) {
    try {
      const samples = (await getActiveWindSampleSeries(lat, lng, model.key, signal)).samples as FieldSample[];
      for (const sample of samples) { const at = Date.parse(sample.valid_at); if (!merged.has(at)) merged.set(at, sample); }
    } catch { /* a missing model only leaves its hours empty */ }
  }
  return [...merged.values()].sort((a, b) => Date.parse(a.valid_at) - Date.parse(b.valid_at));
}

export interface PointForecastState { forecast: NormalizedForecastSeries | null; loading: boolean; source?: string }

/** Wind and wave series for one coordinate, fetched together; either may be
 *  missing (inland, outside the wave model) without failing the other. */
export function usePointForecast(point: { lng: number; lat: number } | null): PointForecastState {
  const [state, setState] = useState<PointForecastState>({ forecast: null, loading: false });
  useEffect(() => {
    if (!point) { setState({ forecast: null, loading: false }); return; }
    const controller = new AbortController();
    setState({ forecast: null, loading: true });
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    void Promise.allSettled([
      windSeries(point.lat, point.lng, controller.signal),
      getActiveWaveSampleSeries(point.lat, point.lng, undefined, controller.signal),
    ]).then(([windResult, waveResult]) => {
      if (controller.signal.aborted) return;
      const wind = windResult.status === "fulfilled" ? windResult.value : [];
      const waves = waveResult.status === "fulfilled" ? (waveResult.value.samples as WaveFieldSample[]) : [];
      const raw = pointSeries(wind, waves, timeZone);
      const run = wind[0]?.model_run ?? waves[0]?.model_run;
      // One line: which model draws which hours, and the run behind it.
      const name = (key: string) => key.replace(/_/g, "-").replace(/-0P25$/i, "").toUpperCase();
      const windModels = [...new Set(wind.map((sample) => name(sample.model)))];
      const parts = [windModels.length ? `Wind ${windModels.join(" → ")}` : "", waves[0] ? `Wellen ${name(waves[0].model)}` : ""].filter(Boolean);
      const source = raw ? `${parts.join(" · ")}${run ? ` · Lauf ${new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(run))}` : ""}` : undefined;
      setState({ forecast: raw ? normalizeForecast(raw) : null, loading: false, source });
    });
    return () => controller.abort();
  }, [point?.lng, point?.lat]); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}
