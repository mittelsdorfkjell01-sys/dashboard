import { describe, expect, it } from "vitest";
import {
  parsePublicMapUrl,
  publicMapSearch,
  spotDotColor,
  spotFeatures,
  sortViewportSpots,
  spotCountLabel,
  PUBLIC_SPOT_CLUSTER_RADIUS,
  PUBLIC_SPOT_CLUSTER_MAX_ZOOM,
} from "../publicMap";
import { windColor } from "../windScale";
import { waveColor } from "../waveScale";
import type { Spot } from "../types";

const spot = (over: Partial<Spot> = {}): Spot => ({
  id: "s1",
  name: "Tarifa",
  slug: "tarifa",
  region: "Cádiz",
  regionName: "Cádiz",
  regionCountry: "ES",
  wind: 0,
  tags: [],
  image: "",
  coords: [36.01, -5.61],
  ...over,
});

describe("public map URL state", () => {
  it("accepts a shareable valid state and rejects unsafe values", () => {
    expect(parsePublicMapUrl("?lat=36.01&lon=-5.61&z=8.5&spot=a")).toEqual({ center: [-5.61, 36.01], zoom: 8.5, spot: "a" });
    expect(parsePublicMapUrl("?lat=999&lon=x&z=99")).toBeNull();
  });

  it("ignores obsolete overview mode parameters", () => {
    expect(parsePublicMapUrl("?lat=36&lon=-5&z=8&mode=waves")).toEqual({
      center: [-5, 36],
      zoom: 8,
      spot: undefined,
    });
  });

  it("serializes map state without dropping unrelated query values", () => {
    expect(publicMapSearch([8, 40], 6, "a", "?campaign=summer")).toContain("campaign=summer");
    expect(publicMapSearch([8, 40], 6, "a")).toContain("spot=a");
  });

  it("removes obsolete overview mode parameters from shared URLs", () => {
    expect(publicMapSearch([8, 40], 6, undefined, "?mode=waves")).not.toContain("mode=");
  });
});

describe("marker colour", () => {
  it("uses the shared wind/wave scales for the active mode", () => {
    expect(spotDotColor("wind", { windKt: 22, waveM: null })).toBe(windColor(22));
    expect(spotDotColor("waves", { windKt: null, waveM: 1.4 })).toBe(waveColor(1.4));
  });

  it("falls back to the scale's neutral colour when no live value exists", () => {
    expect(spotDotColor("wind", undefined)).toBe(windColor(null));
    expect(spotDotColor("waves", { windKt: 10, waveM: null })).toBe(waveColor(null));
  });
});

describe("clustering input + config", () => {
  it("builds lng/lat point features and drops spots without coordinates", () => {
    const features = spotFeatures([spot(), spot({ id: "s2", coords: undefined })]);
    expect(features).toHaveLength(1);
    expect(features[0].geometry.coordinates).toEqual([-5.61, 36.01]);
    expect(features[0].properties.spotId).toBe("s1");
  });

  it("uses a fixed radius and a max zoom that unclusters around zoom 10", () => {
    expect(PUBLIC_SPOT_CLUSTER_RADIUS).toBe(44);
    expect(PUBLIC_SPOT_CLUSTER_MAX_ZOOM).toBe(9);
  });
});

describe("viewport list", () => {
  it("puts the selected spot first, then orders by distance to the centre", () => {
    const near = spot({ id: "near", coords: [40.1, 9.1] });
    const far = spot({ id: "far", coords: [50, 20] });
    const selected = spot({ id: "sel", coords: [48, 18] });
    const ordered = sortViewportSpots([far, selected, near], [40, 9], "sel");
    expect(ordered.map((s) => s.id)).toEqual(["sel", "near", "far"]);
  });

  it("labels the spot count in German singular/plural", () => {
    expect(spotCountLabel(1)).toBe("1 Spot im Kartenausschnitt");
    expect(spotCountLabel(3)).toContain("3 Spots");
  });
});
