import { describe, expect, it } from "vitest";
import type { DecodedFieldTile } from "../weather-map/fieldTile";
import { arrowLengthPx, ARROW_MAX_PX, ARROW_MIN_PX, latticeAlpha, shortestTurn, waveArrowLengthPx } from "./ArrowLayer";
import { waveAlpha, windAlpha, windRgb } from "./fieldColors";
import { WIND_BINS } from "../lib/windScale";
import { bearingOf, compassName, sampleTiles, tilesForComponent, waveReading, windReading } from "./fieldSample";

/** A 4×4 tile covering z=0 (the whole world), every array constant. */
function tile(arrays: Record<string, number>, key = "t/0/0/0"): DecodedFieldTile {
  const filled = Object.fromEntries(Object.entries(arrays).map(([name, value]) => [name, new Float32Array(16).fill(value)]));
  return { key, header: { z: 0, x: 0, y: 0, width: 4, height: 4, overlap: 0, valid_time: "2026-11-19T12:00:00Z" }, arrays: filled } as unknown as DecodedFieldTile;
}

describe("wind arrows", () => {
  it("grow with the square root of the speed inside 14–24 px", () => {
    expect(arrowLengthPx(0)).toBe(ARROW_MIN_PX);
    expect(arrowLengthPx(40)).toBe(ARROW_MAX_PX);
    expect(arrowLengthPx(80)).toBe(ARROW_MAX_PX);
    expect(arrowLengthPx(10)).toBeCloseTo(14 + 10 * 0.5);
  });

  it("always turn the shorter way round", () => {
    expect(shortestTurn(350, 10)).toBe(20);
    expect(shortestTurn(10, 350)).toBe(-20);
    expect(shortestTurn(0, 180)).toBe(180);
    expect(shortestTurn(90, 90)).toBe(0);
  });
});

describe("field sampling", () => {
  it("reads wind in knots and where it goes", () => {
    const reading = windReading(sampleTiles([tile({ wind_u: 0, wind_v: 10 })], 10, 50));
    expect(reading?.knots).toBeCloseTo(19.44, 1);
    expect(bearingOf(reading!.u, reading!.v)).toBeCloseTo(0); // blows to the north
  });

  it("returns nothing where a neighbour has no data", () => {
    expect(windReading(sampleTiles([tile({ wind_u: Number.NaN, wind_v: 1 })], 10, 50))).toBeNull();
  });

  it("reads the swell from its own height, period and from-direction", () => {
    const values = sampleTiles([tile({ wave_u: 1, wave_v: 0, total_wave_height: 1, primary_swell_height: 1.4, primary_swell_period: 11, primary_swell_direction: 270 })], 10, 50);
    const swell = waveReading(values, "swell");
    expect(swell?.height).toBeCloseTo(1.4);
    expect(swell?.period).toBe(11);
    expect(bearingOf(swell!.dx, swell!.dy)).toBeCloseTo(90); // from W → travels E
    expect(waveReading(values, "sea")).toBeNull(); // not published → never invented
  });

  it("names compass directions in German", () => {
    expect(compassName(0)).toBe("N");
    expect(compassName(135)).toBe("SO");
    expect(compassName(359)).toBe("N");
  });

  it("paints a component through the total-height array and keys blends by instant", () => {
    const base = tile({ total_wave_height: 1, primary_swell_height: 2 }, "z/0/0@blend");
    const [view] = tilesForComponent([base], "swell");
    expect(view.arrays.total_wave_height[0]).toBe(2);
    expect(view.key).toBe("z/0/0@blend#swell@2026-11-19T12:00:00Z");
    expect(tilesForComponent([base], "total")[0].key).toBe("z/0/0@blend@2026-11-19T12:00:00Z");
  });
});

describe("arrow density across zoom", () => {
  it("keeps the coarse lattice and fades the in-between points smoothly", () => {
    expect(latticeAlpha(true, 7.3)).toBe(1);
    expect(latticeAlpha(false, 7)).toBe(0);
    expect(latticeAlpha(false, 7.5)).toBeCloseTo(0.5);
    expect(latticeAlpha(false, 7.999)).toBeGreaterThan(0.99);
  });

  it("sizes wave arrows by the square root of the height", () => {
    expect(waveArrowLengthPx(0)).toBe(ARROW_MIN_PX);
    expect(waveArrowLengthPx(4)).toBe(ARROW_MAX_PX);
    expect(waveArrowLengthPx(1)).toBeCloseTo(19);
  });
});

describe("flowing field colours", () => {
  it("passes through the house bin colours at each bin's middle", () => {
    const green = WIND_BINS.find((bin) => bin.min === 15)!;
    const [r, g, b] = windRgb(17.5);
    expect(`#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`.toUpperCase()).toBe(green.hex.toUpperCase());
  });

  it("makes a bigger sea more intense, on both grounds", () => {
    expect(waveAlpha(3, false)).toBeGreaterThan(waveAlpha(0.3, false));
    expect(waveAlpha(3, true)).toBeGreaterThan(waveAlpha(0.3, true));
    expect(windAlpha(30, true)).toBeGreaterThan(windAlpha(30, false));
  });
});
