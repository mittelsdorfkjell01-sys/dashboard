import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import WindWindowSlider, { formatWindWindow, WIND_WINDOW_MIN, WIND_WINDOW_MAX } from "../WindWindowSlider";

describe("formatWindWindow", () => {
  it("formats a closed window", () => {
    expect(formatWindWindow(15, 20)).toBe("15–20 kt");
  });
  it("formats an open upper bound as N+", () => {
    expect(formatWindWindow(30, null)).toBe("30+ kt");
  });
});

describe("WindWindowSlider", () => {
  it("renders two independently labeled range handles within the documented bounds", () => {
    const html = renderToStaticMarkup(<WindWindowSlider minWindKn={15} maxWindKn={20} onChange={() => undefined} />);
    expect(html).toContain('aria-label="Mindestwindgeschwindigkeit"');
    expect(html).toContain('aria-label="Höchstwindgeschwindigkeit"');
    expect(html).toContain(`min="${WIND_WINDOW_MIN}"`);
    expect(html).toContain(`max="${WIND_WINDOW_MAX}"`);
    expect(html).toContain('aria-valuetext="15 Knoten"');
    expect(html).toContain('aria-valuetext="20 Knoten"');
  });

  it("labels an open upper bound distinctly for screen readers", () => {
    const html = renderToStaticMarkup(<WindWindowSlider minWindKn={30} maxWindKn={null} onChange={() => undefined} />);
    expect(html).toContain("40 Knoten oder mehr, offen");
  });
});
