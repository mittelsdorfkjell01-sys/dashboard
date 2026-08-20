import { describe, expect, it } from "vitest";
import { adminClusterMarkerLabel, adminSpotMarkerLabel } from "../adminMapAccessibility";

describe("admin map accessible labels", () => {
  it("names a spot marker with its actual spot name", () => {
    expect(adminSpotMarkerLabel("Tarifa")).toBe("Spot öffnen: Tarifa");
  });

  it("names a cluster with its exact count", () => {
    expect(adminClusterMarkerLabel(17)).toBe("17 Spots anzeigen");
  });
});
