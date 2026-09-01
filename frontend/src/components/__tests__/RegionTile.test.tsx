import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import RegionTile from "../RegionTile";

function render(props: Partial<React.ComponentProps<typeof RegionTile>> = {}) {
  const merged = {
    slug: "tarifa",
    name: "Tarifa",
    country: "ES",
    image: null,
    spotCount: 3,
    sports: ["kitesurf", "windsurf"],
    ...props,
  };
  return renderToStaticMarkup(
    <MemoryRouter>
      <RegionTile {...merged} />
    </MemoryRouter>,
  );
}

describe("RegionTile", () => {
  it("shows the singular 'Spot' for exactly one spot", () => {
    const html = render({ spotCount: 1 });
    expect(html).toContain("1 Spot");
    expect(html).not.toContain("1 Spots");
  });

  it("shows the plural 'Spots' for any other count", () => {
    expect(render({ spotCount: 18 })).toContain("18 Spots");
    expect(render({ spotCount: 0 })).toContain("0 Spots");
  });

  it("renders no overlay/badge/gradient/coverage markup on top of the image", () => {
    const html = render();
    // Retired RegionTile chrome: rank badge, coverage %, wind-months strip,
    // glass caption panel and gradient scrim.
    expect(html).not.toContain("Abdeckung");
    expect(html).not.toContain("Windmonate");
    expect(html).not.toContain("glass");
    // The retired scrim (`bg-gradient-to-t …`) — distinct from SpotImage's own
    // branded-fallback background (`bg-gradient-to-br`), which is expected.
    expect(html).not.toContain("gradient-to-t");
  });

  it("does not invent placeholders for missing optional metadata", () => {
    const html = render({ country: null, sports: [] });
    // No country line and no sports line should be rendered at all — not a
    // dash, not an empty label.
    expect(html).not.toMatch(/—/);
    expect(html).not.toContain("Ohne Region");
  });

  it("frames the image the same way SpotCard does", () => {
    const html = render();
    expect(html).toContain("aspect-video");
    expect(html).toContain("rounded-[14px]");
  });
});
