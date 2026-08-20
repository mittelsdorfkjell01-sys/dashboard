import { describe, expect, it } from "vitest";
import { clusterRadiusForZoom, parsePublicMapUrl, PUBLIC_MAP_LAYER_RULES, PUBLIC_MAP_PALETTE, publicMapSearch, sortViewportSpots, spotCountLabel } from "../publicMap";
import type { Spot } from "../types";

const spot = (id: string, name: string, coords: [number, number]): Spot => ({ id, name, coords, region: "", wind: 0, favorite: false, tags: [], image: "" });

describe("public map state and hierarchy", () => {
  it("accepts a shareable valid state and rejects unsafe values", () => {
    expect(parsePublicMapUrl("?lat=36.01&lon=-5.61&z=8.5&spot=a")).toEqual({ center: [-5.61, 36.01], zoom: 8.5, spot: "a" });
    expect(parsePublicMapUrl("?lat=999&lon=x&z=99")).toBeNull();
  });

  it("serializes map state without dropping unrelated query values", () => {
    expect(publicMapSearch([8, 40], 6, "a", "?campaign=summer")).toContain("campaign=summer");
    expect(publicMapSearch([8, 40], 6, "a")).toContain("spot=a");
  });

  it("implements the requested cluster radii", () => {
    expect([3, 6, 8, 10, 11].map(clusterRadiusForZoom)).toEqual([64, 52, 42, 32, 3]);
  });

  it("defines controlled label stages and distinct palettes", () => {
    expect(PUBLIC_MAP_LAYER_RULES.country).toEqual({ minzoom: 2.8, maxzoom: 7 });
    expect(PUBLIC_MAP_LAYER_RULES.state.minzoom).toBe(4.5);
    expect(PUBLIC_MAP_LAYER_RULES.village.minzoom).toBe(10);
    expect(PUBLIC_MAP_LAYER_RULES.hamlet.minzoom).toBe(12);
    expect(PUBLIC_MAP_LAYER_RULES.localPoi).toBe(14);
    expect(PUBLIC_MAP_LAYER_RULES.buildings).toBe(15);
    expect(PUBLIC_MAP_PALETTE.light.water).not.toBe(PUBLIC_MAP_PALETTE.dark.water);
  });
});

describe("public map rail", () => {
  it("keeps selection first and otherwise sorts stably by center distance", () => {
    const spots = [spot("far", "Zulu", [2, 2]), spot("near", "Alpha", [0.1, 0.1]), spot("active", "Beta", [3, 3])];
    expect(sortViewportSpots(spots, [0, 0], "active").map((entry) => entry.id)).toEqual(["active", "near", "far"]);
  });

  it("uses correct singular and plural copy", () => {
    expect(spotCountLabel(1)).toBe("1 Spot im Kartenausschnitt");
    expect(spotCountLabel(12)).toBe("12 Spots im Kartenausschnitt");
  });
});
