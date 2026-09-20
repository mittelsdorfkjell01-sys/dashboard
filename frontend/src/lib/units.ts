// Unit preferences + formatters. The account settings let a user choose their
// units; these helpers turn the backend's canonical values (wind in knots, wave
// height in metres, temperature in °C, distance in kilometres) into the chosen
// display. PrefsContext is the single source of truth and persists the choice;
// every conditions display site formats through these helpers so a change in the
// settings takes effect everywhere the value is shown.

export type WindUnit = "kn" | "bft" | "ms";
export type WaveUnit = "m" | "ft";
export type TempUnit = "c" | "f";
export type DistanceUnit = "km" | "mi";

export interface Units {
  wind: WindUnit;
  wave: WaveUnit;
  temp: TempUnit;
  distance: DistanceUnit;
}

export const DEFAULT_UNITS: Units = { wind: "kn", wave: "m", temp: "c", distance: "km" };

// The Daten page historically stored a separate wind unit under `sw-wind-unit`
// with the value "kts" (knots) or "ms". Map that legacy token onto the unified
// model so a returning visitor keeps their choice after the systems merged.
export function normalizeWindUnit(value: string | null | undefined): WindUnit | null {
  if (value === "kts" || value === "kn") return "kn";
  if (value === "ms") return "ms";
  if (value === "bft") return "bft";
  return null;
}

// Lower knot bound of each Beaufort force (1..12).
const BEAUFORT_MIN_KN = [1, 4, 7, 11, 17, 22, 28, 34, 41, 48, 56, 64];

export function knotsToBeaufort(kn: number): number {
  let bft = 0;
  for (let i = 0; i < BEAUFORT_MIN_KN.length; i++) {
    if (kn >= BEAUFORT_MIN_KN[i]) bft = i + 1;
  }
  return bft;
}

const KN_TO_MS = 0.514444;
const M_TO_FT = 3.28084;
const KM_TO_MI = 0.621371;

const comma = (n: number) => n.toFixed(1).replace(".", ",");

/** Numeric wind reading in the chosen unit (no unit suffix), for compact
 *  instrument labels that render the unit separately. */
export function windValue(kn: number, unit: WindUnit): string {
  if (unit === "bft") return String(knotsToBeaufort(kn));
  if (unit === "ms") return comma(kn * KN_TO_MS);
  return String(Math.round(kn));
}

export function formatWind(kn: number | null | undefined, unit: WindUnit): string {
  if (kn == null) return "—";
  if (unit === "bft") return `${knotsToBeaufort(kn)} Bft`;
  if (unit === "ms") return `${comma(kn * KN_TO_MS)} m/s`;
  return `${Math.round(kn)} kn`;
}

export function formatWave(m: number | null | undefined, unit: WaveUnit): string {
  if (m == null) return "—";
  return unit === "ft" ? `${comma(m * M_TO_FT)} ft` : `${comma(m)} m`;
}

export function formatTemp(c: number | null | undefined, unit: TempUnit): string {
  if (c == null) return "—";
  return unit === "f" ? `${Math.round((c * 9) / 5 + 32)} °F` : `${Math.round(c)} °C`;
}

/** Format a distance given in kilometres. Sub-10 values keep one decimal so a
 *  nearby reference station reads e.g. "3,4 km" / "2,1 mi". */
export function formatDistance(km: number | null | undefined, unit: DistanceUnit): string {
  if (km == null) return "—";
  const value = unit === "mi" ? km * KM_TO_MI : km;
  const suffix = unit === "mi" ? "mi" : "km";
  return value < 10 ? `${comma(value)} ${suffix}` : `${Math.round(value)} ${suffix}`;
}

/** Numeric wave height in the chosen unit (no suffix). */
export function waveValue(m: number, unit: WaveUnit): string {
  return comma(unit === "ft" ? m * M_TO_FT : m);
}

/** Numeric air/water temperature in the chosen unit (no degree/suffix). */
export function tempValue(c: number, unit: TempUnit): string {
  return String(Math.round(unit === "f" ? (c * 9) / 5 + 32 : c));
}

/** Numeric distance in the chosen unit (no suffix); km in, one decimal < 10. */
export function distanceValue(km: number, unit: DistanceUnit): string {
  const value = unit === "mi" ? km * KM_TO_MI : km;
  return value < 10 ? comma(value) : String(Math.round(value));
}

export const WAVE_UNIT_SUFFIX: Record<WaveUnit, string> = { m: "m", ft: "ft" };
export const TEMP_UNIT_SUFFIX: Record<TempUnit, string> = { c: "°C", f: "°F" };
export const DISTANCE_UNIT_SUFFIX: Record<DistanceUnit, string> = { km: "km", mi: "mi" };

export const WIND_UNIT_LABELS: Record<WindUnit, string> = { kn: "Knoten", bft: "Beaufort", ms: "Meter/s" };
export const WAVE_UNIT_LABELS: Record<WaveUnit, string> = { m: "Meter", ft: "Fuß" };
export const TEMP_UNIT_LABELS: Record<TempUnit, string> = { c: "Celsius", f: "Fahrenheit" };
export const DISTANCE_UNIT_LABELS: Record<DistanceUnit, string> = { km: "Kilometer", mi: "Meilen" };

/** Short unit suffix as shown next to a reading (e.g. legend header, sidebar). */
export const WIND_UNIT_SUFFIX: Record<WindUnit, string> = { kn: "kn", bft: "Bft", ms: "m/s" };
