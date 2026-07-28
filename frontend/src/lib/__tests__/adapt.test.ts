import { describe, expect, it } from "vitest";
import type { Region, SpotRead, SpotSummary } from "../api";
import { adaptSpot, regionLabel } from "../adapt";

const summary = (over: Partial<SpotSummary> = {}): SpotSummary => ({
  id: "uuid-1",
  slug: "laboe",
  name: "Laboe",
  region_id: "r1",
  location: { lat: 54.4, lon: 10.2 },
  sports: ["kitesurf"],
  water_type: "sea",
  bottom_type: "sand",
  level: "beginner",
  water_character: "chop",
  style: ["freeride"],
  facilities: { parking: { available: true } },
  status: "published",
  confidence: null,
  facing: 45,
  image: null,
  ...over,
});

const region: Region = {
  id: "r1",
  slug: "kieler-bucht",
  name: "Kieler Bucht",
  country: "DE",
  center: null,
  description: null,
  image: null,
  season: null,
  defaults: null,
  status: "published",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("adaptSpot", () => {
  it("maps identity, coords and category fields", () => {
    const s = adaptSpot(summary(), region);
    expect(s.id).toBe("uuid-1");
    expect(s.uuid).toBe("uuid-1");
    expect(s.coords).toEqual([54.4, 10.2]);
    expect(s.region).toBe("Kieler Bucht, Deutschland");
    expect(s.level).toBe("beginner");
    expect(s.waterCharacter).toBe("chop");
    expect(s.style).toEqual(["freeride"]);
    expect(s.facilities).toEqual({ parking: { available: true } });
  });

  it("leaves image empty when none is set (branded fallback, no picsum)", () => {
    const s = adaptSpot(summary({ image: null }), region);
    expect(s.image).toBe("");
    expect(s.hero).toBeUndefined();
  });

  it("resolves a stored image URL", () => {
    const s = adaptSpot(summary({ image: { url: "/media/spots/x/hero.jpg" } }), region);
    expect(s.image).toContain("/media/spots/x/hero.jpg");
    expect(s.hero).toContain("/media/spots/x/hero.jpg");
  });

  it("derives a typical wind + description from editorial (detail record)", () => {
    const detail = {
      ...summary(),
      editorial: { wind_range: [14, 26], description: "Schöner Spot." },
    } as unknown as SpotRead;
    const s = adaptSpot(detail, region);
    expect(s.wind).toBe(20); // midpoint of 14..26
    expect(s.description).toBe("Schöner Spot.");
  });

  it("treats an 'n/a' description as no description", () => {
    const detail = { ...summary(), editorial: { description: "n/a" } } as unknown as SpotRead;
    expect(adaptSpot(detail, region).description).toBeUndefined();
  });
});

describe("regionLabel", () => {
  it("joins name and country, tolerates missing country", () => {
    expect(regionLabel(region)).toBe("Kieler Bucht, Deutschland");
    expect(regionLabel({ ...region, country: null })).toBe("Kieler Bucht");
    expect(regionLabel(undefined)).toBe("");
  });
});
