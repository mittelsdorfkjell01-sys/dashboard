import { describe, expect, it } from "vitest";
import { FIELD_LAYER_STYLES, layerColor, layerOpacity } from "./fieldColor";

describe("weather field colours", () => {
  it("keeps the blue-green-yellow wind scale above the calm end", () => {
    expect(layerColor("wind", 10)).toEqual([72, 169, 210]);
    expect(layerColor("wind", 20)).toEqual([68, 181, 105]);
    expect(layerColor("wind", 30)).toEqual([202, 184, 57]);
    expect(layerOpacity("wind", 40)).toBe(150);
  });

  it("covers land as much as water, with calm drawn lighter than a gale", () => {
    // The air does not stop at the coast, so the field is never transparent.
    // The calm end is pale blue-grey at ~28% and a gale reaches ~59%
    // (2026-10-12: at 47–84%, and still at 36–69%, the land under it was
    // veiled to the point of looking blurred).
    expect(layerColor("wind", 0)).toEqual([176, 190, 214]);
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
