import { describe, expect, it } from "vitest";
import { clusterRadiusForZoom, parsePublicMapUrl, PUBLIC_MAP_LAYER_RULES, PUBLIC_MAP_PALETTE, PUBLIC_MAP_STYLE_URL, PUBLIC_SPOT_LAYER_IDS, PUBLIC_SPOT_SOURCE_ID, publicMapSearch, sortViewportSpots, spotCountLabel, spotsToGeoJson } from "../publicMap";
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
    expect(PUBLIC_MAP_LAYER_RULES.country).toEqual({ minzoom: 2.8, maxzoom: 8.5 });
    expect(PUBLIC_MAP_LAYER_RULES.capital.minzoom).toBe(3.5);
    expect(PUBLIC_MAP_LAYER_RULES.state.minzoom).toBe(9);
    expect(PUBLIC_MAP_LAYER_RULES.majorCity.minzoom).toBe(11.5);
    expect(PUBLIC_MAP_LAYER_RULES.city.minzoom).toBe(13);
    expect(PUBLIC_MAP_LAYER_RULES.village.minzoom).toBe(14.5);
    expect(PUBLIC_MAP_LAYER_RULES.hamlet.minzoom).toBe(15.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.major).toBe(14);
    expect(PUBLIC_MAP_LAYER_RULES.roads.minor).toBe(16);
    expect(PUBLIC_MAP_LAYER_RULES.localPoi).toBe(15);
    expect(PUBLIC_MAP_LAYER_RULES.buildings).toBe(16);
    expect(PUBLIC_MAP_PALETTE.light.water).not.toBe(PUBLIC_MAP_PALETTE.dark.water);
  });

  it("uses the verified keyless CARTO Voyager vector style for both patched themes", () => {
    expect(PUBLIC_MAP_STYLE_URL.light).toBe("https://tiles.basemaps.cartocdn.com/gl/voyager-gl-style/style.json");
    expect(PUBLIC_MAP_STYLE_URL.dark).toBe(PUBLIC_MAP_STYLE_URL.light);
  });
});

describe("public spot GeoJSON", () => {
  it("uses stable ids and lng/lat coordinates without admin fields", () => {
    const input = { ...spot("spot-1", "Almanarre", [43.08, 6.15]), slug: "almanarre", regionName: "Provence", regionCountry: "FR", typicalWindKt: 22, description: "not exported" };
    const data = spotsToGeoJson([input]);
    expect(data.features[0]).toMatchObject({ id: "spot-1", geometry: { coordinates: [6.15, 43.08] }, properties: { spotId: "spot-1", slug: "almanarre", name: "Almanarre", region: "Provence", country: "FR", windKt: 22 } });
    expect(data.features[0].properties).not.toHaveProperty("description");
  });

  it("omits entries without public coordinates and exposes stable source/layer ids", () => {
    const withoutCoords = { ...spot("draft", "Ohne Lage", [0, 0]), coords: undefined };
    expect(spotsToGeoJson([withoutCoords]).features).toHaveLength(0);
    expect(PUBLIC_SPOT_SOURCE_ID).toBe("public-spots");
    expect(Object.values(PUBLIC_SPOT_LAYER_IDS)).toHaveLength(7);
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
