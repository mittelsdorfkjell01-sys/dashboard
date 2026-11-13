import { describe, expect, it } from "vitest";
import type { Spot } from "../../lib/types";
import { facilitiesFromMap, spotFactsFrom } from "../spotView";

const baseSpot = (over: Partial<Spot>): Spot => ({
  id: "x",
  name: "X",
  region: "",
  wind: 0,
  tags: [],
  image: "",
  ...over,
});

describe("facilitiesFromMap", () => {
  it("always renders all six kinds, in canonical order", () => {
    const out = facilitiesFromMap({ parking: { available: true } });
    expect(out.map((f) => f.kind)).toEqual(["parking", "shower", "toilet", "changing", "food", "school"]);
  });

  it("marks an absent key as unknown (available: null), not hidden", () => {
    const out = facilitiesFromMap({ parking: { available: true } });
    const shower = out.find((f) => f.kind === "shower")!;
    expect(shower.available).toBeNull();
    expect(shower.note).toBe("Keine Angabe");
  });

  it("flags available:false as demonstrably absent, distinct from unknown", () => {
    const out = facilitiesFromMap({ shower: { available: false } });
    expect(out.find((f) => f.kind === "shower")).toMatchObject({
      available: false,
      note: "Nicht vorhanden",
    });
  });

  it("keeps custom notes in the data model", () => {
    const out = facilitiesFromMap({ toilet: { available: true, note: "am Parkplatz" } });
    expect(out.find((f) => f.kind === "toilet")?.note).toBe("am Parkplatz");
  });

  it("treats null/empty map as all-unknown, never as all-absent", () => {
    for (const map of [null, {}]) {
      const out = facilitiesFromMap(map);
      expect(out).toHaveLength(6);
      expect(out.every((f) => f.available === null)).toBe(true);
    }
  });
});

describe("spotFactsFrom", () => {
  it("only includes axes that are present", () => {
    const facts = spotFactsFrom(baseSpot({ level: ["advanced"], sports: ["kitesurf"] }));
    const labels = facts.map((f) => f.label);
    expect(labels).toContain("Level");
    expect(labels).toContain("Sportarten");
    expect(labels).not.toContain("Wasserart");
    expect(labels).not.toContain("Fahrstil");
  });

  it("renders German labels and a comma-joined style list", () => {
    const facts = spotFactsFrom(
      baseSpot({ level: ["expert"], waterCharacter: ["welle_gross"], style: ["freeride", "wave_riding", "wavekite"] })
    );
    expect(facts.find((f) => f.label === "Level")?.value).toBe("Experte");
    expect(facts.find((f) => f.label === "Wasserart")?.value).toBe("Große Welle");
    expect(facts.find((f) => f.label === "Fahrstil")?.value).toBe("Freeride, Wellenreiten, Wavekite");
  });
});
