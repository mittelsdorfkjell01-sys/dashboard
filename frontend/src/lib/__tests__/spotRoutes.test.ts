import { describe, expect, it } from "vitest";
import { spotNameSegment, spotPath } from "../spotRoutes";

describe("spot routes", () => {
  it("uses the unique catalogue slug when available", () => {
    expect(spotPath({ id: "spot-id", slug: "gran-canaria-pozo-izquierdo", name: "Pozo Izquierdo" })).toBe(
      "/spot/gran-canaria-pozo-izquierdo/info",
    );
    expect(spotPath({ id: "spot-id", slug: "naxos-agios-georgios-laguna", name: "Agios Georgios / Laguna" }, "daten")).toBe(
      "/spot/naxos-agios-georgios-laguna/daten",
    );
  });

  it("falls back to UUID and finally the legacy display-name segment", () => {
    expect(spotPath({ id: "spot-id", name: "Agios Georgios / Laguna" })).toBe(
      "/spot/spot-id/info",
    );
    expect(spotPath({ name: "Pozo Izquierdo" })).toBe("/spot/Pozo-Izquierdo/info");
  });

  it("keeps letters readable and normalizes punctuation", () => {
    expect(spotNameSegment("Ribeira d’Ilhas")).toBe("Ribeira-d-Ilhas");
  });

  it("builds the canonical Aileen's dashboard preview route", () => {
    expect(
      spotPath({
        id: "6fb34adc-56be-4802-beb1-e207722079df",
        slug: "aileens",
        name: "Aileen's",
      }),
    ).toBe("/spot/aileens/info");
  });
});
