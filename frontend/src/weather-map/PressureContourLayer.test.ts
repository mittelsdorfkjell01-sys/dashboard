import { describe, expect, it } from "vitest";
import { pressureContourSegments } from "./PressureContourLayer";
import type { DecodedFieldTile } from "./fieldTile";

function tile(values: number[], width = 2, height = 2): DecodedFieldTile {
  return {
    key: "pressure-test",
    header: {
      schema: "swd-field-tile-v2",
      width,
      height,
      overlap: 0,
      z: 1,
      x: 0,
      y: 0,
      valid_time: "2026-10-05T12:00:00Z",
      variables: [],
    },
    arrays: { pressure_msl: new Float32Array(values) },
  };
}

describe("pressure contours", () => {
  it("extracts standard four-hectopascal isobars", () => {
    const segments = pressureContourSegments(tile([1000, 1008, 1000, 1008]));

    expect(segments.map((segment) => segment.level)).toEqual([1004, 1008]);
    expect(segments[0].start[0]).toBeCloseTo(0.5);
    expect(segments[0].end[0]).toBeCloseTo(0.5);
  });

  it("does not bridge no-data cells", () => {
    expect(pressureContourSegments(tile([1000, Number.NaN, 1008, 1008]))).toEqual([]);
  });

  it("returns no contours when pressure is absent", () => {
    const missing = tile([1000, 1008, 1000, 1008]);
    missing.arrays = {};

    expect(pressureContourSegments(missing)).toEqual([]);
  });
});
