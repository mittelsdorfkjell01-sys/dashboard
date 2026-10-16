import { describe, expect, it } from "vitest";
import { buildSearchParams, EMPTY_SEARCH, loadSearchDraft, saveSearchDraft } from "../searchSubmit";

describe("buildSearchParams", () => {
  it("keeps an empty search as the intentional discovery route", () => {
    expect(buildSearchParams(EMPTY_SEARCH).toString()).toBe("");
  });

  it("preserves the chosen place, sport and date context", () => {
    const params = buildSearchParams({
      ...EMPTY_SEARCH,
      whereText: "Tarifa",
      whereSel: { label: "Tarifa", kind: "region", id: "region-1" },
      when: { mode: "range", from: "2026-10-03", to: "2026-10-04" },
      which: ["kitesurf"],
    });

    expect(params.get("q")).toBe("Tarifa");
    expect(params.get("region_id")).toBe("region-1");
    expect(params.get("sport")).toBe("kitesurf");
    expect(params.get("from")).toBe("2026-10-03");
    expect(params.get("to")).toBe("2026-10-04");
  });
});

describe("search draft", () => {
  it("restores the last search without depending on browser storage", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
      removeItem: (key: string) => { values.delete(key); },
    };
    const draft = { ...EMPTY_SEARCH, whereText: "Tarifa", which: ["kitesurf"] };

    saveSearchDraft(draft, storage);
    expect(loadSearchDraft(storage)).toMatchObject(draft);
    saveSearchDraft(null, storage);
    expect(loadSearchDraft(storage)).toEqual(EMPTY_SEARCH);
  });
});
