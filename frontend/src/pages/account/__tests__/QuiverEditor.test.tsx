import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import QuiverEditor, { type QuiverDraft } from "../QuiverEditor";

const ITEMS: QuiverDraft[] = [
  { clientId: "kite-1", sport: "kitesurf", kind: "kite", size: 9, boardType: null, active: true, sortOrder: 0 },
  { clientId: "kite-2", sport: "kitesurf", kind: "kite", size: 12, boardType: null, active: true, sortOrder: 1 },
  { clientId: "board", sport: "kitesurf", kind: "board", size: null, boardType: "foil", active: true, sortOrder: 2 },
];

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
});
