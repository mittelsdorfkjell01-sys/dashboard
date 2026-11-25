import type { ForecastHour, WaveComponents } from "./api";

/**
 * Which number the "Welle" readout actually shows.
 *
 * The backend sends the sea state as four separate components (see
 * `docs/weather-waves-contract.md`): `total_wave` is the combined sea state,
 * `wind_sea` the locally forced part, `primary_swell`/`secondary_swell` the
 * spectral swell partitions. The flat `swell` field is **deprecated and carries
 * primary swell only** — it is never populated from total-wave values.
 *
 * The spot page used to print that deprecated field under the label "Welle",
 * while the weather map coloured the same word from `total_wave`. The two
 * surfaces therefore disagreed for any sea with a wind wave on top of the
 * swell, and the smaller of the two numbers was the one the visitor read before
 * driving to the beach.
 *
 * One rule, one place: the headline wave height is the **total wave**. The
 * deprecated field stays as a fallback only because it is what the legacy
 * transition path populates when the marine core is absent; the contract calls
 * `total_wave` "effectively always present", so this is a safety net rather
 * than a routine code path. A missing value stays missing — it is never
 * substituted by another component, because "no data" and "flat" are different
 * statements (see the help page, section "Wetter, Wellen & Gezeiten").
 */
export function headlineWaveM(
  hour: { swell?: number | null; waves?: WaveComponents | null } | null | undefined,
): number | null {
  if (!hour) return null;
  const total = hour.waves?.total_wave?.significant_height_m;
  if (typeof total === "number" && Number.isFinite(total)) return total;
  return typeof hour.swell === "number" && Number.isFinite(hour.swell) ? hour.swell : null;
}

/** Narrow helper for call sites that already hold a full `ForecastHour`. */
export function hourWaveM(hour: ForecastHour | null | undefined): number | null {
  return headlineWaveM(hour);
}

type WaveHour = { swell?: number | null; period?: number | null; swell_dir?: number | null; waves?: WaveComponents | null } | null | undefined;
const num = (value: number | null | undefined): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

/**
 * The sea's period for the wave readouts (Daten wave mode, 2026-11-25): the
 * total wave's peak period, else its mean period, else the primary wave's
 * peak period (NOAA sends that one only), else the legacy flat field. Same
 * rule as the height: never borrowed from the wind sea or a swell partition.
 */
export function headlineWavePeriodS(hour: WaveHour): number | null {
  if (!hour) return null;
  const total = hour.waves?.total_wave;
  const primary = hour.waves?.primary_wave;
  return num(total?.peak_period_s) ?? num(total?.mean_period_s) ?? num(primary?.peak_period_s) ?? num(hour.period);
}

/** Where the sea comes from (degrees), same order as the period. */
export function headlineWaveFromDeg(hour: WaveHour): number | null {
  if (!hour) return null;
  const total = hour.waves?.total_wave;
  const primary = hour.waves?.primary_wave;
  return num(total?.peak_direction_from_deg) ?? num(total?.mean_direction_from_deg)
    ?? num(primary?.peak_direction_from_deg) ?? num(primary?.mean_direction_from_deg) ?? num(hour.swell_dir);
}

/** The primary swell partition: height, period and direction, or null when
 *  the model carries none (null stays null — never filled from the total). */
export function primarySwell(hour: WaveHour): { heightM: number; periodS: number | null; fromDeg: number | null } | null {
  const swell = hour?.waves?.primary_swell;
  const heightM = num(swell?.significant_height_m);
  if (heightM == null) return null;
  return {
    heightM,
    periodS: num(swell?.peak_period_s) ?? num(swell?.mean_period_s),
    fromDeg: num(swell?.peak_direction_from_deg) ?? num(swell?.mean_direction_from_deg),
  };
}
