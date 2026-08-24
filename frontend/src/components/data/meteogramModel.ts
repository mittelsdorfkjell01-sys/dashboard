import type { AvailabilityStatus } from "../../lib/api";
import type { NormalizedForecastDay, NormalizedForecastHour, NormalizedForecastSeries } from "../../lib/forecastNormalization";

export type ChartScale = { min: number; mid: number; max: number };
export type MeteogramDayGroup = { date: string; start: number; count: number; confidence: string | null; confidenceSource: "spread" | "calendar" | null };
export type MeteogramModel = {
  slots: NormalizedForecastHour[];
  detailDays: NormalizedForecastDay[];
  trendDays: NormalizedForecastDay[];
  dayGroups: MeteogramDayGroup[];
  scales: { precipitation: ChartScale; temperature: ChartScale; wind: ChartScale; wave: ChartScale; period: ChartScale };
  temperatureSegments: NormalizedForecastHour[][];
  marineStatus: AvailabilityStatus | null;
  showMarine: boolean;
};

const finite = (value: number | null | undefined): value is number => value != null && Number.isFinite(value);

function niceCeiling(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

function zeroScale(values: number[], fallbackMax: number): ChartScale {
  const max = niceCeiling(values.length ? Math.max(...values) : fallbackMax);
  return { min: 0, mid: max / 2, max };
}

function temperatureScale(values: number[]): ChartScale {
  if (!values.length) return { min: 0, mid: 15, max: 30 };
  let min = Math.floor(Math.min(...values) / 5) * 5;
  let max = Math.ceil(Math.max(...values) / 5) * 5;
  if (min === max) { min -= 5; max += 5; }
  return { min, mid: (min + max) / 2, max };
}

function temperatureSegments(slots: NormalizedForecastHour[]): NormalizedForecastHour[][] {
  const epochs = slots.map((slot) => Date.parse(slot.utcKey));
  const deltas = epochs.slice(1).map((epoch, index) => epoch - epochs[index]).filter((delta) => delta > 0);
  const cadence = deltas.length ? [...deltas].sort((a, b) => a - b)[Math.floor(deltas.length / 2)] : 3_600_000;
  const segments: NormalizedForecastHour[][] = [];
  let current: NormalizedForecastHour[] = [];
  slots.forEach((slot, index) => {
    const gap = index > 0 && epochs[index] - epochs[index - 1] > cadence * 1.5;
    if (!finite(slot.air) || gap) {
      if (current.length) segments.push(current);
      current = [];
    }
    if (finite(slot.air)) current.push(slot);
  });
  if (current.length) segments.push(current);
  return segments;
}

export function buildMeteogramModel(forecast: NormalizedForecastSeries): MeteogramModel {
  const detailDays = forecast.days.filter((day) => day.detail === "hourly" && day.hours.length > 0).slice(0, 5);
  const trendDays = forecast.days.filter((day) => day.detail === "trend").slice(0, 5);
  const slots = detailDays.flatMap((day) => day.hours);
  const dayGroups: MeteogramDayGroup[] = [];
  for (const day of detailDays) {
    const start = slots.findIndex((slot) => slot.localDate === (day.local_date ?? day.date));
    const count = day.hours.length;
    if (start >= 0 && count > 0) dayGroups.push({ date: day.local_date ?? day.date, start, count, confidence: day.confidence, confidenceSource: day.confidenceSource });
  }
  const precipitation = slots.map((slot) => slot.precip).filter(finite);
  const temperature = slots.map((slot) => slot.air).filter(finite);
  const wind = slots.flatMap((slot) => [slot.wind, slot.gust, slot.wind_spread?.high]).filter(finite);
  const wave = slots.map((slot) => slot.swell).filter(finite);
  const period = slots.map((slot) => slot.period).filter(finite);
  const marineStatus = forecast.availability?.marine ?? null;
  const showMarine = (marineStatus === "available" || marineStatus === "available_stale") && (wave.length > 0 || period.length > 0);
  return {
    slots, detailDays, trendDays, dayGroups, marineStatus, showMarine,
    scales: {
      precipitation: zeroScale(precipitation, 1),
      temperature: temperatureScale(temperature),
      wind: zeroScale(wind, 20),
      wave: zeroScale(wave, 2),
      period: zeroScale(period, 10),
    },
    temperatureSegments: temperatureSegments(slots),
  };
}

export function hasValidSpread(hour: NormalizedForecastHour): boolean {
  const band = hour.wind_spread;
  return Boolean(band && band.n >= 2 && finite(band.low) && finite(band.median) && finite(band.high) && band.low <= band.median && band.median <= band.high);
}

export function marineStatusText(status: AvailabilityStatus | null): string {
  switch (status) {
    case "available_stale": return "Marinewerte stammen vom letzten verfügbaren Stand.";
    case "not_applicable_inland": return "Wellenhöhe und Periode sind für diesen Binnen-Spot nicht anwendbar.";
    case "unavailable_out_of_range": return "Marineprognose liegt für diesen Ort außerhalb des Modellbereichs.";
    case "unavailable_provider": return "Marineprognose ist beim Datenanbieter derzeit nicht verfügbar.";
    case "unknown_location_type": return "Marineprognose ist für diesen Standort nicht eindeutig anwendbar.";
    default: return "Wellenhöhe und Periode sind derzeit nicht verfügbar.";
  }
}
