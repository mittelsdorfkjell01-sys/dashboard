import { describe, expect, it } from "vitest";
import { layoutPois, type PoiCandidate } from "./poiLayout";
import { readableOpeningHours } from "./poiMeta";

const poi = (
  id: string,
  category: PoiCandidate["category"],
  x: number,
  y: number,
  distance = 100,
  name: string | null = id,
): PoiCandidate => ({ id, category, x, y, distance, name });

describe("layoutPois", () => {
  it("staggers categories by zoom", () => {
    const items = [poi("s", "surf_school", 50, 50), poi("p", "parking", 200, 50), poi("c", "cafe", 350, 50), poi("b", "bar", 500, 50)];
    const at = (zoom: number) =>
      [...layoutPois(items, { zoom, width: 600, height: 400 })].filter(([, p]) => p.visible).map(([id]) => id).sort();
    expect(at(13)).toEqual([]);
    expect(at(13.6)).toEqual(["s"]);
    expect(at(14.2)).toEqual(["p", "s"]);
    expect(at(14.6)).toEqual(["c", "p", "s"]);
    expect(at(15.2)).toEqual(["b", "c", "p", "s"]);
  });

  it("leaves out a pin that would touch a higher-priority one", () => {
    const result = layoutPois([poi("cafe", "cafe", 100, 100), poi("parking", "parking", 110, 105)], { zoom: 16, width: 400, height: 400 });
    expect(result.get("parking")?.visible).toBe(true);
    expect(result.get("cafe")?.visible).toBe(false);
  });

  it("keeps the selected pin even when it collides", () => {
    const result = layoutPois(
      [poi("cafe", "cafe", 100, 100), poi("parking", "parking", 110, 105)],
      { zoom: 16, width: 400, height: 400, selectedId: "cafe" },
    );
    expect(result.get("cafe")).toEqual({ visible: true, label: true });
  });

  it("never covers the spot pin", () => {
    const result = layoutPois([poi("p", "parking", 100, 100)], {
      zoom: 16, width: 400, height: 400, reserved: [{ left: 90, top: 80, right: 110, bottom: 102 }],
    });
    expect(result.get("p")?.visible).toBe(false);
  });

  it("shows names only from the label zoom and drops a crowded pin", () => {
    const items = [poi("a", "parking", 100, 100, 50, "Strandparkplatz Nord"), poi("b", "parking", 100, 135, 60, "Süd")];
    expect(layoutPois(items, { zoom: 15, width: 400, height: 400 }).get("a")).toEqual({ visible: true, label: false });
    const close = layoutPois(items, { zoom: 16, width: 400, height: 400 });
    expect(close.get("a")).toEqual({ visible: true, label: true });
    expect(close.get("b")?.visible).toBe(false);
  });
});

describe("readableOpeningHours", () => {
  it("translates days and keeps one rule per line", () => {
    expect(readableOpeningHours("Mo-Fr 08:00-18:00; Sa,Su 09:00-17:00; PH off")).toEqual([
      "Mo–Fr 08:00–18:00", "Sa, So 09:00–17:00", "Feiertage geschlossen",
    ]);
    expect(readableOpeningHours("24/7")).toEqual(["Rund um die Uhr"]);
  });
});
