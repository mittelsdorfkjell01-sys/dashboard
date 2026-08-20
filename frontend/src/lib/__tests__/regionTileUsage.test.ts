import { describe, expect, it } from "vitest";
import { revalidate, __resetCache } from "../swr";
import searchResultsSrc from "../../pages/SearchResults.tsx?raw";
import similarRegionsSrc from "../../components/SimilarRegions.tsx?raw";
import regionTileSrc from "../../components/RegionTile.tsx?raw";

describe("region tile: one shared design across surfaces", () => {
  it("SearchResults renders region rows through the shared RegionTile", () => {
    expect(searchResultsSrc).toContain('import RegionTile from "../components/RegionTile"');
    expect(searchResultsSrc).toMatch(/<RegionTile\b/);
    // The retired image-overlay props must not be wired up anywhere anymore.
    expect(searchResultsSrc).not.toMatch(/\bcoverage=\{/);
    expect(searchResultsSrc).not.toMatch(/\brank=\{/);
    expect(searchResultsSrc).not.toMatch(/\bwindMonths=/);
  });

  it("SimilarRegions renders through the same shared RegionTile, not a bespoke card", () => {
    expect(similarRegionsSrc).toContain('import RegionTile from "./RegionTile"');
    expect(similarRegionsSrc).toMatch(/<RegionTile\b/);
    expect(similarRegionsSrc).not.toContain("WindBadge");
    expect(similarRegionsSrc).not.toContain("aspect-[16/11]");
  });

  it("RegionTile itself never performs a data fetch (props-only, no per-tile request)", () => {
    expect(regionTileSrc).not.toMatch(/\bfetch\(/);
    expect(regionTileSrc).not.toMatch(/\buseSwr\(/);
    expect(regionTileSrc).not.toMatch(/\buseEffect\(/);
    expect(regionTileSrc).not.toMatch(/\bapi\.get/);
  });
});

describe("region tile data: one collective fetch, never one per tile", () => {
  it("many tiles resolving the same 'regions' key join a single in-flight request", async () => {
    __resetCache();
    let calls = 0;
    const fetcher = () =>
      new Promise<{ id: string }[]>((resolve) => {
        calls += 1;
        setTimeout(() => resolve([{ id: "r1" }, { id: "r2" }]), 5);
      });
    // Simulate 12 region tiles mounting at once (e.g. a full search results
    // grid) and each asking the shared cache for the "regions" key.
    const requests = Array.from({ length: 12 }, () => revalidate("regions", fetcher));
    await Promise.all(requests);
    expect(calls).toBe(1);
  });
});
