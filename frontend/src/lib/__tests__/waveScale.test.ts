import { describe, it, expect } from "vitest";
import { waveColor, WAVE_BINS } from "../waveScale";

describe("waveColor", () => {
  it("returns the first bin at the lower edge", () => {
    expect(waveColor(0)).toBe("#C9DDE2");
  });

  it("stays in the 0.6–1.0 bin just under its upper edge", () => {
    expect(waveColor(0.99)).toBe("#4F93A8");
  });

  it("crosses into the 1.0–1.5 bin exactly at 1.0 (teal)", () => {
    expect(waveColor(1.0)).toBe("#1C4E63");
  });

  it("falls into the open-ended top bin at 2.5", () => {
    expect(waveColor(2.5)).toBe("#0E2438");
  });

  it("stays in the top bin far above 2.5", () => {
    expect(waveColor(50)).toBe("#0E2438");
  });

  it("treats null and undefined as no-data", () => {
    expect(waveColor(null)).toBe("#E6E1DA");
    expect(waveColor(undefined)).toBe("#E6E1DA");
  });

  it("has six contiguous, non-overlapping bins", () => {
    expect(WAVE_BINS).toHaveLength(6);
    WAVE_BINS.slice(1).forEach((bin, i) => {
      expect(bin.min).toBe(WAVE_BINS[i].max);
    });
  });

  it("never shares a color with the wind scale (visually distinct systems)", async () => {
    const { WIND_BINS } = await import("../windScale");
    const waveHexes = new Set(WAVE_BINS.map((b) => b.hex));
    const windHexes = new Set(WIND_BINS.map((b) => b.hex));
    for (const hex of waveHexes) expect(windHexes.has(hex)).toBe(false);
  });
});
