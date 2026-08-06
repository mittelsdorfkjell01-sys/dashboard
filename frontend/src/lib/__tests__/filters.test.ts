import { describe, expect, it } from "vitest";
import type { Spot } from "../../lib/types";
import {
  activeFilterCount,
  emptyFilters,
  filterSpots,
  filtersToQuery,
  filtersToSearchParams,
  parseFilters,
  sortSpots,
} from "../filters";

const spot = (over: Partial<Spot>): Spot => ({
  id: over.id ?? "x",
  name: over.name ?? "X",
  region: "",
  wind: 0,
  tags: [],
  image: "",
  ...over,
});

describe("filters URL (de)serialisation", () => {
  it("round-trips a populated state through the URL", () => {
    const f = {
      level: "advanced",
      waterCharacter: "welle_gross",
      styles: ["freeride", "big_air"],
      sort: "name-desc" as const,
    };
    const sp = filtersToSearchParams(f);
    expect(parseFilters(sp)).toEqual(f);
  });

  it("omits defaults and drops unknown sort keys", () => {
    expect(filtersToSearchParams(emptyFilters()).toString()).toBe("");
    expect(parseFilters(new URLSearchParams("sort=bogus")).sort).toBe("name-asc");
  });

  it("maps to the server query (style only when present)", () => {
    expect(filtersToQuery({ styles: [], sort: "name-asc" })).toEqual({
      level: undefined,
      water_character: undefined,
      style: undefined,
    });
    expect(filtersToQuery({ level: "pro", styles: ["freeride"], sort: "name-asc" })).toEqual({
      level: "pro",
      water_character: undefined,
      style: ["freeride"],
    });
  });

  it("counts active filters", () => {
    expect(activeFilterCount(emptyFilters())).toBe(0);
    expect(
      activeFilterCount({ level: "pro", styles: ["a", "b"], sort: "name-desc" })
    ).toBe(4);
  });
});

describe("client-side sort", () => {
  const spots = [
    spot({ id: "1", name: "Zeta", level: ["beginner"] }),
    spot({ id: "2", name: "Alpha", level: ["pro"] }),
    spot({ id: "3", name: "Mango", level: ["intermediate"] }),
  ];

  it("sorts by name asc/desc", () => {
    expect(sortSpots(spots, "name-asc").map((s) => s.name)).toEqual([
      "Alpha",
      "Mango",
      "Zeta",
    ]);
    expect(sortSpots(spots, "name-desc").map((s) => s.name)).toEqual([
      "Zeta",
      "Mango",
      "Alpha",
    ]);
  });

  it("sorts by level order", () => {
    expect(sortSpots(spots, "level-asc").map((s) => s.level)).toEqual([
      ["beginner"],
      ["intermediate"],
      ["pro"],
    ]);
    expect(sortSpots(spots, "level-desc").map((s) => s.level)).toEqual([
      ["pro"],
      ["intermediate"],
      ["beginner"],
    ]);
  });

  it("does not mutate the input array", () => {
    const original = [...spots];
    sortSpots(spots, "name-desc");
    expect(spots).toEqual(original);
  });
});

describe("client-side filter", () => {
  const spots = [
    spot({ id: "1", level: ["beginner"], waterCharacter: ["flach"], style: ["freeride"] }),
    spot({ id: "2", level: ["pro"], waterCharacter: ["welle_gross"], style: ["wave_riding"] }),
    spot({ id: "3", level: ["beginner"], waterCharacter: ["chop"], style: ["freeride", "big_air", "wavekite"] }),
  ];

  it("filters by level and water character", () => {
    expect(filterSpots(spots, { level: "beginner", styles: [], sort: "name-asc" }).map((s) => s.id))
      .toEqual(["1", "3"]);
    expect(
      filterSpots(spots, { waterCharacter: "welle_gross", styles: [], sort: "name-asc" }).map((s) => s.id)
    ).toEqual(["2"]);
  });

  it("style filter is an overlap (any match)", () => {
    expect(
      filterSpots(spots, { styles: ["big_air", "freestyle"], sort: "name-asc" }).map((s) => s.id)
    ).toEqual(["3"]);
    expect(
      filterSpots(spots, { styles: ["wavekite"], sort: "name-asc" }).map((s) => s.id)
    ).toEqual(["3"]);
  });
});
