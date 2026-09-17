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

  it("renders the LiveWind contract and the station as a separate observed-at reference", () => {
    const live = {
      spot_id: "spot-1",
      model: "surfwinddata",
      time: "2026-09-16T08:00:00Z",
      current: { wind: 12, gust: 16, dir: 220, swell: 1.1, waves: null },
      live_wind: {
        contract_version: "live-wind-v1", product_type: "live_wind", status: "station_adjusted",
        analyzed_at: "2026-09-16T08:05:00Z", valid_at: "2026-09-16T08:00:00Z",
        wind_speed_ms: 8, wind_direction_from_deg: 274, wind_u_ms: 7.98, wind_v_ms: -0.56,
        gust: null, model_version: "consensus-v1", analysis_version: "regional-live-wind-uv-v1",
        station_count: 3, uncertainty_ms: 1, confidence: 0.8,
        sources: [{ source_type: "station_residual", source: "residual:a" }],
        applied_physics_version: "physics-v1", fallback_reason: null,
      },
      measurement: {
        observation_type: "measurement", station_id: "station-1", provider: "DWD", provider_station_id: "01234",
        station_name: "Küstenstation", observed_at: "2026-09-16T07:58:00Z", age_seconds: 420,
        distance_km: 3.2, wind_speed_ms: 7, wind_gust_ms: 9, wind_direction_from_deg: 260, quality: 1,
      },
    } as unknown as LiveConditionsRead;
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={live} />
      </SpotDataScopeProvider>,
    );
    expect(html).toContain("Aktuelle Bedingungen");
    expect(html).toContain("Stationskorrigiert");
    expect(html).toContain("Unsicherheitsband");
    expect(html).toContain("Relevante Stationen");
    expect(html).toContain("Küstenstation");
    expect(html).toMatch(/3[,.]2 km entfernt/);
    expect(html).toContain("Gemessen");
    expect(html).toContain("07:58");
  });

  it("shows the model baseline and a readable fallback instead of inventing LiveWind", () => {
    const live = {
      spot_id: "spot-1", model: "surfwinddata", time: "2026-09-16T08:00:00Z",
      current: { wind: 12, gust: 16, dir: 220, swell: 1.1 },
      live_wind: {
        contract_version: "live-wind-v1", product_type: "live_wind", status: "unavailable",
        analyzed_at: null, valid_at: null, wind_speed_ms: null, wind_direction_from_deg: null,
        wind_u_ms: null, wind_v_ms: null, gust: null, model_version: null, analysis_version: null,
        station_count: 0, uncertainty_ms: null, confidence: null, sources: [],
        applied_physics_version: null, fallback_reason: "station_residuals_unavailable",
      },
    } as unknown as LiveConditionsRead;
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={live} />
      </SpotDataScopeProvider>,
    );
    expect(html).toContain("Baseline");
    expect(html).toContain("keine ausreichend aktuellen Stationsresiduen");
  });

  it("labels weak wind as variable and suppresses a precise compass bearing", () => {
    const live = {
      spot_id: "spot-1", model: "surfwinddata", time: "2026-09-16T08:00:00Z",
      current: { wind: 2, gust: 3, dir: 220, swell: null },
    } as unknown as LiveConditionsRead;
    const html = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={live} />
      </SpotDataScopeProvider>,
    );
    expect(html).toContain("Wind variabel");
    expect(html).not.toContain("220 Grad");
  });

  it("covers loading, error and stale current-condition states", () => {
    const loading = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={null} liveLoading />
      </SpotDataScopeProvider>,
    );
    expect(loading).toContain("Aktuelle Bedingungen werden geladen");

    const failed = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={null} liveError="API nicht erreichbar" onRetryLive={() => undefined} />
      </SpotDataScopeProvider>,
    );
    expect(failed).toContain("API nicht erreichbar");
    expect(failed).toContain("Aktuelle Bedingungen erneut laden");

    const staleLive = {
      spot_id: "spot-1", model: "surfwinddata", time: "2026-09-16T08:00:00Z",
      current: { wind: 12, gust: 16, dir: 220, air: null, sst: null, swell: null, period: null, swell_dir: null },
    } as unknown as LiveConditionsRead;
    const stale = renderToStaticMarkup(
      <SpotDataScopeProvider>
        <WindSidebar forecast={null} live={staleLive} liveStale />
      </SpotDataScopeProvider>,
    );
    expect(stale).toContain("Diese Analyse ist veraltet");
  });
});
