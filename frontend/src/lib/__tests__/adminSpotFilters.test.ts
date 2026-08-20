import { describe, expect, it } from "vitest";
import { countActiveAdminSpotFilters, resetAdminSpotFilters } from "../adminSpotFilters";

describe("admin spot filters", () => {
  it("shows reset only from two meaningful filters", () => {
    expect(countActiveAdminSpotFilters(new URLSearchParams("sort=-updated&offset=25"))).toBe(0);
    expect(countActiveAdminSpotFilters(new URLSearchParams("q=Tarifa"))).toBe(1);
    expect(countActiveAdminSpotFilters(new URLSearchParams("q=Tarifa&sport=kitesurf"))).toBe(2);
  });

  it("clears all filters and offset while preserving non-default sorting", () => {
    const result = resetAdminSpotFilters(
      new URLSearchParams("q=Tarifa&status=draft&region_id=r1&sport=surf&completeness=incomplete&media=no_hero&offset=50&sort=-updated"),
    );
    expect(result.toString()).toBe("sort=-updated");
  });

  it("omits the default sorting from the reset URL", () => {
    expect(resetAdminSpotFilters(new URLSearchParams("q=Tarifa&sort=name")).toString()).toBe("");
  });
});
