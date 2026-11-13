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
