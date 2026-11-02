import { describe, expect, it } from "vitest";
import type { ForecastSummaryRead, WeatherProvenance } from "../api";
import { buildSpotConditionHints, directionName } from "../spotConditionHints";
import type { Spot } from "../types";

const spot = (over: Partial<Spot> = {}): Spot => ({
  id: "spot-1", name: "Test", region: "Küste", wind: 0, tags: [], image: "",
  bottomType: [], facingDeg: 45, ...over,
});

const source = (over: Partial<WeatherProvenance> = {}): WeatherProvenance => ({
  contract_version: "weather-v6",
  source_type: "forecast",
  observation_type: "forecast",
  source: "model",
  provider: "Test",
  captured_at: "2026-10-21T11:55:00Z",
  valid_at: "2026-10-21T12:00:00Z",
  model_run_quality: "capture-time-only",
  stale: false,
  availability: "available",
  quality_tier: "provider_point",
  uncertainty: "not_determined",
  data_issues: [],
  spot_timezone: "Europe/Berlin",
  ...over,
});

const forecast = (hourOver: Partial<NonNullable<ForecastSummaryRead["hour"]>> = {}): ForecastSummaryRead => ({
  spot_id: "spot-1",
  model: "test",
  generated_at: "2026-10-21T11:55:00Z",
  timezone: "Europe/Berlin",
  hour: {
    time: "2026-10-21T12:00:00Z", wind: 12, gust: 15, dir: 225,
    air: 8.2, sst: 14.7, swell: null, period: null, swell_dir: null, precip: null,
    quality_tier: "coastal", coastal_normal_deg: 45,
    coastal_profile_reviewed_at: "2026-10-01T00:00:00Z",
    coastal_classification: "offshore", stale: false, provenance: source(),
    ...hourOver,
  },
});

describe("spot condition hints", () => {
  it("places an editorial safety notice alongside the dynamic hints", () => {
    const hints = buildSpotConditionHints(
      spot({ safetyNotice: "Starke Strömung am Flussauslauf." }),
      forecast(),
    );
    expect(hints[0]).toEqual({
      id: "safety",
      kind: "safety",
      sentence: "Starke Strömung am Flussauslauf.",
      sourceLabel: "Redaktioneller Sicherheitshinweis",
    });
  });

  it("links a verified field source and states when it was checked", () => {
    const hint = buildSpotConditionHints(spot({
      safetyNotice: "Starke Strömung am Flussauslauf.",
      contentSources: [{
        id: "source-1",
        spot_id: "spot-1",
        field_path: "editorial.safety_notice",
        url: "https://example.test/safety",
        title: "Safety source",
        publisher: "Harbour authority",
        checked_at: "2026-10-20T12:00:00Z",
        verification_status: "verified",
        note: null,
      }],
    }), null)[0];
    expect(hint.sourceUrl).toBe("https://example.test/safety");
    expect(hint.timing).toContain("20.10.2026");
  });

  it("writes compass directions out in German", () => {
    expect(directionName(45)).toBe("Nordosten");
    expect(directionName(225)).toBe("Südwesten");
  });

  it("uses only a reviewed coastal profile for an offshore hint, never facing", () => {
    const hints = buildSpotConditionHints(spot({ facingDeg: 225 }), forecast());
    expect(hints.find((hint) => hint.id === "forecast-wind")?.sentence)
      .toBe("Voraussichtlich ablandiger Wind – der Wind kommt aus Südwesten.");

    const unreviewed = buildSpotConditionHints(spot({ facingDeg: 225 }), forecast({ coastal_profile_reviewed_at: null }));
    expect(unreviewed.some((hint) => hint.kind === "wind")).toBe(false);
  });

  it("hides stale dynamic values", () => {
    const stale = source({ stale: true, availability: "available_stale" });
    const hints = buildSpotConditionHints(spot(), forecast({ provenance: stale }));
    expect(hints.some((hint) => hint.kind === "wind" || hint.kind === "temperature")).toBe(false);
  });

  it("shows temperatures with units, validity, data stand and provenance", () => {
    const hint = buildSpotConditionHints(spot(), forecast()).find((item) => item.id === "temperature");
    expect(hint?.sentence).toBe("Voraussichtlich 8 °C Lufttemperatur und 15 °C Wassertemperatur.");
    expect(hint?.sourceLabel).toBe("Vorhersage");
    expect(hint?.timing).toContain("Gültig:");
    expect(hint?.timing).toContain("Datenstand:");
  });

  it("does not show a wind hint unless the forecast classifies it as offshore", () => {
    const hints = buildSpotConditionHints(spot(), forecast({ coastal_classification: "onshore" }));
    expect(hints.some((hint) => hint.kind === "wind")).toBe(false);
  });

  it("states rocky ground without inventing an entry hazard", () => {
    const hint = buildSpotConditionHints(spot({ bottomType: ["rock"] }), null)[0];
    expect(hint.sentence).toBe("Laut Spotprofil felsiger Untergrund.");
    expect(hint.sentence.toLowerCase()).not.toContain("einstieg");
    expect(hint.sourceLabel).toBe("Geprüftes Spotprofil");
  });
});
