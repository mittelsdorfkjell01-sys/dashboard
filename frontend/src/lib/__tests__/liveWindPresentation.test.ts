import { describe, expect, it } from "vitest";
import type { LiveConditionsRead, LiveWindAnalysis } from "../api";
import {
  currentWindPresentation,
  friendlyFallbackReason,
  uncertaintyBandKt,
} from "../liveWindPresentation";

const NOW = Date.parse("2026-09-14T12:15:00Z");

const analysis = (patch: Partial<LiveWindAnalysis> = {}): LiveWindAnalysis => ({
  contract_version: "live-wind-v1",
  product_type: "live_wind",
  status: "station_adjusted",
  analyzed_at: "2026-09-14T12:10:00Z",
  valid_at: "2026-09-14T12:00:00Z",
  wind_speed_ms: 10.2,
  wind_direction_from_deg: 276,
  wind_u_ms: 10.0,
  wind_v_ms: -2.12,
  gust: null,
  model_version: "consensus-v1",
  analysis_version: "regional-live-wind-uv-v1",
  station_count: 3,
  uncertainty_ms: 1.2,
  confidence: 0.8,
  sources: [{ source_type: "model_nowcast", source: "consensus" }],
  applied_physics_version: "physics-v1",
  fallback_reason: null,
  ...patch,
});

const live = (patch: Partial<LiveConditionsRead> = {}): LiveConditionsRead => ({
  spot_id: "spot-1",
  model: "surfwinddata",
  time: "2026-09-14T12:00:00Z",
  current: {
    wind: 14,
    gust: 19,
    wind_ms: 7.2,
    dir: 220,
    air: 18,
    sst: 17,
    swell: 1.1,
    period: 8,
    swell_dir: 250,
  },
  live_wind: analysis(),
  ...patch,
});

describe("currentWindPresentation", () => {
  it("uses LiveWind and never the separate station measurement as the spot value", () => {
    const value = currentWindPresentation(live({
      measurement: {
        observation_type: "measurement",
        station_id: "station-1",
        provider: "DWD",
        provider_station_id: "123",
        observed_at: "2026-09-14T12:11:00Z",
        age_seconds: 240,
        distance_km: 2.4,
        wind_speed_ms: 30,
        wind_gust_ms: 35,
        wind_direction_from_deg: 90,
        quality: 1,
      },
    }), NOW);

    expect(value).toMatchObject({
      source: "live_wind",
      status: "station_adjusted",
      windKt: 20,
      directionFromDeg: 280,
      ageMinutes: 5,
      stationCount: 3,
    });
    expect(value.windMs).toBe(10.2);
  });

  it("falls back only to the model nowcast and explains an unavailable analysis", () => {
    const value = currentWindPresentation(live({
      live_wind: analysis({
        status: "unavailable",
        analyzed_at: null,
        valid_at: null,
        wind_speed_ms: null,
        wind_direction_from_deg: null,
        wind_u_ms: null,
        wind_v_ms: null,
        model_version: null,
        analysis_version: null,
        station_count: 0,
        uncertainty_ms: null,
        confidence: null,
        sources: [],
        applied_physics_version: null,
        fallback_reason: "engine_disabled",
      }),
    }), NOW);

    expect(value).toMatchObject({ source: "model_nowcast", status: "baseline", windKt: 14, directionFromDeg: 220 });
    expect(value.fallbackReason).toContain("noch nicht aktiviert");
  });

  it("marks calm wind as variable and weak evidence as directionally uncertain", () => {
    expect(currentWindPresentation(live({ live_wind: analysis({ wind_speed_ms: 1.2 }) }), NOW).directionState).toBe("variable");
    expect(currentWindPresentation(live({ live_wind: analysis({ confidence: 0.2 }) }), NOW).directionState).toBe("uncertain");
  });

  it("exposes a rounded uncertainty band and a stale analysis state", () => {
    const value = currentWindPresentation(live({
      live_wind: analysis({ analyzed_at: "2026-09-14T11:00:00Z" }),
    }), NOW);
    expect(value.stale).toBe(true);
    expect(uncertaintyBandKt(value)).toEqual([17, 22]);
  });

  it("translates operational and unknown fallbacks without leaking internal codes", () => {
    expect(friendlyFallbackReason("operational_gate:fallback_rate_high")).toContain("Betriebsproblem");
    expect(friendlyFallbackReason("future_internal_code")).not.toContain("future_internal_code");
  });
});
