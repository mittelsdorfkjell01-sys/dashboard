import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { headlineWaveFromDeg, headlineWaveM, headlineWavePeriodS, primarySwell } from "../waveReading";
import { SizedWaveIcon, WAVE_PATH, waveStage } from "../icons";
import { tempColor, tempTone } from "../tempScale";

describe("wave readings (Daten wave focus and map tile)", () => {
  it("takes height, period and direction from the total wave first", () => {
    const hour = {
      swell: 0.4,
      period: 6,
      swell_dir: 200,
      waves: {
        total_wave: { significant_height_m: 1.3, peak_period_s: 9.5, mean_period_s: 7.2, peak_direction_from_deg: 285, mean_direction_from_deg: 280 },
        primary_wave: { significant_height_m: 1.1, peak_period_s: 11, peak_direction_from_deg: 300 },
      },
    };
    expect(headlineWaveM(hour)).toBe(1.3);
    expect(headlineWavePeriodS(hour)).toBe(9.5);
    expect(headlineWaveFromDeg(hour)).toBe(285);
  });

  it("falls back step by step: mean values, then the primary wave, then the legacy fields", () => {
    expect(headlineWavePeriodS({ waves: { total_wave: { significant_height_m: 1, mean_period_s: 7 } } })).toBe(7);
    expect(headlineWaveFromDeg({ waves: { total_wave: { significant_height_m: 1, mean_direction_from_deg: 270 } } })).toBe(270);
    // NOAA publishes period and direction on the primary wave only.
    const noaa = { waves: { total_wave: { significant_height_m: 1 }, primary_wave: { significant_height_m: 1, peak_period_s: 12, mean_direction_from_deg: 310 } } };
    expect(headlineWavePeriodS(noaa)).toBe(12);
    expect(headlineWaveFromDeg(noaa)).toBe(310);
    const legacy = { swell: 0.8, period: 8, swell_dir: 240 };
    expect(headlineWaveM(legacy)).toBe(0.8);
    expect(headlineWavePeriodS(legacy)).toBe(8);
    expect(headlineWaveFromDeg(legacy)).toBe(240);
  });

  it("keeps a missing reading missing instead of borrowing another component", () => {
    const seaOnly = { waves: { wind_sea: { significant_height_m: 0.6, peak_period_s: 4, peak_direction_from_deg: 90 } } };
    expect(headlineWaveM(seaOnly)).toBeNull();
    expect(headlineWavePeriodS(seaOnly)).toBeNull();
    expect(headlineWaveFromDeg(seaOnly)).toBeNull();
    expect(headlineWaveM(null)).toBeNull();
    expect(headlineWavePeriodS(undefined)).toBeNull();
    expect(headlineWaveFromDeg(null)).toBeNull();
  });

  it("reads the primary swell partition, or nothing when the model has none", () => {
    expect(primarySwell({ waves: { primary_swell: { significant_height_m: 1.2, peak_period_s: 11, mean_direction_from_deg: 295 } } }))
      .toEqual({ heightM: 1.2, periodS: 11, fromDeg: 295 });
    expect(primarySwell({ waves: { primary_swell: { significant_height_m: 0.9, mean_period_s: 8, peak_direction_from_deg: 300 } } }))
      .toEqual({ heightM: 0.9, periodS: 8, fromDeg: 300 });
    expect(primarySwell({ waves: { primary_swell: { significant_height_m: 0.5 } } }))
      .toEqual({ heightM: 0.5, periodS: null, fromDeg: null });
    expect(primarySwell({ waves: { primary_swell: { significant_height_m: null } } })).toBeNull();
    expect(primarySwell({ swell: 1 })).toBeNull();
    expect(primarySwell(null)).toBeNull();
  });
});

describe("wave mark by height", () => {
  it("has five stages on a fixed scale", () => {
    expect(waveStage(0)).toBe(0);
    expect(waveStage(0.49)).toBe(0);
    expect(waveStage(0.5)).toBe(1);
    expect(waveStage(1.2)).toBe(2);
    expect(waveStage(2)).toBe(3);
    expect(waveStage(3)).toBe(4);
    expect(waveStage(8)).toBe(4);
  });

  it("grows a little with each stage and draws the house wave from 2 m", () => {
    const sizes = [0.2, 0.7, 1.5, 2.5, 3.5].map((height) => {
      const html = renderToStaticMarkup(<SizedWaveIcon heightM={height} />);
      return Number(/width="(\d+)"/.exec(html)?.[1]);
    });
    expect(sizes).toEqual([17, 19, 21, 23, 26]);
    expect(renderToStaticMarkup(<SizedWaveIcon heightM={0.2} />)).not.toContain(WAVE_PATH);
    expect(renderToStaticMarkup(<SizedWaveIcon heightM={2.4} />)).toContain(WAVE_PATH);
    // From 3 m the crest carries spray: one more path than at 2 m.
    const paths = (height: number) => (renderToStaticMarkup(<SizedWaveIcon heightM={height} />).match(/<path/g) ?? []).length;
    expect(paths(3.5)).toBe(paths(2.4) + 1);
  });
});

describe("temperature tone", () => {
  it("mixes the scale colour toward ink by the theme's share", () => {
    const tone = tempTone(18);
    expect(tone).toContain(tempColor(18));
    expect(tone).toContain("var(--sw-temp-ink-mix, 0%)");
    expect(tone.startsWith("color-mix(in srgb,")).toBe(true);
  });
});
