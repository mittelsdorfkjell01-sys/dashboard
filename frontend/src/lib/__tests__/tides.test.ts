import { describe, expect, it } from "vitest";
import { formatTideTime, isoToSpotLocalInput, spotLocalInputToIso } from "../tideTime";

describe("formatTideTime", () => {
  it("uses the spot timezone across the European DST jump", () => {
    expect(formatTideTime("2026-03-29T00:30:00Z", "Europe/Berlin", 10).time)
      .toBe("ca. 01:30");
    expect(formatTideTime("2026-03-29T01:30:00Z", "Europe/Berlin", 10).time)
      .toBe("ca. 03:30");
  });

  it("shows a window for elevated uncertainty", () => {
    expect(formatTideTime("2026-08-06T12:20:00Z", "UTC", 20).time)
      .toBe("ca. 12:00–12:40");
  });

  it("round-trips a spot-local time independent of the browser timezone", () => {
    const iso = spotLocalInputToIso("2026-08-06T14:20", "Europe/Berlin");
    expect(iso).toBe("2026-08-06T12:20:00.000Z");
    expect(isoToSpotLocalInput(iso, "Europe/Berlin")).toBe("2026-08-06T14:20");
  });

  it("rejects a nonexistent local time during the DST jump", () => {
    expect(() => spotLocalInputToIso("2026-03-29T02:30", "Europe/Berlin"))
      .toThrow("Zeitumstellung");
  });
});
