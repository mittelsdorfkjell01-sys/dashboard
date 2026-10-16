import { describe, expect, it, vi } from "vitest";
import {
  ADVECTION_MAX_PX_PER_MS,
  ADVECTION_MIN_PX_PER_MS,
  ADVECTION_REF_MPP,
  ADVECTION_REF_PX_PER_MS,
  ARROW_SCALE_MAX_KT,
  TRAIL_SECONDS,
  advectionPxPerSecond,
  alignedGridStart,
  arrowSpacingPx,
  fadeParticleTrails,
  mercatorStretch,
  metresPerPixel,
  particleAreaPx,
  trailLengthPx,
  windArrowLength,
} from "./WindAnimationLayer";

describe("particle trail fading", () => {
  it("removes trail alpha instead of painting an opaque dark veil", () => {
    const context = {
      save: vi.fn(),
      restore: vi.fn(),
      fillRect: vi.fn(),
      globalCompositeOperation: "source-over",
      fillStyle: "",
    } as unknown as CanvasRenderingContext2D;

    fadeParticleTrails(context, 800, 600);

    expect(context.save).toHaveBeenCalledOnce();
    expect(context.fillRect).toHaveBeenCalledWith(0, 0, 800, 600);
    expect(context.globalCompositeOperation).toBe("destination-out");
    // Firm enough that long streaks cannot pile up into a white haze.
    expect(context.fillStyle).toBe("rgba(0, 0, 0, .2)");
    expect(context.restore).toHaveBeenCalledOnce();
  });
});

describe("world-aligned arrow grid", () => {
  it("moves with the projected map origin instead of staying on a viewport grid", () => {
    expect(alignedGridStart(-145, 62)).toBe(41);
    expect(alignedGridStart(-125, 62)).toBe(61);
  });
});

describe("wind arrow length", () => {
  it("spans exactly the domain the colour scale spans, 0–40 kt", () => {
    expect(windArrowLength(0)).toBe(14);
    // 40 kt = 20.58 m/s is the top colour stop and the longest arrow; it used
    // to saturate at ~25 kt, so colour and length disagreed above that.
    expect(windArrowLength(ARROW_SCALE_MAX_KT / 1.943844)).toBe(56);
    expect(windArrowLength(10)).toBe(34); // 19.4 kt, just under half the range
    expect(windArrowLength(5)).toBe(24);
  });

  it("caps extreme values without hiding invalid or negative input", () => {
    expect(windArrowLength(100)).toBe(56);
    expect(windArrowLength(-5)).toBe(14);
    expect(windArrowLength(Number.NaN)).toBe(14);
  });
});

describe("zoom-aware advection", () => {
  it("measures the ground a pixel covers", () => {
    // z8 at 50°N is the scale the animation was originally tuned at.
    expect(Math.round(metresPerPixel(8, 50))).toBe(197);
    // One zoom level in halves it.
    expect(metresPerPixel(9, 50)).toBeCloseTo(metresPerPixel(8, 50) / 2, 6);
  });

  it("keeps the tuned speed at the reference scale", () => {
    expect(advectionPxPerSecond(ADVECTION_REF_MPP)).toBeCloseTo(ADVECTION_REF_PX_PER_MS, 6);
  });

  it("speeds the field up as you zoom in, as gently as earth/leaflet-velocity", () => {
    // That implementation's step is ∝ mapArea^0.4 × pixelJacobian = (1/mpp)^0.2,
    // so four times closer to the ground is 4^0.2 = 1.32× faster, not 4×.
    expect(advectionPxPerSecond(ADVECTION_REF_MPP / 4))
      .toBeCloseTo(ADVECTION_REF_PX_PER_MS * 4 ** 0.2, 6);
    // Across the whole zoom range the band stays readable without clamping.
    const far = advectionPxPerSecond(metresPerPixel(3, 50));
    const close = advectionPxPerSecond(metresPerPixel(13, 50));
    expect(far).toBeGreaterThan(ADVECTION_MIN_PX_PER_MS);
    expect(close).toBeLessThan(ADVECTION_MAX_PX_PER_MS);
    expect(close / far).toBeCloseTo(2 ** (10 * 0.2), 4); // ten zoom levels
  });

  it("clamps the extremes and survives a missing scale", () => {
    expect(advectionPxPerSecond(5_000_000)).toBe(ADVECTION_MIN_PX_PER_MS);
    expect(advectionPxPerSecond(0.0001)).toBe(ADVECTION_MAX_PX_PER_MS);
    expect(advectionPxPerSecond(0)).toBe(ADVECTION_REF_PX_PER_MS);
  });

  it("draws the streak as the path covered in the last TRAIL_SECONDS", () => {
    // 10 m/s at the reference scale: 10 × 4.8 px/s × 1.2 s.
    expect(trailLengthPx(10, ADVECTION_REF_PX_PER_MS))
      .toBeCloseTo(10 * ADVECTION_REF_PX_PER_MS * TRAIL_SECONDS, 6);
    // Zoomed in the step is larger, so the same wind draws a longer streak.
    expect(trailLengthPx(10, ADVECTION_REF_PX_PER_MS * 1.5))
      .toBeGreaterThan(trailLengthPx(10, ADVECTION_REF_PX_PER_MS));
    // Clamped at both ends: calm air still leaves a mark, a gale does not smear.
    expect(trailLengthPx(0, ADVECTION_REF_PX_PER_MS)).toBe(9);
    expect(trailLengthPx(45, ADVECTION_MAX_PX_PER_MS)).toBe(96);
  });
});

describe("mercator stretch", () => {
  it("leaves the centre alone and corrects away from it", () => {
    expect(mercatorStretch(54, 54)).toBe(1);
    // A particle further north needs MORE pixels for the same ground speed.
    expect(mercatorStretch(66, 54)).toBeGreaterThan(1);
    expect(mercatorStretch(40, 54)).toBeLessThan(1);
    expect(mercatorStretch(60, 0)).toBeCloseTo(2, 2);
  });

  it("stays finite at the poles", () => {
    // 4× is the cap for anything the map can actually show (it stops at 85°)…
    expect(mercatorStretch(85, 54)).toBe(4);
    // …and a degenerate cosine falls back to "no correction" rather than ∞.
    expect(mercatorStretch(89.9, 54)).toBe(1);
    expect(mercatorStretch(0, 89.99)).toBe(1);
  });
});

describe("density follows the published cell", () => {
  it("keeps the base density while a cell is small on screen", () => {
    expect(particleAreaPx(36)).toBe(1050);
    expect(particleAreaPx(0)).toBe(1050);
  });

  it("thins out once one cell covers a large part of the view", () => {
    // A 300px cell may carry ~40 streaks — Mapbox's per-tile count does the
    // same thing more coarsely. Below that the base screen density wins.
    expect(particleAreaPx(300)).toBe(2250);
    expect(particleAreaPx(300)).toBeGreaterThan(particleAreaPx(150));
    expect(particleAreaPx(150)).toBe(1050);
  });

  it("widens the arrow lattice with the cell, within bounds", () => {
    expect(arrowSpacingPx(36)).toBe(62);
    expect(arrowSpacingPx(220)).toBeCloseTo(100, 6);
    expect(arrowSpacingPx(1200)).toBe(190);
  });
});
