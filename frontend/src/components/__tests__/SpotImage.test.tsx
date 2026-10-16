import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import SpotImage from "../SpotImage";

describe("SpotImage", () => {
  it("keeps a deferred card URL out of the initial HTML", () => {
    const html = renderToStaticMarkup(
      <SpotImage src="https://cdn.example/large-hero.avif" name="Tarifa" eager={false} />,
    );

    expect(html).toContain("data-deferred-spot-image");
    expect(html).not.toContain("large-hero.avif");
  });

  it("renders an eager image immediately", () => {
    const html = renderToStaticMarkup(
      <SpotImage src="https://cdn.example/hero.avif" name="Tarifa" eager />,
    );

    expect(html).toContain("hero.avif");
    expect(html).toContain('loading="eager"');
  });
});
