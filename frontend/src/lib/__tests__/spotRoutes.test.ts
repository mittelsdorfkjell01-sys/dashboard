import { describe, expect, it } from "vitest";
import { spotNameSegment, spotPath } from "../spotRoutes";

describe("spot routes", () => {
  it("uses only the display name, not UUID or catalogue slug", () => {
    expect(spotPath({ name: "Pozo Izquierdo" })).toBe(
      "/spot/Pozo-Izquierdo/info",
    );
    expect(spotPath({ name: "Pozo Izquierdo" }, "daten")).toBe(
      "/spot/Pozo-Izquierdo/daten",
    );
  });

  it("keeps letters readable and normalizes punctuation", () => {
    expect(spotNameSegment("Ribeira d’Ilhas")).toBe("Ribeira-d-Ilhas");
  });
});
