import { describe, expect, it, vi } from "vitest";
import {
  applyPublicSpotTheme,
  ensurePublicSpotLayers,
  parsePublicMapUrl,
  PUBLIC_MAP_LAYER_RULES,
  PUBLIC_MAP_PALETTE,
  PUBLIC_MAP_STYLE_URL,
  PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
  PUBLIC_SPOT_CLUSTER_RADIUS,
  PUBLIC_SPOT_LAYER_IDS,
  PUBLIC_SPOT_SOURCE_ID,
  publicMapSearch,
  setPublicClusterHover,
  setPublicSpotSelection,
  sortViewportSpots,
  spotCountLabel,
  spotsToGeoJson,
} from "../publicMap";
import type { Spot } from "../types";

const spot = (id: string, name: string, coords: [number, number]): Spot => ({ id, name, coords, region: "", wind: 0, favorite: false, tags: [], image: "" });

/** A minimal fake of the MapLibre GL `Map` surface `publicMap.ts` touches —
 *  enough to exercise `ensurePublicSpotLayers`/`applyPublicSpotTheme` without
 *  a real WebGL context, and to assert on the exact source/layer config it
 *  builds (not just an isolated helper). */
function fakeMap() {
  const sources = new Map<string, any>();
  const layers = new Map<string, any>();
  return {
    _sources: sources,
    _layers: layers,
    getSource: (id: string) => sources.get(id),
    addSource: (id: string, spec: any) => sources.set(id, spec),
    getLayer: (id: string) => layers.get(id),
    addLayer: (spec: any) => layers.set(spec.id, spec),
    setFilter: vi.fn((id: string, filter: unknown) => { const l = layers.get(id); if (l) l.filter = filter; }),
    setPaintProperty: vi.fn((id: string, prop: string, value: unknown) => { const l = layers.get(id); if (l) l.paint = { ...l.paint, [prop]: value }; }),
    setLayoutProperty: vi.fn(),
    setLayerZoomRange: vi.fn(),
    getStyle: () => ({ layers: [] }),
    getZoom: () => 3,
  } as any;
}

describe("public map state and hierarchy", () => {
  it("accepts a shareable valid state and rejects unsafe values", () => {
    expect(parsePublicMapUrl("?lat=36.01&lon=-5.61&z=8.5&spot=a")).toEqual({ center: [-5.61, 36.01], zoom: 8.5, spot: "a" });
    expect(parsePublicMapUrl("?lat=999&lon=x&z=99")).toBeNull();
  });

  it("serializes map state without dropping unrelated query values", () => {
    expect(publicMapSearch([8, 40], 6, "a", "?campaign=summer")).toContain("campaign=summer");
    expect(publicMapSearch([8, 40], 6, "a")).toContain("spot=a");
  });

  it("defines an earlier, coastal-atlas label hierarchy than a generic street map", () => {
    expect(PUBLIC_MAP_LAYER_RULES.country.minzoom).toBe(2.5);
    expect(PUBLIC_MAP_LAYER_RULES.state.minzoom).toBe(4.5);
    expect(PUBLIC_MAP_LAYER_RULES.majorCity.minzoom).toBe(5.5);
    expect(PUBLIC_MAP_LAYER_RULES.city.minzoom).toBe(8);
    expect(PUBLIC_MAP_LAYER_RULES.town.minzoom).toBe(10.5);
    expect(PUBLIC_MAP_LAYER_RULES.village.minzoom).toBe(10.5);
    expect(PUBLIC_MAP_LAYER_RULES.hamlet.minzoom).toBe(12.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.major).toBe(8.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.secondary).toBe(11.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.minor).toBe(13);
    expect(PUBLIC_MAP_LAYER_RULES.buildings).toBe(15.5);
    // Spot names must appear at the local/regional zoom, not street level.
    expect(PUBLIC_MAP_LAYER_RULES.spotNames.minzoom).toBe(11);
  });

  it("defines two genuinely distinct palettes, not a filtered copy", () => {
    expect(PUBLIC_MAP_PALETTE.light.water).toBe("#D8E8E9");
    expect(PUBLIC_MAP_PALETTE.dark.water).toBe("#0C2E34");
    expect(PUBLIC_MAP_PALETTE.light.spot).toBe("#126B70");
    expect(PUBLIC_MAP_PALETTE.dark.spot).toBe("#6AC2C0");
    expect(PUBLIC_MAP_PALETTE.light.selection).toBe("#F06F4F");
    expect(PUBLIC_MAP_PALETTE.dark.selection).toBe("#FF8160");
    expect(PUBLIC_MAP_PALETTE.light.water).not.toBe(PUBLIC_MAP_PALETTE.dark.water);
  });

  it("uses the verified keyless CARTO Voyager vector style for both patched themes", () => {
    expect(PUBLIC_MAP_STYLE_URL.light).toBe("https://tiles.basemaps.cartocdn.com/gl/voyager-gl-style/style.json");
    expect(PUBLIC_MAP_STYLE_URL.dark).toBe(PUBLIC_MAP_STYLE_URL.light);
  });
});

describe("cluster source configuration", () => {
  it("wires the real GeoJSON source to a fixed radius and a max zoom that unclusters around zoom 10", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    const source = map.getSource(PUBLIC_SPOT_SOURCE_ID);
    expect(source.cluster).toBe(true);
    expect(source.clusterRadius).toBe(PUBLIC_SPOT_CLUSTER_RADIUS);
    expect(source.clusterRadius).toBe(44);
    expect(source.clusterMaxZoom).toBe(PUBLIC_SPOT_CLUSTER_MAX_ZOOM);
    expect(source.clusterMaxZoom).toBeLessThan(10);
  });

  it("does not recreate the source or duplicate layers on a second call (style/theme restoration)", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    const firstSource = map.getSource(PUBLIC_SPOT_SOURCE_ID);
    const layerCountBefore = map._layers.size;
    ensurePublicSpotLayers(map);
    expect(map.getSource(PUBLIC_SPOT_SOURCE_ID)).toBe(firstSource);
    expect(map._layers.size).toBe(layerCountBefore);
  });

  it("stages cluster circle radii as small/medium/large, capped well under 42px", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    const step = map.getLayer(PUBLIC_SPOT_LAYER_IDS.clusters).paint["circle-radius"];
    expect(step[0]).toBe("step");
    const [, , base, , mid, , large] = step;
    expect(base).toBeLessThan(mid);
    expect(mid).toBeLessThan(large);
    expect(large * 2).toBeLessThanOrEqual(42);
  });
});

describe("marker geometry", () => {
  it("keeps the normal spot marker compact (≈18–20px diameter)", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    const radiusExpr = map.getLayer(PUBLIC_SPOT_LAYER_IDS.points).paint["circle-radius"];
    // ["interpolate", ["linear"], ["zoom"], z1, r1, z2, r2, ...] — radii sit
    // at the odd positions from index 4 on; every one stays within 16–20px.
    const radii: number[] = [];
    for (let i = 4; i < radiusExpr.length; i += 2) radii.push(radiusExpr[i]);
    expect(radii.length).toBeGreaterThan(0);
    for (const r of radii) expect(r * 2).toBeGreaterThanOrEqual(16);
    for (const r of radii) expect(r * 2).toBeLessThanOrEqual(20);
  });

  it("enlarges hover/focus and selected markers only modestly, with a coral accent", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    const hover = map.getLayer(PUBLIC_SPOT_LAYER_IDS.hover).paint;
    const selected = map.getLayer(PUBLIC_SPOT_LAYER_IDS.selected).paint;
    expect(hover["circle-radius"] * 2).toBeLessThanOrEqual(24);
    expect(selected["circle-radius"] * 2).toBeLessThanOrEqual(24);
    expect(hover["circle-stroke-color"]).toBe("#F06F4F");
    expect(selected["circle-stroke-color"]).toBe("#F06F4F");
  });

  it("gates the collision-driven name layer at the local/regional zoom, not street level", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    const names = map.getLayer(PUBLIC_SPOT_LAYER_IDS.names);
    expect(names.minzoom).toBe(11);
    expect(names.layout["text-allow-overlap"]).toBe(false);
  });

  it("exposes exactly the documented layer ids (shadow/clusters/hover/selection/names stack)", () => {
    expect(Object.values(PUBLIC_SPOT_LAYER_IDS)).toHaveLength(9);
    expect(PUBLIC_SPOT_SOURCE_ID).toBe("public-spots");
  });
});

describe("selection and theme restoration", () => {
  it("filters hover/selected layers by feature id, defaulting to an impossible match", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    setPublicSpotSelection(map, "hover-1", "sel-1");
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.hover).filter).toEqual(["==", ["get", "spotId"], "hover-1"]);
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.selected).filter).toEqual(["==", ["get", "spotId"], "sel-1"]);
    setPublicSpotSelection(map, undefined, undefined);
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.hover).filter).toEqual(["==", ["get", "spotId"], ""]);
  });

  it("filters the cluster hover ring by cluster_id, off by default", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    setPublicClusterHover(map, 42);
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.clusterHover).filter).toEqual(["==", ["get", "cluster_id"], 42]);
    setPublicClusterHover(map, undefined);
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.clusterHover).filter).toEqual(["==", ["get", "cluster_id"], -1]);
  });

  it("repaints spot/cluster/name colors independently per theme (not a shared filter)", () => {
    const map = fakeMap();
    ensurePublicSpotLayers(map);
    applyPublicSpotTheme(map, "light");
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.points).paint["circle-color"]).toBe(PUBLIC_MAP_PALETTE.light.spot);
    applyPublicSpotTheme(map, "dark");
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.points).paint["circle-color"]).toBe(PUBLIC_MAP_PALETTE.dark.spot);
    expect(map.getLayer(PUBLIC_SPOT_LAYER_IDS.points).paint["circle-color"]).not.toBe(PUBLIC_MAP_PALETTE.light.spot);
  });

  it("tolerates an optional CARTO layer being absent from the loaded style", () => {
    const map = fakeMap();
    // No ensurePublicSpotLayers() call — every layer id is missing.
    expect(() => applyPublicSpotTheme(map, "dark")).not.toThrow();
    expect(() => setPublicSpotSelection(map, "x", "y")).not.toThrow();
    expect(() => setPublicClusterHover(map, 1)).not.toThrow();
  });
});

describe("public spot GeoJSON", () => {
  it("uses stable ids and lng/lat coordinates without admin fields", () => {
    const input = { ...spot("spot-1", "Almanarre", [43.08, 6.15]), slug: "almanarre", regionName: "Provence", regionCountry: "FR", typicalWindKt: 22, description: "not exported" };
    const data = spotsToGeoJson([input]);
    expect(data.features[0]).toMatchObject({ id: "spot-1", geometry: { coordinates: [6.15, 43.08] }, properties: { spotId: "spot-1", slug: "almanarre", name: "Almanarre", region: "Provence", country: "FR", windKt: 22 } });
    expect(data.features[0].properties).not.toHaveProperty("description");
  });

  it("omits entries without public coordinates", () => {
    const withoutCoords = { ...spot("draft", "Ohne Lage", [0, 0]), coords: undefined };
    expect(spotsToGeoJson([withoutCoords]).features).toHaveLength(0);
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
