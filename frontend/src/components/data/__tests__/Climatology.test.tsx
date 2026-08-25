import { describe, expect, it } from "vitest";
import { metricValue } from "../Climatology";
import type { WindClimatologySection } from "../../../lib/api";

const section = {
  section: 1, month: 1, day_start: 1, day_end: 7,
  windows: {
    "10_15": { hours: 0, percent: 0, hours_per_day: 0 },
    "15_20": { hours: 10, percent: 25, hours_per_day: 0.5 },
    "20_30": { hours: 0, percent: Number.NaN, hours_per_day: Number.POSITIVE_INFINITY },
    "30_plus": { hours: 0, percent: 0, hours_per_day: 0 },
  },
} as WindClimatologySection;

describe("Climatology metric hardening", () => {
  it("preserves a real zero so it can render as a visible zero marker", () => {
    expect(metricValue(section, "10_15", "percent")).toBe(0);
    expect(metricValue(section, "10_15", "hours")).toBe(0);
  });

  it("treats invalid metrics as unavailable instead of producing NaN CSS heights", () => {
    expect(metricValue(section, "20_30", "percent")).toBeNull();
    expect(metricValue(section, "20_30", "hours")).toBeNull();
  });
});
