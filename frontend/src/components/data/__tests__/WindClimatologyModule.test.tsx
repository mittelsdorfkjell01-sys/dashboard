import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import {
  WeekChart,
  WeekBar,
  WeekDetail,
  selectionFromUrl,
  normalizeSelection,
  reliabilityBand,
  groupByMonth,
  formatMonthDayRange,
} from "../WindClimatologyModule";
import type { WindClimatologyV3Week } from "../../../lib/api";

function week(index: number, overrides: Partial<WindClimatologyV3Week> = {}): WindClimatologyV3Week {
  const monthDay = new Date(2000, 0, 1 + index * 7);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    week: index + 1,
    date_range: { start: `${pad(monthDay.getMonth() + 1)}-${pad(monthDay.getDate())}`, end: `${pad(monthDay.getMonth() + 1)}-${pad(monthDay.getDate() + 6)}` },
    sample_years: 19,
    successful_years: 10,
    reliability_percent: index === 0 ? 0 : 55,
    reliability_low_percent: 34,
    reliability_high_percent: 74,
    probability_at_least_1_day: 80,
    probability_at_least_2_days: 55,
    probability_at_least_3_days: 20,
    median_usable_days: 2,
    median_session_hours: 8,
    p25_session_hours: 4,
    p75_session_hours: 12,
    median_longest_session: 4,
    quality_status: "high",
    ...overrides,
  };
}

const weeks52 = Array.from({ length: 52 }, (_, i) => week(i));

describe("WindClimatologyModule pure helpers", () => {
  it("parses only valid URL params and ignores the rest", () => {
    const params = new URLSearchParams("wind_min=15&wind_max=plus&wind_dir=usable");
    expect(selectionFromUrl(params)).toEqual({ minWindKn: 15, maxWindKn: null, directionMode: "usable" });
    expect(selectionFromUrl(new URLSearchParams("wind_min=abc&wind_dir=bogus"))).toEqual({});
  });

  it("normalizes out-of-range and crossed bounds to valid values", () => {
    expect(normalizeSelection({})).toEqual({ minWindKn: 15, maxWindKn: 20, directionMode: "all" });
    expect(normalizeSelection({ minWindKn: 2, maxWindKn: 1 })).toEqual({ minWindKn: 5, maxWindKn: 6, directionMode: "all" });
    expect(normalizeSelection({ minWindKn: 30, maxWindKn: 41 })).toEqual({ minWindKn: 30, maxWindKn: null, directionMode: "all" });
    expect(normalizeSelection({ minWindKn: 39, maxWindKn: 40 })).toEqual({ minWindKn: 39, maxWindKn: null, directionMode: "all" });
  });

  it("maps reliability percent to the four documented bands", () => {
    expect(reliabilityBand(null)).toBe(0);
    expect(reliabilityBand(0)).toBe(0);
    expect(reliabilityBand(29)).toBe(0);
    expect(reliabilityBand(30)).toBe(1);
    expect(reliabilityBand(49)).toBe(1);
    expect(reliabilityBand(50)).toBe(2);
    expect(reliabilityBand(69)).toBe(2);
    expect(reliabilityBand(70)).toBe(3);
    expect(reliabilityBand(100)).toBe(3);
  });

  it("groups all 52 weeks into 12 months without dropping or duplicating a week", () => {
    const groups = groupByMonth(weeks52);
    expect(groups).toHaveLength(12);
    const total = groups.reduce((sum, g) => sum + g.length, 0);
    expect(total).toBe(52);
    // every group has 4 or 5 weeks (never a forced 4-per-month split)
    for (const g of groups) expect(g.length === 0 || g.length === 4 || g.length === 5).toBe(true);
  });

  it("formats a month/day range without a year", () => {
    expect(formatMonthDayRange("07-15", "07-21")).toBe("15.–21. Juli");
    expect(formatMonthDayRange("07-29", "08-04")).toBe("29. Juli – 4. August");
  });
});

describe("WeekChart", () => {
  it("renders exactly 52 unmodified bars with no smoothing", () => {
    const html = renderToStaticMarkup(
      <WeekChart weeks={weeks52} monthGroups={groupByMonth(weeks52)} currentWeek={1} selectedWeek={2} onSelect={() => undefined} scrollerRef={{ current: null }} />,
    );
    expect((html.match(/data-week=/g) ?? []).length).toBe(52);
    expect(html).toContain('role="slider"');
    expect(html).toContain("0–29 %");
    expect(html).toContain("Aktuelle Woche");
  });

  it("flags a payload that does not contain exactly 52 weeks instead of rendering a malformed chart", () => {
    const broken = weeks52.slice(0, 51);
    const html = renderToStaticMarkup(
      <WeekChart weeks={broken} monthGroups={groupByMonth(broken)} currentWeek={1} selectedWeek={1} onSelect={() => undefined} scrollerRef={{ current: null }} />,
    );
    expect(html).toContain('role="alert"');
  });
});

describe("WeekBar", () => {
  it("renders a real zero as a solid baseline, not as missing data", () => {
    const html = renderToStaticMarkup(<WeekBar week={week(0, { reliability_percent: 0 })} isCurrent={false} isSelected={false} />);
    expect(html).toContain("bg-reliability-0");
    expect(html).not.toContain("border-dashed");
  });

  it("renders insufficient-quality (null) weeks as a distinct missing-data marker, never as a zero bar", () => {
    const html = renderToStaticMarkup(<WeekBar week={week(0, { reliability_percent: null, quality_status: "insufficient" })} isCurrent={false} isSelected={false} />);
    expect(html).toContain("border-dashed");
    expect(html).not.toContain("bg-reliability-0");
  });

  it("marks the selected week without turning every bar into a tab stop", () => {
    const html = renderToStaticMarkup(<WeekBar week={week(3)} isCurrent={false} isSelected />);
    expect(html).toContain("ring-inset");
    expect(html).not.toContain("tabindex");
  });
});

describe("WeekDetail", () => {
  it("translates raw API field names into plain-language labels and shows the active window", () => {
    const html = renderToStaticMarkup(
      <WeekDetail week={week(10, { reliability_percent: 68 })} selection={{ min_wind_kn: 15, max_wind_kn: 20, direction_mode: "usable" }} />,
    );
    expect(html).toContain("68%");
    expect(html).toContain("15–20 kt");
    expect(html).toContain("passende Richtung");
    expect(html).not.toContain("reliability_percent");
    expect(html).not.toContain("median_session_hours");
  });
});
