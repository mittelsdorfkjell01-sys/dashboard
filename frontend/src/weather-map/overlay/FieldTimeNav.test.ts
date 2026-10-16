import { describe, expect, it } from "vitest";
import { dayDomain, fieldWindow, hourMarks, nearestTime, selectableDays, FIELD_DAYS } from "./FieldTimeNav";

const iso = (hoursFromNow: number, now: number) => new Date(now + hoursFromNow * 3_600_000).toISOString();

describe("field time window", () => {
  const now = Date.parse("2026-10-11T12:00:00Z");

  it("offers the next ten days and nothing beyond them", () => {
    const times = [-48, -2, 0, 24, FIELD_DAYS * 24 - 1, FIELD_DAYS * 24 + 6].map((hours) => iso(hours, now));
    const window = fieldWindow(times, now);

    expect(window).toEqual([times[2], times[3], times[4]]);
  });

  it("keeps the hour just behind now, so 'now' never falls out between runs", () => {
    const times = [iso(-0.5, now), iso(3, now)];
    expect(fieldWindow(times, now)).toEqual(times);
  });

  it("returns the instants in order, whatever the manifest's order", () => {
    const times = [iso(6, now), iso(0, now), iso(3, now)];
    expect(fieldWindow(times, now)).toEqual([times[1], times[2], times[0]]);
  });

  it("keeps a wholly out-of-window publication rather than going blank", () => {
    // A stale run (or a fixture from another week) still gets drawn: an empty
    // window would leave the map with no field at all.
    const stale = [iso(-200, now), iso(-197, now)];
    expect(fieldWindow(stale, now)).toEqual(stale);
  });

  it("finds the instant closest to a target in either direction", () => {
    const times = [iso(0, now), iso(3, now), iso(6, now)];
    expect(nearestTime(times, now + 2.6 * 3_600_000)).toBe(times[1]);
    expect(nearestTime(times, now - 10 * 3_600_000)).toBe(times[0]);
    expect(nearestTime([], now)).toBeUndefined();
  });
});

describe("one day per slider", () => {
  const now = new Date(2026, 9, 11, 19, 45).getTime();
  const publishedFrom = new Date(2026, 9, 11, 0, 0).getTime();
  const publishedTo = new Date(2026, 9, 16, 12, 0).getTime();
  const bounds = { nowAt: now, publishedFrom, publishedTo };

  it("starts today at now, never earlier — a forecast map does not look back", () => {
    const today = dayDomain(now, bounds)!;
    expect(today.from).toBe(now);
    expect(new Date(today.to).getDate()).toBe(11);
    expect(new Date(today.to).getHours()).toBe(23);
  });

  it("gives a later day its full midnight-to-midnight span", () => {
    const monday = new Date(2026, 9, 13, 8, 0).getTime();
    const domain = dayDomain(monday, bounds)!;
    expect(new Date(domain.from).getHours()).toBe(0);
    expect(new Date(domain.to).getHours()).toBe(23);
  });

  it("clips the last day to the end of the publication", () => {
    const last = new Date(2026, 9, 16, 3, 0).getTime();
    expect(dayDomain(last, bounds)!.to).toBe(publishedTo);
    // Beyond the horizon there is no day to offer.
    expect(dayDomain(new Date(2026, 9, 18, 3, 0).getTime(), bounds)).toBeNull();
  });

  it("offers today and four more days, cut short by the horizon", () => {
    expect(selectableDays(now, publishedTo)).toHaveLength(FIELD_DAYS);
    const shortRun = new Date(2026, 9, 13, 6, 0).getTime();
    expect(selectableDays(now, shortRun)).toHaveLength(3);
  });

  it("labels the left end of today 'jetzt' and spaces the hour marks", () => {
    const today = dayDomain(now, bounds)!;
    const marks = hourMarks(today.from, today.to, now);
    expect(marks[0].label).toBe("jetzt");
    expect(marks[0].offset).toBe(0);
    expect(marks.every((mark, index) => index === 0 || mark.offset - marks[index - 1].offset >= 0.12)).toBe(true);
  });
});

describe("hour marks at the end of the day", () => {
  it("labels the end of the track when no six-hour mark is left", () => {
    // 22:10 → the next six-hour mark (00:00) is already past the day's end.
    const from = new Date(2026, 9, 11, 22, 10).getTime();
    const to = new Date(2026, 9, 11, 23, 59).getTime();
    const marks = hourMarks(from, to, from);
    expect(marks.map((mark) => mark.label)).toEqual(["jetzt", "24:00"]);
    expect(marks[1].offset).toBe(1);
  });
});
