import type {
  AvailabilityStatus,
  ForecastConfidence,
  ForecastConfidenceSource,
  ForecastDay,
  ForecastHour,
  ForecastSeries,
  ForecastTimezoneStatus,
  SpreadBand,
} from "./api";

export type ForecastDiagnosticCode =
  | "invalid_timezone"
  | "invalid_timestamp"
  | "duplicate_timestamp"
  | "unsorted_timestamp"
  | "invalid_number"
  | "negative_value"
  | "invalid_direction"
  | "invalid_spread"
  | "insufficient_spread_members"
  | "gust_below_wind"
  | "invalid_confidence"
  | "invalid_confidence_source"
  | "invalid_availability"
  | "invalid_detail";

export type ForecastDiagnostic = {
  code: ForecastDiagnosticCode;
  path: string;
  message: string;
};

export type NormalizedForecastHour = ForecastHour & {
  utcKey: string;
  localDate: string;
  localTime: string;
  localTimeWithOffset: string;
  localHour: number;
  localMinute: number;
};

export type NormalizedForecastDay = Omit<ForecastDay, "hours" | "confidence" | "detail" | "confidence_source"> & {
  hours: NormalizedForecastHour[];
  confidence: ForecastConfidence | null;
  confidenceSource: ForecastConfidenceSource | null;
  detail: ForecastDay["detail"] | null;
};

export type NormalizedForecastSeries = Omit<ForecastSeries, "days" | "availability"> & {
  days: NormalizedForecastDay[];
  availability?: Record<"atmosphere" | "solar" | "marine", AvailabilityStatus | null>;
  timezone: string;
  timezoneStatus: ForecastTimezoneStatus;
  diagnostics: ForecastDiagnostic[];
};

const CONFIDENCE = new Set<ForecastConfidence>(["hoch", "mittel", "niedrig"]);
const CONFIDENCE_SOURCE = new Set<ForecastConfidenceSource>(["spread", "calendar"]);
const AVAILABILITY = new Set<AvailabilityStatus>([
  "available", "available_stale", "not_applicable_inland", "unavailable_out_of_range",
  "unavailable_provider", "unknown_location_type",
]);

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numeric(
  value: unknown,
  path: string,
  diagnostics: ForecastDiagnostic[],
  options: { minimum?: number; maximum?: number; direction?: boolean } = {},
): number | null {
  if (value == null) return null;
  const parsed = finite(value);
  if (parsed == null) {
    diagnostics.push({ code: "invalid_number", path, message: "Wert ist keine endliche Zahl." });
    return null;
  }
  if (options.minimum != null && parsed < options.minimum) {
    diagnostics.push({ code: "negative_value", path, message: `Wert liegt unter ${options.minimum}.` });
    return null;
  }
  if (options.maximum != null && parsed > options.maximum) {
    diagnostics.push({ code: options.direction ? "invalid_direction" : "invalid_number", path, message: `Wert liegt über ${options.maximum}.` });
    return null;
  }
  return parsed;
}

function spreadBand(value: unknown, path: string, diagnostics: ForecastDiagnostic[]): SpreadBand | null {
  if (value == null) return null;
  if (typeof value !== "object") {
    diagnostics.push({ code: "invalid_spread", path, message: "Modellspanne ist kein Objekt." });
    return null;
  }
  const raw = value as Record<string, unknown>;
  const n = finite(raw.n);
  const low = numeric(raw.low, `${path}.low`, diagnostics, { minimum: 0 });
  const median = numeric(raw.median, `${path}.median`, diagnostics, { minimum: 0 });
  const high = numeric(raw.high, `${path}.high`, diagnostics, { minimum: 0 });
  if (n == null || !Number.isInteger(n) || n < 2) {
    diagnostics.push({ code: "insufficient_spread_members", path, message: "Eine Modellspanne benötigt mindestens zwei Modelle." });
    return null;
  }
  if (low == null || median == null || high == null || low > median || median > high) {
    diagnostics.push({ code: "invalid_spread", path, message: "Erwartet wird low ≤ median ≤ high." });
    return null;
  }
  return { low, median, high, n };
}

export function resolveForecastTimezone(value: unknown): ForecastTimezoneStatus {
  const requested = typeof value === "string" && value.trim() ? value : "UTC";
  try {
    const effective = new Intl.DateTimeFormat("en", { timeZone: requested }).resolvedOptions().timeZone;
    return { requested, effective, status: "valid" };
  } catch {
    return { requested, effective: "UTC", status: "fallback_utc" };
  }
}

function localParts(instant: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(instant);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  const localDate = `${part("year")}-${part("month")}-${part("day")}`;
  const localTime = `${part("hour")}:${part("minute")}`;
  const localHour = Number(part("hour"));
  const localMinute = localHour * 60 + Number(part("minute"));
  const offset = new Intl.DateTimeFormat("en", { timeZone: timezone, timeZoneName: "shortOffset" })
    .formatToParts(instant).find((item) => item.type === "timeZoneName")?.value ?? "UTC";
  return { localDate, localTime, localTimeWithOffset: `${localTime} ${offset}`, localHour, localMinute };
}

function normalizeSummary(summary: ForecastDay["summary"], path: string, diagnostics: ForecastDiagnostic[]): ForecastDay["summary"] {
  const result = { ...summary } as ForecastDay["summary"] & Record<string,unknown>;
  const nonNegative = ["wind_avg","wind_max","gust_max","swell_max","precipitation_sum_mm","precipitation_probability_max_pct","cloud_cover_mean_pct","uv_index_max"];
  for (const key of nonNegative) {
    if (key in result) result[key] = numeric(result[key], `${path}.${key}`, diagnostics, { minimum: 0, maximum: key.endsWith("_pct") ? 100 : undefined });
  }
  for (const key of ["air_min","air_max","temperature_min_c","temperature_max_c","apparent_temperature_min_c","apparent_temperature_max_c"]) {
    if (key in result) result[key] = numeric(result[key], `${path}.${key}`, diagnostics);
  }
  if (result.gust_max != null && result.wind_max != null && result.gust_max < result.wind_max) {
    diagnostics.push({ code: "gust_below_wind", path: `${path}.gust_max`, message: "Maximale Böe liegt unter dem maximalen Mittelwind." });
    result.gust_max = null;
  }
  if (result.air_min != null && result.air_max != null && result.air_min > result.air_max) {
    diagnostics.push({ code: "invalid_number", path, message: "Temperaturminimum liegt über dem Maximum." });
    result.air_min = null; result.air_max = null;
  }
  return result as ForecastDay["summary"];
}

function normalizeHour(raw: ForecastHour, path: string, timezone: string, diagnostics: ForecastDiagnostic[]): NormalizedForecastHour | null {
  const timestamp = typeof raw?.time === "string" ? raw.time : "";
  // A timestamp without an explicit offset is not a unique instant.
  if (!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp)) {
    diagnostics.push({ code: "invalid_timestamp", path: `${path}.time`, message: "Zeitpunkt enthält keinen eindeutigen UTC-Offset." });
    return null;
  }
  const epoch = Date.parse(timestamp);
  if (!Number.isFinite(epoch)) {
    diagnostics.push({ code: "invalid_timestamp", path: `${path}.time`, message: "Zeitpunkt ist ungültig." });
    return null;
  }
  const instant = new Date(epoch);
  const wind = numeric(raw.wind, `${path}.wind`, diagnostics, { minimum: 0 });
  let gust = numeric(raw.gust, `${path}.gust`, diagnostics, { minimum: 0 });
  if (wind != null && gust != null && gust < wind) {
    diagnostics.push({ code: "gust_below_wind", path: `${path}.gust`, message: "Böe liegt unter dem Mittelwind." });
    gust = null;
  }
  const normalized: NormalizedForecastHour = {
    ...raw,
    time: instant.toISOString(),
    utcKey: instant.toISOString(),
    ...localParts(instant, timezone),
    wind,
    gust,
    dir: numeric(raw.dir, `${path}.dir`, diagnostics, { minimum: 0, maximum: 359.999, direction: true }),
    air: numeric(raw.air, `${path}.air`, diagnostics),
    swell: numeric(raw.swell, `${path}.swell`, diagnostics, { minimum: 0 }),
    period: numeric(raw.period, `${path}.period`, diagnostics, { minimum: 0 }),
    swell_dir: numeric(raw.swell_dir, `${path}.swell_dir`, diagnostics, { minimum: 0, maximum: 359.999, direction: true }),
    precip: numeric(raw.precip, `${path}.precip`, diagnostics, { minimum: 0 }),
    sst: numeric(raw.sst, `${path}.sst`, diagnostics),
    apparent_temperature_c: numeric(raw.apparent_temperature_c, `${path}.apparent_temperature_c`, diagnostics),
    cloud_cover_pct: numeric(raw.cloud_cover_pct, `${path}.cloud_cover_pct`, diagnostics, { minimum: 0, maximum: 100 }),
    pressure_msl_hpa: numeric(raw.pressure_msl_hpa, `${path}.pressure_msl_hpa`, diagnostics, { minimum: 0 }),
    uv_index: numeric(raw.uv_index, `${path}.uv_index`, diagnostics, { minimum: 0 }),
    wind_spread: spreadBand(raw.wind_spread, `${path}.wind_spread`, diagnostics),
  };
  return normalized;
}

export function normalizeForecast(raw: ForecastSeries): NormalizedForecastSeries {
  const diagnostics: ForecastDiagnostic[] = [];
  const timezoneStatus = resolveForecastTimezone(raw?.timezone);
  if (timezoneStatus.status === "fallback_utc") {
    diagnostics.push({ code: "invalid_timezone", path: "timezone", message: `Ungültige Zeitzone ${timezoneStatus.requested}; UTC wird verwendet.` });
  }
  const seen = new Set<string>();
  let previousEpoch = -Infinity;
  const days = (Array.isArray(raw?.days) ? raw.days : []).map((day, dayIndex): NormalizedForecastDay => {
    const confidence = CONFIDENCE.has(day.confidence as ForecastConfidence) ? day.confidence as ForecastConfidence : null;
    if (confidence == null) diagnostics.push({ code: "invalid_confidence", path: `days[${dayIndex}].confidence`, message: "Unbekannte Sicherheit wurde als nicht verfügbar behandelt." });
    const confidenceSource = CONFIDENCE_SOURCE.has(day.confidence_source as ForecastConfidenceSource) ? day.confidence_source as ForecastConfidenceSource : null;
    if (confidenceSource == null && day.confidence_source != null) diagnostics.push({ code: "invalid_confidence_source", path: `days[${dayIndex}].confidence_source`, message: "Unbekannte Sicherheitsquelle wurde ignoriert." });
    const detail = day.detail === "trend" || day.detail === "hourly" ? day.detail : null;
    if (detail == null) diagnostics.push({ code: "invalid_detail", path: `days[${dayIndex}].detail`, message: "Fehlender oder ungültiger Detailstatus wurde als nicht verfügbar behandelt." });
    const hours: NormalizedForecastHour[] = [];
    for (const [hourIndex, hour] of (Array.isArray(day.hours) ? day.hours : []).entries()) {
      const normalized = normalizeHour(hour, `days[${dayIndex}].hours[${hourIndex}]`, timezoneStatus.effective, diagnostics);
      if (!normalized) continue;
      const epoch = Date.parse(normalized.utcKey);
      if (seen.has(normalized.utcKey)) {
        diagnostics.push({ code: "duplicate_timestamp", path: `days[${dayIndex}].hours[${hourIndex}].time`, message: "Doppelter UTC-Zeitpunkt wurde nicht erneut übernommen." });
        continue;
      }
      if (epoch < previousEpoch) diagnostics.push({ code: "unsorted_timestamp", path: `days[${dayIndex}].hours[${hourIndex}].time`, message: "UTC-Zeitachse war unsortiert und wurde geordnet." });
      seen.add(normalized.utcKey);
      previousEpoch = Math.max(previousEpoch, epoch);
      hours.push(normalized);
    }
    hours.sort((a, b) => Date.parse(a.utcKey) - Date.parse(b.utcKey));
    return { ...day, summary: normalizeSummary(day.summary, `days[${dayIndex}].summary`, diagnostics), confidence, confidenceSource, detail, hours };
  });
  days.sort((a,b)=>(a.local_date??a.date).localeCompare(b.local_date??b.date));
  const availability = Object.fromEntries(Object.entries(raw.availability ?? {}).map(([key, value]) => {
    if (AVAILABILITY.has(value as AvailabilityStatus)) return [key, value];
    diagnostics.push({ code: "invalid_availability", path: `availability.${key}`, message: "Unbekannter Verfügbarkeitsstatus wurde als nicht verfügbar behandelt." });
    return [key, null];
  })) as Record<"atmosphere" | "solar" | "marine", AvailabilityStatus | null>;
  return { ...raw, timezone: timezoneStatus.effective, timezoneStatus, availability, days, diagnostics };
}

export function forecastHours(forecast: NormalizedForecastSeries | null | undefined): NormalizedForecastHour[] {
  return forecast?.days.flatMap((day) => day.hours).sort((a, b) => Date.parse(a.utcKey) - Date.parse(b.utcKey)) ?? [];
}

export function closestForecastUtc(forecast: NormalizedForecastSeries | null | undefined, now = Date.now()): string | null {
  const hours = forecastHours(forecast);
  if (!hours.length) return null;
  return hours.reduce((best, hour) => Math.abs(Date.parse(hour.utcKey) - now) < Math.abs(Date.parse(best.utcKey) - now) ? hour : best).utcKey;
}

export function selectedForecastHour(forecast: NormalizedForecastSeries | null | undefined, selectedAtUtc: string | null): NormalizedForecastHour | null {
  if (!selectedAtUtc) return null;
  return forecastHours(forecast).find((hour) => hour.utcKey === selectedAtUtc) ?? null;
}
