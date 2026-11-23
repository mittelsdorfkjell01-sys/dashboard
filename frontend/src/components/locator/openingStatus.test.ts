import { describe, expect, it } from "vitest";
import { openingState, parseOpeningHours } from "./openingStatus";

// 2026-11-18 is a Wednesday. Times are UTC; Europe/Berlin is UTC+1 in November.
const at = (iso: string) => new Date(iso);
const BERLIN = "Europe/Berlin";

describe("openingState", () => {
  it("reads weekday ranges at the spot's local time", () => {
    expect(openingState("Mo-Su 12:00-19:00", at("2026-11-18T12:30:00Z"), BERLIN)).toBe("open"); // 13:30
    expect(openingState("Mo-Su 12:00-19:00", at("2026-11-18T18:30:00Z"), BERLIN)).toBe("closed"); // 19:30
    // Same instant, a spot in Lisbon (UTC+0) is still before opening.
    expect(openingState("Mo-Su 12:00-19:00", at("2026-11-18T11:30:00Z"), "Europe/Lisbon")).toBe("closed");
    expect(openingState("Mo-Su 12:00-19:00", at("2026-11-18T11:30:00Z"), BERLIN)).toBe("open");
  });

  it("lets a later rule override an earlier one for its days", () => {
    const raw = "Mo-Fr 10:00-17:00; We off; Sa,Su 10:00-18:00";
    expect(openingState(raw, at("2026-11-18T11:00:00Z"), BERLIN)).toBe("closed"); // Wednesday
    expect(openingState(raw, at("2026-11-19T11:00:00Z"), BERLIN)).toBe("open"); // Thursday
  });

  it("handles ranges across the week end and times past midnight", () => {
    expect(openingState("Th-Tu 11:00-24:00", at("2026-11-18T12:00:00Z"), BERLIN)).toBe("closed"); // Wednesday
    expect(openingState("Th-Tu 11:00-24:00", at("2026-11-17T22:30:00Z"), BERLIN)).toBe("open"); // Tue 23:30
    expect(openingState("Fr 22:00-02:00", at("2026-11-21T00:30:00Z"), BERLIN)).toBe("open"); // Sat 01:30
    expect(openingState("Fr 22:00-02:00", at("2026-11-21T01:30:00Z"), BERLIN)).toBe("closed"); // Sat 02:30
  });

  it("knows 24/7, split days and the PH prefix on weekdays", () => {
    expect(openingState("24/7", at("2026-11-18T03:00:00Z"), BERLIN)).toBe("open");
    expect(openingState("Mo-Fr 08:00-12:00, 14:00-18:00", at("2026-11-18T12:00:00Z"), BERLIN)).toBe("closed"); // 13:00
    expect(openingState("PH,Mo-Su 12:00-18:00", at("2026-11-18T12:00:00Z"), BERLIN)).toBe("open");
  });

  it("says nothing when it cannot be sure", () => {
    const now = at("2026-11-18T18:00:00Z"); // 19:00
    expect(openingState("Mo-Su 16:00+", now, BERLIN)).toBeNull();
    expect(openingState("Mo-Su 16:00+", at("2026-11-18T10:00:00Z"), BERLIN)).toBe("closed");
    expect(openingState("Mo-Fr 12:00-18:00+", now, BERLIN)).toBeNull();
    expect(openingState("Apr-Oct Mo-Su 10:00-18:00", now, BERLIN)).toBeNull();
    expect(openingState("Mo-Fr 10:00-18:00; PH off", now, BERLIN)).toBeNull();
    expect(openingState("Mo-Fr 10:00-18:00; SH Mo-Su 09:00-20:00", now, BERLIN)).toBeNull();
    expect(openingState("Mo-Su sunrise-sunset", now, BERLIN)).toBeNull();
    expect(openingState("nach Vereinbarung", now, BERLIN)).toBeNull();
    expect(openingState("Mo-Su 10:00-18:00", now, null)).toBeNull();
    expect(openingState("Mo-Su 10:00-18:00", now, "Not/AZone")).toBeNull();
    expect(openingState(null, now, BERLIN)).toBeNull();
  });

  it("treats days no rule mentions as closed", () => {
    expect(parseOpeningHours("Mo,Th-Su 11:00-17:00")?.[2]).toEqual([]);
    expect(openingState("Mo,Th-Su 11:00-17:00", at("2026-11-18T12:00:00Z"), BERLIN)).toBe("closed");
  });
});
