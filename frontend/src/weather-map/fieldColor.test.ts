import { describe, expect, it } from "vitest";
import { FIELD_LAYER_STYLES, layerColor, layerOpacity } from "./fieldColor";
import { WIND_BINS, windColor } from "../lib/windScale";

/** "#A9B7C2" → [169, 183, 194] — what the chart primitives draw. */
const rgb = (hex: string) => {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
};

describe("weather field colours", () => {
  it("paints wind in the house wind scale, so the field agrees with the bars", () => {
    // One scale for the whole product (lib/windScale.ts): the colour the field
    // gives a speed is the colour a forecast bar gives the same speed, and the
    // colour the legend names. Before 2026-11-16 the field ran a second,
    // continuous ramp of its own and 18 kn was two different colours on one
    // screen.
    for (const speed of [0, 4, 7, 12, 18, 22, 27, 33, 60]) {
      expect(layerColor("wind", speed)).toEqual(rgb(windColor(speed)));
      expect(layerColor("gust", speed)).toEqual(rgb(windColor(speed)));
    }
  });

  it("steps between bins instead of interpolating", () => {
    // Discrete by design — the steps on the map are exactly the steps the
    // legend names, so a boundary is a boundary and not a gradient.
    expect(layerColor("wind", 15)).toEqual(layerColor("wind", 19.9));
    expect(layerColor("wind", 19.9)).not.toEqual(layerColor("wind", 20));
    expect(layerColor("wind", 99)).toEqual(rgb(WIND_BINS[WIND_BINS.length - 1].hex));
  });

  it("covers land as much as water, with calm drawn lighter than a gale", () => {
    // The air does not stop at the coast, so the field is never transparent.
    // The calm end is drawn at ~28% and a gale reaches ~59% (2026-10-12: at
    // 47–84%, and still at 36–69%, the land under it was veiled to the point
    // of looking blurred).
    expect(layerColor("wind", 0)).toEqual(rgb(WIND_BINS[0].hex));
    expect(layerOpacity("wind", 0)).toBe(72);
    expect(layerOpacity("wind", 0)).toBeLessThan(layerOpacity("wind", 20));
    expect(layerOpacity("wind", 40)).toBe(150);
  });

  it("keeps dry and clear areas transparent", () => {
    expect(layerOpacity("precipitation", 0)).toBe(0);
    expect(layerOpacity("clouds", 0)).toBe(0);
    expect(layerOpacity("precipitation", 10)).toBeGreaterThan(100);
    expect(layerOpacity("clouds", 100)).toBe(95);
  });

  it("keeps every layer colour and opacity inside the renderable range", () => {
    for (const [layer, style] of Object.entries(FIELD_LAYER_STYLES)) {
      for (const value of style.values) {
        expect(layerColor(layer as keyof typeof FIELD_LAYER_STYLES, value).every((channel) => channel >= 0 && channel <= 255)).toBe(true);
        expect(layerOpacity(layer as keyof typeof FIELD_LAYER_STYLES, value)).toBeGreaterThanOrEqual(0);
        expect(layerOpacity(layer as keyof typeof FIELD_LAYER_STYLES, value)).toBeLessThanOrEqual(255);
      }
    }
  });
});
