import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import SpotOriginMark, { SpotOriginLine } from "../SpotOriginMark";
import { SpotOriginContext } from "../../context/SpotOriginContext";
import type { Spot } from "../../lib/types";

function mark(origin: Spot["origin"], mixed: boolean) {
  return renderToStaticMarkup(
    <SpotOriginContext.Provider value={mixed}>
      <SpotOriginMark origin={origin} />
    </SpotOriginContext.Provider>,
  );
}

const spot = (over: Partial<Spot> = {}): Spot =>
  ({ id: "1", name: "Laboe", region: "Kiel", wind: 0, tags: [], image: "", ...over }) as Spot;

describe("SpotOriginMark", () => {
  it("stays hidden while the catalogue is all ours", () => {
    expect(mark("editorial", false)).toBe("");
  });

  it("marks an editorial spot once the catalogue is mixed", () => {
    expect(mark("editorial", true)).toContain("Von der Redaktion erfasst");
  });

  it("never marks a community spot — absence is the distinction, not a second badge", () => {
    expect(mark("community", true)).toBe("");
  });
});

describe("SpotOriginLine", () => {
  it("credits the contributor of a community spot by name", () => {
    const html = renderToStaticMarkup(
      <SpotOriginLine spot={spot({ origin: "community", contributorName: "Lena K." })} />,
    );
    expect(html).toContain("von Lena K. eingetragen");
  });

  it("falls back to the community as a whole when no name is stored", () => {
    const html = renderToStaticMarkup(<SpotOriginLine spot={spot({ origin: "community" })} />);
    expect(html).toContain("von der Community eingetragen");
  });

  it("names the Redaktion for our own records", () => {
    const html = renderToStaticMarkup(<SpotOriginLine spot={spot({ origin: "editorial" })} />);
    expect(html).toContain("von der Redaktion erfasst");
  });
});
