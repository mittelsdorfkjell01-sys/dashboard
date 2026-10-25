import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import QuiverEditor, { type QuiverDraft } from "../QuiverEditor";
import type { GearCatalogItem } from "../../../lib/account";

const ITEMS: QuiverDraft[] = [
  { clientId: "kite-1", sport: "kitesurf", kind: "kite", size: 9, boardType: null, catalogSizeVariantId: null, catalogColorVariantId: null, active: true, sortOrder: 0 },
  { clientId: "kite-2", sport: "kitesurf", kind: "kite", size: 12, boardType: null, catalogSizeVariantId: null, catalogColorVariantId: null, active: true, sortOrder: 1 },
  { clientId: "board", sport: "kitesurf", kind: "board", size: null, boardType: "foil", catalogSizeVariantId: null, catalogColorVariantId: null, active: true, sortOrder: 2 },
];

const CATALOG_ITEM: GearCatalogItem = {
  catalogSizeVariantId: "size-xr8-11",
  brand: { slug: "core", name: "CORE" },
  category: "kite",
  name: "XR8",
  model: "XR8",
  subtype: null,
  season: "2023",
  modelYear: 2023,
  identityStatus: "verified",
  size: { label: "11 m²", value: 11, unit: "m²" },
  colors: [],
  specifications: [{
    field: "weight_without_bag",
    group: "dimensions",
    value: { value: 3.5 },
    unit: "kg",
    status: "verified",
    verifiedAt: "2026-10-22T12:00:00Z",
    uncertainty: null,
    source: {
      title: "Official weights",
      publisher: "CORE",
      url: "https://support.corekites.com/weights",
      type: "manufacturer_page",
      checkedAt: "2026-10-22T12:00:00Z",
    },
  }],
  compatibility: [{
    targetCategory: "bar", targetProductVersionId: null, targetProduct: null, relation: "recommended",
    specification: { system: "Sensor Bar System" }, status: "verified",
    verifiedAt: "2026-10-22T12:00:00Z", notes: null,
    source: {
      title: "Official compatibility", publisher: "CORE",
      url: "https://support.corekites.com/compatibility", type: "manufacturer_page",
      checkedAt: "2026-10-22T12:00:00Z",
    },
  }],
  useProfiles: [{
    sport: "kitesurf", discipline: "big_air", condition: "strong_wind",
    suitability: "suitable", sizeVariantId: null,
    status: "review", verifiedAt: null, notes: "Qualitative classification pending.",
    source: {
      title: "Official use", publisher: "CORE",
      url: "https://support.corekites.com/use", type: "manufacturer_page",
      checkedAt: "2026-10-22T12:00:00Z",
    },
  }],
};

describe("QuiverEditor", () => {
  it("renders every kite size and the selected board type", () => {
    const html = renderToStaticMarkup(<QuiverEditor items={ITEMS} onChange={() => undefined} />);
    expect(html).toContain('aria-label="Größe Kite 1 in Quadratmetern"');
    expect(html).toContain('value="9"');
    expect(html).toContain('value="12"');
    expect(html).toContain('<option value="foil" selected="">Foilboard</option>');
  });

  it("shows an actionable empty state", () => {
    const html = renderToStaticMarkup(<QuiverEditor items={[]} onChange={() => undefined} />);
    expect(html).toContain("Füge mindestens einen Kite hinzu.");
    expect(html).toContain("Kite hinzufügen");
  });

  it("shows product identity, evidence, use and compatibility for a catalog selection", () => {
    const selected: QuiverDraft = {
      ...ITEMS[0],
      size: 11,
      catalogSizeVariantId: CATALOG_ITEM.catalogSizeVariantId,
      catalogItem: CATALOG_ITEM,
    };
    const html = renderToStaticMarkup(
      <QuiverEditor items={[selected]} catalog={[CATALOG_ITEM]} onChange={() => undefined} />,
    );

    expect(html).toContain("CORE XR8");
    expect(html).toContain("2023 · 11 m²");
    expect(html).toContain("Einsatzbereiche");
    expect(html).toContain("Big Air");
    expect(html).toContain("Starkwind");
    expect(html).toContain("Kompatibilität");
    expect(html).toContain("Sensor Bar System");
    expect(html).toContain("Maße und Gewicht");
    expect(html).toContain("Gewicht ohne Tasche");
    expect(html).toContain("3.5 kg");
    expect(html).toContain("Official weights");
  });
});
