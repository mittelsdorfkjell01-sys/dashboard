import { describe, expect, it, vi } from "vitest";
import type { StyleSpecification } from "maplibre-gl";
import {
  buildPublicMapStyle,
  parsePublicMapUrl,
  PUBLIC_MAP_LAYER_RULES,
  PUBLIC_MAP_PALETTE,
  PUBLIC_MAP_STYLE_URL,
  PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
  PUBLIC_SPOT_CLUSTER_RADIUS,
  PUBLIC_SPOT_LAYER_IDS,
  PUBLIC_SPOT_SOURCE_ID,
  publicMapSearch,
  publicSpotLayers,
  publicSpotSource,
  setPublicClusterHover,
  setPublicSpotMode,
  setPublicSpotSelection,
  sortViewportSpots,
  spotColorExpression,
  spotCountLabel,
  spotsToGeoJson,
} from "../publicMap";
import type { Spot } from "../types";

const spot = (id: string, name: string, coords: [number, number]): Spot => ({ id, name, coords, region: "", wind: 0, favorite: false, tags: [], image: "" });

/** A minimal-but-real CARTO Voyager-shaped style document, standing in for
 *  the actual fetched JSON. Layer ids match real ones `buildPublicMapStyle`
 *  targets, so the transform's behavior against the genuine document shape
 *  is exercised, not just against an isolated helper. */
function fakeBaseStyle(): StyleSpecification {
  return {
    version: 8,
    sources: { openmaptiles: { type: "vector", url: "https://example.test/tiles.json" } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#000000" } },
      { id: "water", type: "fill", source: "openmaptiles", "source-layer": "water", paint: { "fill-color": "#000000" } },
      { id: "water_shadow", type: "fill", source: "openmaptiles", "source-layer": "water", paint: { "fill-color": "#000000" } },
      { id: "landcover", type: "fill", source: "openmaptiles", "source-layer": "landcover", paint: { "fill-color": "#000000" } },
      { id: "road_pri_fill_noramp", type: "line", source: "openmaptiles", "source-layer": "transportation", paint: { "line-color": "#000000" } },
      { id: "road_minor_fill", type: "line", source: "openmaptiles", "source-layer": "transportation", paint: { "line-color": "#000000" } },
      { id: "place_country_1", type: "symbol", source: "openmaptiles", "source-layer": "place", paint: { "text-color": "#000000" }, layout: { "text-field": "{name}" } },
      { id: "place_capital_dot_z7", type: "symbol", source: "openmaptiles", "source-layer": "place", paint: {}, layout: {} },
      { id: "poi_stadium", type: "symbol", source: "openmaptiles", "source-layer": "poi", paint: {}, layout: {} },
      { id: "housenumber", type: "symbol", source: "openmaptiles", "source-layer": "housenumber", paint: {}, layout: {} },
    ] as StyleSpecification["layers"],
  } as StyleSpecification;
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
    // Country/state names deliberately stay off the initial world overview —
    // they only appear once zoomed in well past a "where in the world" view
    // (2026-08-23 feedback), unlike the rest of the (earlier-onset) hierarchy.
    expect(PUBLIC_MAP_LAYER_RULES.country.minzoom).toBe(7);
    expect(PUBLIC_MAP_LAYER_RULES.state.minzoom).toBe(8);
    expect(PUBLIC_MAP_LAYER_RULES.majorCity.minzoom).toBe(5.5);
    expect(PUBLIC_MAP_LAYER_RULES.city.minzoom).toBe(8);
    expect(PUBLIC_MAP_LAYER_RULES.town.minzoom).toBe(10.5);
    expect(PUBLIC_MAP_LAYER_RULES.village.minzoom).toBe(10.5);
    expect(PUBLIC_MAP_LAYER_RULES.hamlet.minzoom).toBe(12.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.major).toBe(8.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.secondary).toBe(11.5);
    expect(PUBLIC_MAP_LAYER_RULES.roads.minor).toBe(13);
    expect(PUBLIC_MAP_LAYER_RULES.buildings).toBe(15.5);
    expect(PUBLIC_MAP_LAYER_RULES.spotNames.minzoom).toBe(11);
  });

  it("defines two genuinely distinct palettes, not a filtered copy", () => {
    expect(PUBLIC_MAP_PALETTE.light.spot).toBe("#126B70");
    expect(PUBLIC_MAP_PALETTE.dark.spot).toBe("#6AC2C0");
    expect(PUBLIC_MAP_PALETTE.light.selection).toBe("#F06F4F");
    expect(PUBLIC_MAP_PALETTE.dark.selection).toBe("#FF8160");
    expect(PUBLIC_MAP_PALETTE.light.water).not.toBe(PUBLIC_MAP_PALETTE.dark.water);
  });

  it("uses a bright, clearly-blue light water and a lightened land tone (2026-08-22 feedback)", () => {
    // Sanity-checked as HSL rather than pinning exact hex: "too dark" is a
    // brightness complaint, so the regression test should catch a future
    // value sliding back down, not just a literal string match.
    const toRgb = (hex: string) => [0, 2, 4].map((i) => parseInt(hex.slice(1 + i, 3 + i), 16));
    const luminance = ([r, g, b]: number[]) => (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    const [wr, wg, wb] = toRgb(PUBLIC_MAP_PALETTE.light.water);
    expect(luminance([wr, wg, wb])).toBeGreaterThan(0.75); // bright, not muted
    expect(wb).toBeGreaterThan(wr); // reads as blue, not teal/grey
    expect(luminance(toRgb(PUBLIC_MAP_PALETTE.light.land))).toBeGreaterThan(0.9);
  });

  it("uses the verified keyless CARTO Voyager vector style for both patched themes", () => {
    expect(PUBLIC_MAP_STYLE_URL.light).toBe("https://tiles.basemaps.cartocdn.com/gl/voyager-gl-style/style.json");
    expect(PUBLIC_MAP_STYLE_URL.dark).toBe(PUBLIC_MAP_STYLE_URL.light);
  });
});

describe("cluster source configuration", () => {
  it("uses a fixed radius and a max zoom that unclusters around zoom 10", () => {
    const source = publicSpotSource();
    expect(source.cluster).toBe(true);
    expect(source.clusterRadius).toBe(PUBLIC_SPOT_CLUSTER_RADIUS);
    expect(source.clusterRadius).toBe(44);
    expect(source.clusterMaxZoom).toBe(PUBLIC_SPOT_CLUSTER_MAX_ZOOM);
    expect(source.clusterMaxZoom).toBeLessThan(10);
  });

  it("stages cluster circle radii as small/medium/large, capped well under 42px", () => {
    const clusters = publicSpotLayers("light").find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.clusters)!;
    const step = (clusters.paint as any)["circle-radius"];
    expect(step[0]).toBe("step");
    const [, , base, , mid, , large] = step;
    expect(base).toBeLessThan(mid);
    expect(mid).toBeLessThan(large);
    expect(large * 2).toBeLessThanOrEqual(42);
  });
});

describe("marker geometry", () => {
  it("keeps the normal spot marker compact (≈16–20px diameter)", () => {
    const points = publicSpotLayers("light").find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.points)!;
    const radiusExpr = (points.paint as any)["circle-radius"];
    const radii: number[] = [];
    for (let i = 4; i < radiusExpr.length; i += 2) radii.push(radiusExpr[i]);
    expect(radii.length).toBeGreaterThan(0);
    for (const r of radii) expect(r * 2).toBeGreaterThanOrEqual(16);
    for (const r of radii) expect(r * 2).toBeLessThanOrEqual(20);
  });

  it("enlarges hover/focus and selected markers only modestly, with a coral accent", () => {
    const layers = publicSpotLayers("light");
    const hover = layers.find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.hover)!.paint as any;
    const selected = layers.find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.selected)!.paint as any;
    expect(hover["circle-radius"] * 2).toBeLessThanOrEqual(24);
    expect(selected["circle-radius"] * 2).toBeLessThanOrEqual(24);
    expect(hover["circle-stroke-color"]).toBe(PUBLIC_MAP_PALETTE.light.selection);
    expect(selected["circle-stroke-color"]).toBe(PUBLIC_MAP_PALETTE.light.selection);
  });

  it("colors the marker stack per theme+mode at build time (no shared mutable state)", () => {
    const lightPoints = publicSpotLayers("light", "wind").find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.points)!.paint as any;
    const darkPoints = publicSpotLayers("dark", "wind").find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.points)!.paint as any;
    // Neutral fallback (no live value) differs per theme even though the
    // expression shape is identical.
    expect(lightPoints["circle-color"][2]).toBe(PUBLIC_MAP_PALETTE.light.spot);
    expect(darkPoints["circle-color"][2]).toBe(PUBLIC_MAP_PALETTE.dark.spot);
  });

  it("clusters never encode a live value — always the neutral theme color", () => {
    const clusters = publicSpotLayers("light", "waves").find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.clusters)!.paint as any;
    expect(clusters["circle-color"]).toBe(PUBLIC_MAP_PALETTE.light.spot);
  });

  it("gates the collision-driven name layer at the local/regional zoom, not street level", () => {
    const names = publicSpotLayers("light").find((l) => l.id === PUBLIC_SPOT_LAYER_IDS.names)!;
    expect(names.minzoom).toBe(11);
    expect((names.layout as any)["text-allow-overlap"]).toBe(false);
  });

  it("exposes exactly the documented layer ids (shadow/clusters/hover/selection/names stack)", () => {
    expect(Object.values(PUBLIC_SPOT_LAYER_IDS)).toHaveLength(9);
    expect(PUBLIC_SPOT_SOURCE_ID).toBe("public-spots");
  });
});

describe("buildPublicMapStyle — pure style-document transform", () => {
  it("bakes the spot source and marker layers into the returned document", () => {
    const style = buildPublicMapStyle(fakeBaseStyle(), "light");
    expect(style.sources[PUBLIC_SPOT_SOURCE_ID]).toBeDefined();
    const ids = style.layers.map((l: any) => l.id);
    for (const id of Object.values(PUBLIC_SPOT_LAYER_IDS)) expect(ids).toContain(id);
  });

  it("recolors water/land/roads and never leaves the base document's placeholder black", () => {
    const style = buildPublicMapStyle(fakeBaseStyle(), "light");
    const byId = new Map(style.layers.map((l: any) => [l.id, l]));
    expect((byId.get("water").paint as any)["fill-color"]).toBe(PUBLIC_MAP_PALETTE.light.water);
    expect((byId.get("background").paint as any)["background-color"]).toBe(PUBLIC_MAP_PALETTE.light.land);
    expect((byId.get("road_pri_fill_noramp").paint as any)["line-color"]).not.toBe("#000000");
  });

  it("produces two independently colored documents for light/dark from the same base", () => {
    const base = fakeBaseStyle();
    const light = buildPublicMapStyle(base, "light");
    const dark = buildPublicMapStyle(base, "dark");
    const waterOf = (s: StyleSpecification) => (s.layers.find((l: any) => l.id === "water") as any).paint["fill-color"];
    expect(waterOf(light)).toBe(PUBLIC_MAP_PALETTE.light.water);
    expect(waterOf(dark)).toBe(PUBLIC_MAP_PALETTE.dark.water);
    // The base document passed in must not be mutated — building the dark
    // variant right after the light one must not have altered it.
    expect((base.layers[1] as any).paint["fill-color"]).toBe("#000000");
  });

  it("hides layers with no place in the editorial map (poi clutter, house numbers)", () => {
    const style = buildPublicMapStyle(fakeBaseStyle(), "light");
    const byId = new Map(style.layers.map((l: any) => [l.id, l]));
    expect((byId.get("poi_stadium").layout as any).visibility).toBe("none");
    expect((byId.get("housenumber").layout as any).visibility).toBe("none");
  });

  it("keeps only national capitals (capital = 2), filtering out the upstream regional set", () => {
    const style = buildPublicMapStyle(fakeBaseStyle(), "light");
    const capital = style.layers.find((l: any) => l.id === "place_capital_dot_z7") as any;
    expect(capital.filter).toEqual(["==", "capital", 2]);
  });

  it("tolerates an optional CARTO layer being absent from the fetched document", () => {
    const sparse: StyleSpecification = { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: {} }] } as StyleSpecification;
    expect(() => buildPublicMapStyle(sparse, "light")).not.toThrow();
    const style = buildPublicMapStyle(sparse, "light");
    expect(style.layers.some((l: any) => l.id === PUBLIC_SPOT_LAYER_IDS.points)).toBe(true);
  });
});

describe("selection state (live map only)", () => {
  function fakeMap() {
    const layers = new Map<string, any>();
    for (const id of Object.values(PUBLIC_SPOT_LAYER_IDS)) layers.set(id, { id, filter: undefined });
    return {
      getLayer: (id: string) => layers.get(id),
      setFilter: vi.fn((id: string, filter: unknown) => { const l = layers.get(id); if (l) l.filter = filter; }),
      _layers: layers,
    } as any;
  }

  it("filters hover/selected layers by feature id, defaulting to an impossible match", () => {
    const map = fakeMap();
    setPublicSpotSelection(map, "hover-1", "sel-1");
    expect(map._layers.get(PUBLIC_SPOT_LAYER_IDS.hover).filter).toEqual(["==", ["get", "spotId"], "hover-1"]);
    expect(map._layers.get(PUBLIC_SPOT_LAYER_IDS.selected).filter).toEqual(["==", ["get", "spotId"], "sel-1"]);
    setPublicSpotSelection(map, undefined, undefined);
    expect(map._layers.get(PUBLIC_SPOT_LAYER_IDS.hover).filter).toEqual(["==", ["get", "spotId"], ""]);
  });

  it("filters the cluster hover ring by cluster_id, off by default", () => {
    const map = fakeMap();
    setPublicClusterHover(map, 42);
    expect(map._layers.get(PUBLIC_SPOT_LAYER_IDS.clusterHover).filter).toEqual(["==", ["get", "cluster_id"], 42]);
    setPublicClusterHover(map, undefined);
    expect(map._layers.get(PUBLIC_SPOT_LAYER_IDS.clusterHover).filter).toEqual(["==", ["get", "cluster_id"], -1]);
  });
});

describe("public spot GeoJSON", () => {
  it("uses stable ids and lng/lat coordinates without admin fields", () => {
    const input = { ...spot("spot-1", "Almanarre", [43.08, 6.15]), slug: "almanarre", regionName: "Provence", regionCountry: "FR", typicalWindKt: 22, description: "not exported" };
    const data = spotsToGeoJson([input]);
    expect(data.features[0]).toMatchObject({ id: "spot-1", geometry: { coordinates: [6.15, 43.08] }, properties: { spotId: "spot-1", slug: "almanarre", name: "Almanarre", region: "Provence", country: "FR", windKt: 22, liveWindKt: null, liveWaveM: null } });
    expect(data.features[0].properties).not.toHaveProperty("description");
  });

  it("omits entries without public coordinates", () => {
    const withoutCoords = { ...spot("draft", "Ohne Lage", [0, 0]), coords: undefined };
    expect(spotsToGeoJson([withoutCoords]).features).toHaveLength(0);
  });

  it("merges live readings by spot id, never backfilling from the typical value", () => {
    const input = { ...spot("spot-1", "Almanarre", [43.08, 6.15]), typicalWindKt: 22 };
    const live = new Map([["spot-1", { windKt: 18, waveM: 1.2 }]]);
    const withLive = spotsToGeoJson([input], live).features[0].properties;
    expect(withLive.liveWindKt).toBe(18);
    expect(withLive.liveWaveM).toBe(1.2);
    expect(withLive.windKt).toBe(22); // typical value untouched

    const noEntry = spotsToGeoJson([input], new Map()).features[0].properties;
    expect(noEntry.liveWindKt).toBeNull();
    expect(noEntry.liveWaveM).toBeNull();
  });
});

describe("marker mode — wind/wave live-data coloring", () => {
  it("falls back to the neutral theme color when a spot has no live value for the active mode", () => {
    const expr = spotColorExpression("wind", "light") as any;
    expect(expr[0]).toBe("case");
    expect(expr[1]).toEqual(["==", ["get", "liveWindKt"], null]);
    expect(expr[2]).toBe(PUBLIC_MAP_PALETTE.light.spot);
  });

  it("steps through the exact windScale.ts bins for wind mode", () => {
    const expr = spotColorExpression("wind", "light") as any;
    const step = expr[3];
    expect(step[0]).toBe("step");
    expect(step[1]).toEqual(["get", "liveWindKt"]);
    expect(step[2]).toBe("#A9B7C2"); // WIND_BINS[0]
    expect(step).toContain("#4A8159"); // green bin present
  });

  it("steps through the exact waveScale.ts bins for waves mode, using a different field", () => {
    const expr = spotColorExpression("waves", "light") as any;
    const step = expr[3];
    expect(step[1]).toEqual(["get", "liveWaveM"]);
    expect(step[2]).toBe("#C9DDE2"); // WAVE_BINS[0]
    expect(step).toContain("#1C4E63"); // teal bin present
  });

  it("wind and wave expressions never share a step color (visually distinct systems)", () => {
    const windColors = (spotColorExpression("wind", "light") as any)[3].filter((_: unknown, i: number) => i >= 2 && i % 2 === 0);
    const waveColors = (spotColorExpression("waves", "light") as any)[3].filter((_: unknown, i: number) => i >= 2 && i % 2 === 0);
    for (const c of waveColors) expect(windColors).not.toContain(c);
  });

  it("setPublicSpotMode swaps circle-color on points/hover/selected only, leaving clusters untouched", () => {
    const calls: [string, string, unknown][] = [];
    const map = {
      getLayer: () => ({}),
      setPaintProperty: (id: string, prop: string, value: unknown) => calls.push([id, prop, value]),
    } as any;
    setPublicSpotMode(map, "waves", "light");
    const touchedLayers = calls.map(([id]) => id);
    expect(touchedLayers).toEqual([PUBLIC_SPOT_LAYER_IDS.points, PUBLIC_SPOT_LAYER_IDS.hover, PUBLIC_SPOT_LAYER_IDS.selected]);
    expect(touchedLayers).not.toContain(PUBLIC_SPOT_LAYER_IDS.clusters);
    expect(calls.every(([, prop]) => prop === "circle-color")).toBe(true);
  });

  it("setPublicSpotMode skips a layer that isn't present on the map yet", () => {
    const map = { getLayer: () => undefined, setPaintProperty: vi.fn() } as any;
    expect(() => setPublicSpotMode(map, "wind", "light")).not.toThrow();
    expect(map.setPaintProperty).not.toHaveBeenCalled();
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
