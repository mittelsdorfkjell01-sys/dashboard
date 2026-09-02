// Shared wind-speed → color scale, used by every wind chart on the spot page
// (Forecast, WindMonths, the live overlay). One source of truth so a given
// knot value always reads as the same color everywhere.

export type WindBin = { min: number; max: number; hex: string };

// Discrete steps, not a gradient — no interpolation between bins. Two steps
// (15–20 and 25–30) land exactly on green / orange; that's
// intentional, not a coincidence to "fix".
export const WIND_BINS: WindBin[] = [
  { min: 0, max: 5, hex: "#A9B7C2" },
  { min: 5, max: 10, hex: "#7C9BB6" },
  { min: 10, max: 15, hex: "#3F7F9B" },
  { min: 15, max: 20, hex: "#4A8159" }, // = green
  { min: 20, max: 25, hex: "#E3C341" },
  { min: 25, max: 30, hex: "#E0823C" }, // = orange
  { min: 30, max: 35, hex: "#C55E3C" },
  { min: 35, max: 40, hex: "#9C3E30" },
  { min: 40, max: Infinity, hex: "#6E2620" },
];

// = the `line` token, for values with no wind data.
const NO_DATA_HEX = "#E6E1DA";

export function windColor(kts: number | null | undefined): string {
  if (kts == null || Number.isNaN(kts)) return NO_DATA_HEX;
  const bin = WIND_BINS.find((b) => kts >= b.min && kts < b.max);
  return (bin ?? WIND_BINS[WIND_BINS.length - 1]).hex;
}
