import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DirectionCompassView } from "../DirectionCompass";
import type { DirectionSnapshot } from "../../../lib/directionSnapshot";

const snapshot = (patch: Partial<DirectionSnapshot> = {}): DirectionSnapshot => ({
  validAtUtc: "2026-08-24T14:00:00Z", localLabel: "2026-08-24 · 16:00 GMT+2", timezone: "Europe/Berlin", kind: "forecast",
  windDirectionFromDeg: 318, windKt: 21, gustKt: 27, waveDirectionFromDeg: 292, waveHeightM: 1.8, wavePeriodS: 11,
  coastalNormalDeg: 270, windCoastalClassification: "sideshore", waveCoastalClassification: "onshore",
  stale: false, quality: "coastal", provider: null, model: "Forecast", ...patch,
});

describe("DirectionCompassView", () => {
  it("renders wind mode with textual legend and accessible description", () => {
    const html = renderToStaticMarkup(<DirectionCompassView snapshot={snapshot()} sportMode="wind" windUnit="kts"/>);
    expect(html).toContain("Richtung &amp; Anströmung");
    expect(html).toContain("Aus NW");
    expect(html).toContain("Wind aus NW, 318 Grad");
    expect(html).toContain("border-dashed");
  });
  it("renders surf mode from the same wave fields", () => {
    const html = renderToStaticMarkup(<DirectionCompassView snapshot={snapshot()} sportMode="surf" windUnit="kts"/>);
    expect(html).toContain("Aus WNW");
    expect(html).toContain("1.8 m");
  });
  it("draws no wind mark when wind direction is absent", () => {
    const html = renderToStaticMarkup(<DirectionCompassView snapshot={snapshot({ windDirectionFromDeg: null, waveDirectionFromDeg: null })} sportMode="wind" windUnit="kts"/>);
    expect(html).toContain("Windrichtung nicht verfügbar");
    expect(html).not.toContain("M100 21 L100 86");
  });
  it("shows stale and missing coast states explicitly", () => {
    const html = renderToStaticMarkup(<DirectionCompassView snapshot={snapshot({ stale: true, coastalNormalDeg: null, windCoastalClassification: null })} sportMode="wind" windUnit="ms"/>);
    expect(html).toContain("Letzter Stand");
    expect(html).toContain("Küstenbezug nicht verfügbar");
  });
  it("uses theme tokens instead of literal hex colors", () => {
    const html = renderToStaticMarkup(<DirectionCompassView snapshot={snapshot()} sportMode="wind" windUnit="kts"/>);
    expect(html).toContain("var(--sw-surface)");
    expect(html).not.toMatch(/#[0-9a-f]{3,8}/i);
  });
});
