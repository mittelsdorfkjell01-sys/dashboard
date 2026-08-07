import { describe, expect, it } from "vitest";
import { moveItem, removalNeedsConfirmation } from "../gallery";
import type { GalleryImage } from "../api";

function image(overrides: Partial<GalleryImage> = {}): GalleryImage {
  return {
    id: "1",
    url: "https://img/x.jpg",
    kind: "gallery",
    status: "approved",
    position: null,
    width: 2000,
    height: 1200,
    source: "unsplash",
    provider: "unsplash",
    external_id: "abc",
    delivery: "hotlinked",
    credit: "Jo",
    credit_url: null,
    license_name: "Unsplash License",
    license_url: null,
    source_url: null,
    geo_verified: false,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("moveItem", () => {
  it("moves an entry to a later position", () => {
    expect(moveItem(["a", "b", "c", "d"], 0, 2)).toEqual(["b", "c", "a", "d"]);
  });

  it("moves an entry to an earlier position", () => {
    expect(moveItem(["a", "b", "c", "d"], 3, 0)).toEqual(["d", "a", "b", "c"]);
  });

  it("is a no-op for the same index", () => {
    const items = ["a", "b", "c"];
    expect(moveItem(items, 1, 1)).toBe(items);
  });

  it("ignores an out-of-range index instead of throwing", () => {
    const items = ["a", "b"];
    expect(moveItem(items, -1, 0)).toBe(items);
    expect(moveItem(items, 0, 5)).toBe(items);
  });

  it("does not mutate the input array", () => {
    const items = ["a", "b", "c"];
    moveItem(items, 0, 2);
    expect(items).toEqual(["a", "b", "c"]);
  });
});

describe("removalNeedsConfirmation", () => {
  it("requires confirmation for a community photo", () => {
    expect(removalNeedsConfirmation(image({ provider: "community" }))).toBe(true);
    expect(removalNeedsConfirmation(image({ provider: null, source: "user_upload" }))).toBe(
      true
    );
  });

  it("does not require confirmation for stock material", () => {
    expect(removalNeedsConfirmation(image({ provider: "unsplash" }))).toBe(false);
    expect(removalNeedsConfirmation(image({ provider: "wikimedia" }))).toBe(false);
  });
});
