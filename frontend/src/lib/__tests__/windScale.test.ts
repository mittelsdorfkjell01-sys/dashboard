import { describe, it, expect } from "vitest";
import { windColor, WIND_BINS } from "../windScale";

describe("windColor", () => {
  it("returns the first bin at the lower edge", () => {
    expect(windColor(0)).toBe("#A9B7C2");
  });

  it("stays in the 10–15 bin just under its upper edge", () => {
    expect(windColor(14.9)).toBe("#3F7F9B");
  });

  it("crosses into the 15–20 bin exactly at 15 (green)", () => {
    expect(windColor(15)).toBe("#4A8159");
  });

  it("matches green at 17 kt", () => {
    expect(windColor(17)).toBe("#4A8159");
  });

  it("matches orange in the 25–30 bin", () => {
    expect(windColor(27)).toBe("#E0823C");
  });

  it("falls into the open-ended top bin at 40", () => {
    expect(windColor(40)).toBe("#6E2620");
  });

  it("stays in the top bin far above 40", () => {
    expect(windColor(999)).toBe("#6E2620");
  });

  it("treats null and undefined as no-data", () => {
    expect(windColor(null)).toBe("#E6E1DA");
    expect(windColor(undefined)).toBe("#E6E1DA");
  });

  it("has nine contiguous, non-overlapping bins", () => {
    expect(WIND_BINS).toHaveLength(9);
    WIND_BINS.slice(1).forEach((bin, i) => {
      expect(bin.min).toBe(WIND_BINS[i].max);
    });
  });
});
