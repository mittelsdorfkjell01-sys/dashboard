import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { LiveConditionsRead, WaveComponents } from "../../../lib/api";
import { SpotDataScopeProvider } from "../../../state/SpotDataScope";
import WindSidebar from "./WindSidebar";

// No forecast in scope, so selectedForecast is null and the WELLE tile reads
// from live.current — the deterministic path for asserting the wave breakdown.
function renderWith(waves: WaveComponents, swell: number | null) {
  const live = { time: "2026-09-07T12:00:00Z", current: { swell, waves } } as unknown as LiveConditionsRead;
  return renderToStaticMarkup(
    <SpotDataScopeProvider>
      <WindSidebar forecast={null} live={live} />
    </SpotDataScopeProvider>,
  );
}

const comp = (h: number) => ({ significant_height_m: h });

describe("WindSidebar wave breakdown", () => {
  it("headlines total wave height and lists every resolved component", () => {
    const html = renderWith(
      { total_wave: comp(0.8), wind_sea: comp(0.4), primary_swell: comp(0.6), secondary_swell: comp(0.1) },
      0.6,
    );
    expect(html).toContain("0.8"); // headline = total significant wave height
    expect(html).toContain("Dünung 0.6 m");
    expect(html).toContain("Windsee 0.4 m");
    expect(html).toContain("2. Dünung 0.1 m");
  });

  it("omits components the model did not resolve — never a placeholder", () => {
    const html = renderWith({ total_wave: comp(0.8), primary_swell: comp(0.6) }, 0.6);
    expect(html).toContain("Dünung 0.6 m");
    expect(html).not.toContain("Windsee");
    expect(html).not.toContain("2. Dünung");
  });

  it("falls back to the flat swell when no decomposition is present", () => {
    const live = { time: "2026-09-07T12:00:00Z", current: { swell: 1.3, waves: null } } as unknown as LiveConditionsRead;
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={live} />
      </SpotDataScopeProvider>,
    );
    expect(html).toContain("1.3"); // headline from the legacy flat primary swell
    expect(html).not.toContain("Windsee");
  });
});
