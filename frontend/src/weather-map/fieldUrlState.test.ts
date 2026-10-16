import { describe, expect, it } from "vitest";
import { fieldUrlSearch, parseFieldUrlState, windMapHref } from "./fieldUrlState";

describe("weather field URL state", () => {
  it("keeps the shared camera while switching into wind mode", () => {
    const search = fieldUrlSearch("?lat=54&lon=10&z=6", { mode: "wind", validAt: "2026-10-03T12:00:00Z", model: "icon-eu", display: "arrows", layer: "gust" });
    const state = parseFieldUrlState(search);
    expect(state).toMatchObject({ mode: "wind", center: [10, 54], zoom: 6, model: "icon-eu", display: "arrows", layer: "gust" });
  });

  it("rejects invalid camera values without losing mode", () => {
    const state = parseFieldUrlState("?mode=wind&lat=999&lon=nope&z=40");
    expect(state.mode).toBe("wind");
    expect(state.center).toEqual([9.3, 48.5]);
    expect(state.zoom).toBe(3.5);
  });

  it("restores a shared wave-map link", () => {
    const state = parseFieldUrlState("?mode=waves&lat=48&lon=-5&z=5");
    expect(state.mode).toBe("waves");
    expect(state.layer).toBe("waves");
    expect(state.center).toEqual([-5, 48]);
  });

  it("frames a wind-only map link for the spot and results entries", () => {
    const href = windMapHref([8.68, 50.11], 11, { toggle: false });
    const search = href.slice(href.indexOf("?"));
    const query = new URLSearchParams(search);

    expect(href.startsWith("/map?")).toBe(true);
    expect(query.get("mode")).toBe("wind");
    expect(query.get("toggle")).toBe("0");
    expect(parseFieldUrlState(search)).toMatchObject({ mode: "wind", center: [8.68, 50.11], zoom: 11 });
  });

  it("removes a manual model when automatic coverage selection is restored", () => {
    const search = fieldUrlSearch("?mode=wind&model=icon-d2&lat=50.11&lon=8.68&z=6", { model: undefined });
    const state = parseFieldUrlState(search);

    expect(new URLSearchParams(search).has("model")).toBe(false);
    expect(state.model).toBeUndefined();
  });
});
