import { describe, expect, it } from "vitest";
import {
  adoptLabel,
  aspectRatio,
  focalFromPoint,
  isUsable,
  masonryColumns,
  nextIndex,
  tabLabel,
  tabOrder,
  tileBadges,
  type MediaItem,
  type TabState,
} from "../mediaPicker";

function item(overrides: Partial<MediaItem> = {}): MediaItem {
  return {
    provider: "unsplash",
    external_id: "abc",
    thumb_url: "https://cdn/thumb.jpg",
    preview_url: "https://cdn/preview.jpg",
    full_url: "https://cdn/full.jpg",
    width: 6000,
    height: 4000,
    license: {
      name: "Unsplash License",
      url: "https://unsplash.com/license",
      commercial: true,
      modification: true,
    },
    credit: { name: "Sam Rivera", url: "https://unsplash.com/@sam" },
    source_page: "https://unsplash.com/photos/abc",
    delivery: "hotlinked",
    geo_verified: false,
    hero_eligible: true,
    gallery_eligible: true,
    used_by: [],
    unsplash_download_location: null,
    ...overrides,
  };
}

describe("tab order", () => {
  it("leads with the source that fits the entity", () => {
    // Spots want an action photo; regions want the actual place, and that is
    // what geotagged Commons material is.
    expect(tabOrder("spot")).toEqual([
      "nearby",
      "unsplash",
      "pexels",
      "wikimedia",
      "openverse",
    ]);
    expect(tabOrder("region")).toEqual([
      "nearby",
      "wikimedia",
      "unsplash",
      "pexels",
      "openverse",
    ]);
  });

  it("offers the same sources to both, only differently ordered", () => {
    expect([...tabOrder("spot")].sort()).toEqual([...tabOrder("region")].sort());
  });
});

describe("eligibility", () => {
  it("lets the admin pick any tile — size becomes an advisory, not a gate", () => {
    const small = item({ hero_eligible: false, gallery_eligible: true });
    expect(isUsable(small, "hero")).toBe(true);
    expect(isUsable(small, "gallery")).toBe(true);
  });
});

describe("tile badges", () => {
  it("states why a tile is dimmed instead of leaving it to be guessed", () => {
    const badges = tileBadges(
      item({ hero_eligible: false, gallery_eligible: true }),
      "hero"
    );
    expect(badges.map((b) => b.label)).toContain("nur Galerie");
  });

  it("does not cry 'gallery only' when the gallery mode is active", () => {
    const badges = tileBadges(
      item({ hero_eligible: false, gallery_eligible: true }),
      "gallery"
    );
    expect(badges.map((b) => b.label)).not.toContain("nur Galerie");
  });

  it("names where a photo is already used", () => {
    const badges = tileBadges(
      item({
        used_by: [
          { entity_type: "spot", entity_id: "1", name: "Los Lances", role: "hero" },
        ],
      }),
      "hero"
    );
    expect(badges.map((b) => b.label)).toContain("bereits genutzt bei Los Lances");
  });

  it("counts instead of listing when a photo is used several times", () => {
    const badges = tileBadges(
      item({
        used_by: [
          { entity_type: "spot", entity_id: "1", name: "A", role: "hero" },
          { entity_type: "spot", entity_id: "2", name: "B", role: "gallery" },
        ],
      }),
      "hero"
    );
    const badge = badges.find((b) => b.label.startsWith("bereits genutzt"));
    expect(badge?.label).toBe("bereits genutzt (2×)");
    expect(badge?.title).toBe("A, B");
  });

  it("marks an unverified location and stays quiet about a verified one", () => {
    expect(tileBadges(item({ geo_verified: false }), "hero").map((b) => b.label)).toContain(
      "Ortsbezug ungeprüft"
    );
    expect(tileBadges(item({ geo_verified: true }), "hero").map((b) => b.label)).not.toContain(
      "Ortsbezug ungeprüft"
    );
  });

  it("always shows resolution and license", () => {
    const labels = tileBadges(item(), "hero").map((b) => b.label);
    expect(labels).toContain("6000×4000");
    expect(labels).toContain("Unsplash License");
  });
});

describe("focal point", () => {
  const rect = { left: 100, top: 50, width: 400, height: 200 };

  it("maps a click to object-position percentages", () => {
    expect(focalFromPoint(rect, 300, 150)).toEqual({ x: 50, y: 50 });
    expect(focalFromPoint(rect, 100, 50)).toEqual({ x: 0, y: 0 });
    expect(focalFromPoint(rect, 500, 250)).toEqual({ x: 100, y: 100 });
  });

  it("clamps clicks that land outside the frame", () => {
    expect(focalFromPoint(rect, -500, -500)).toEqual({ x: 0, y: 0 });
    expect(focalFromPoint(rect, 9999, 9999)).toEqual({ x: 100, y: 100 });
  });

  it("falls back to centre for a zero-sized frame", () => {
    expect(focalFromPoint({ left: 0, top: 0, width: 0, height: 0 }, 10, 10)).toEqual({
      x: 50,
      y: 50,
    });
  });
});

describe("masonry", () => {
  it("fills the shortest column first so no column runs long", () => {
    const tall = item({ external_id: "tall", width: 1000, height: 2000 }); // ratio 2.0
    const wide = item({ external_id: "wide", width: 2000, height: 1000 }); // ratio 0.5
    const columns = masonryColumns([tall, wide, wide, wide], 2);
    // One tall tile is worth four wide ones, so it holds a column on its own
    // while the rest stack beside it. Round-robin would have alternated and
    // left the first column visibly longer.
    expect(columns[0].map((i) => i.external_id)).toEqual(["tall"]);
    expect(columns[1].map((i) => i.external_id)).toEqual(["wide", "wide", "wide"]);
  });

  it("never produces fewer than one column", () => {
    expect(masonryColumns([item()], 0)).toHaveLength(1);
  });

  it("keeps every item", () => {
    const items = Array.from({ length: 11 }, (_, i) =>
      item({ external_id: String(i) })
    );
    const flat = masonryColumns(items, 3).flat();
    expect(flat).toHaveLength(11);
    expect(new Set(flat.map((i) => i.external_id)).size).toBe(11);
  });
});

describe("aspect ratio", () => {
  it("reserves the real box so lazy images cause no layout shift", () => {
    expect(aspectRatio(item({ width: 6000, height: 4000 }))).toBe("6000 / 4000");
  });

  it("falls back when the provider reports no dimensions", () => {
    expect(aspectRatio(item({ width: null, height: null }))).toBe("3 / 2");
  });
});

describe("tab labels", () => {
  const base: TabState = { status: "ok", items: [], total: 24, loading: false };

  it("shows the post-filter count so it is clear where searching pays off", () => {
    expect(tabLabel("unsplash", base)).toBe("Unsplash (24)");
  });

  it("distinguishes unconfigured, throttled and broken sources", () => {
    expect(tabLabel("pexels", { ...base, status: "disabled" })).toBe("Pexels (—)");
    expect(tabLabel("unsplash", { ...base, status: "budget_exhausted" })).toBe(
      "Unsplash (⏸)"
    );
    expect(tabLabel("wikimedia", { ...base, status: "error" })).toBe("Wikimedia (!)");
  });

  it("shows no count while loading", () => {
    expect(tabLabel("nearby", { ...base, loading: true })).toBe("Vor Ort");
  });
});

describe("keyboard navigation", () => {
  it("moves through the flat result order, not down a visual column", () => {
    expect(nextIndex(0, "ArrowRight", 10, 3)).toBe(1);
    expect(nextIndex(5, "ArrowLeft", 10, 3)).toBe(4);
  });

  it("steps a row at a time for up/down", () => {
    expect(nextIndex(0, "ArrowDown", 10, 3)).toBe(3);
    expect(nextIndex(6, "ArrowUp", 10, 3)).toBe(3);
  });

  it("stops at the ends instead of wrapping", () => {
    expect(nextIndex(0, "ArrowLeft", 10, 3)).toBe(0);
    expect(nextIndex(9, "ArrowRight", 10, 3)).toBe(9);
    expect(nextIndex(9, "ArrowDown", 10, 3)).toBe(9);
  });

  it("jumps to the ends with Home/End", () => {
    expect(nextIndex(5, "Home", 10, 3)).toBe(0);
    expect(nextIndex(5, "End", 10, 3)).toBe(9);
  });

  it("returns -1 for an empty grid", () => {
    expect(nextIndex(0, "ArrowRight", 0, 3)).toBe(-1);
  });

  it("ignores unrelated keys", () => {
    expect(nextIndex(4, "a", 10, 3)).toBe(4);
  });
});

describe("adopt label", () => {
  it("names the action for the active mode", () => {
    expect(adoptLabel("hero")).toBe("Als Hero übernehmen");
    expect(adoptLabel("gallery")).toBe("Zur Galerie hinzufügen");
  });
});
