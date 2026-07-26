import { describe, expect, it } from "vitest";
import type { CommunityImage } from "../api";
import { aspectRatio, justifyRows } from "../justifyRows";

const img = (id: string, width: number | null, height: number | null): CommunityImage => ({
  id,
  url: `/media/${id}.jpg`,
  kind: "gallery",
  width,
  height,
  credit: null,
  created_at: "2026-01-01T00:00:00Z",
  source: "user",
  license_name: null,
  license_url: null,
  source_url: null,
});

describe("aspectRatio", () => {
  it("uses real dimensions when present", () => {
    expect(aspectRatio(img("a", 300, 200))).toBeCloseTo(1.5);
  });
  it("falls back to 3:2 when a dimension is missing or zero", () => {
    expect(aspectRatio(img("a", null, 200))).toBeCloseTo(1.5);
    expect(aspectRatio(img("a", 300, 0))).toBeCloseTo(1.5);
  });
});

describe("justifyRows", () => {
  it("returns nothing for empty input or zero width", () => {
    expect(justifyRows([], 1000, 240, 12)).toEqual([]);
    expect(justifyRows([img("a", 300, 200)], 0, 240, 12)).toEqual([]);
  });

  it("makes each full row fill the container width exactly", () => {
    const photos = Array.from({ length: 9 }, (_, i) => img(`p${i}`, 300, 200));
    const rows = justifyRows(photos, 1000, 240, 12);
    // Every row except possibly the last is "full" and should span the width.
    for (const row of rows.slice(0, -1)) {
      const total = row.reduce((sum, t) => sum + t.width, 0) + (row.length - 1) * 12;
      expect(total).toBeCloseTo(1000, 1);
    }
  });

  it("preserves each photo's aspect ratio within a row", () => {
    const rows = justifyRows([img("wide", 400, 200), img("tall", 200, 400)], 1000, 240, 12);
    for (const tile of rows.flat()) {
      const ratio = tile.width / tile.height;
      expect(ratio).toBeCloseTo(aspectRatio(tile.photo), 3);
    }
  });

  it("does not let a short trailing row grow oversized", () => {
    // One landscape photo alone would fill 1000px wide → far past target; cap it.
    const rows = justifyRows([img("solo", 300, 200)], 1000, 240, 12);
    const [tile] = rows[0];
    expect(tile.height).toBeLessThanOrEqual(240 * 1.5 + 0.001);
  });
});
