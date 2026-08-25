// Shared wave-height → color scale, the wave-mode counterpart to
// windScale.ts. Deliberately a single hue (teal) throughout — wind reads
// blue-gray → green → orange → rust as it strengthens, wave stays teal
// end-to-end so the two are never mistaken for each other at a glance.

export type WaveBin = { min: number; max: number; hex: string };

// Discrete steps, not a gradient — matches the wind scale's convention.
export const WAVE_BINS: WaveBin[] = [
  { min: 0, max: 0.3, hex: "#C9DDE2" },
  { min: 0.3, max: 0.6, hex: "#8FB9C4" },
  { min: 0.6, max: 1.0, hex: "#4F93A8" },
  { min: 1.0, max: 1.5, hex: "#1C4E63" }, // = teal
  { min: 1.5, max: 2.5, hex: "#163A52" },
  { min: 2.5, max: Infinity, hex: "#0E2438" },
];

// = the `line` token, for values with no wave data.
const NO_DATA_HEX = "#E6E1DA";

export function waveColor(meters: number | null | undefined): string {
  if (meters == null || Number.isNaN(meters)) return NO_DATA_HEX;
  const bin = WAVE_BINS.find((b) => meters >= b.min && meters < b.max);
  return (bin ?? WAVE_BINS[WAVE_BINS.length - 1]).hex;
}
