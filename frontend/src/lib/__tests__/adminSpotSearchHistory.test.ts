import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getAdminSpotSearches,
  rememberAdminSpotSearch,
} from "../adminSpotSearchHistory";

describe("admin spot search history", () => {
  const values = new Map<string, string>();

  beforeEach(() => {
    values.clear();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
      },
    });
  });

  it("keeps the latest unique searches first", () => {
    rememberAdminSpotSearch("Laboe");
    rememberAdminSpotSearch("Fehmarn");
    rememberAdminSpotSearch("laboe");

    expect(getAdminSpotSearches()).toEqual(["laboe", "Fehmarn"]);
  });

  it("ignores empty searches and caps the history", () => {
    for (let i = 0; i < 10; i += 1) rememberAdminSpotSearch(`Spot ${i}`);
    rememberAdminSpotSearch("   ");

    expect(getAdminSpotSearches()).toHaveLength(8);
    expect(getAdminSpotSearches()[0]).toBe("Spot 9");
  });
});
