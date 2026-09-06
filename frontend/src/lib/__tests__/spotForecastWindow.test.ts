import { describe, expect, it } from "vitest";
import type { NormalizedForecastHour } from "../forecastNormalization";
import { isSpotForecastDisplayHour } from "../spotForecastWindow";

const hour = (localTime: string): NormalizedForecastHour => {
  const [localHour, minute] = localTime.split(":").map(Number);
  return {
    utcKey: `2026-09-05T${localTime}:00.000Z`,
    time: `2026-09-05T${localTime}:00.000Z`,
    localDate: "2026-09-05",
    localTime,
    localTimeWithOffset: `${localTime} UTC`,
    localHour,
    localMinute: localHour * 60 + minute,
  } as NormalizedForecastHour;
};

describe("Spot-Daten forecast window", () => {
  it("includes exactly 17 hourly slots from 06:00 through 22:00", () => {
    const visible = Array.from({ length: 24 }, (_, value) => hour(`${String(value).padStart(2, "0")}:00`))
      .filter(isSpotForecastDisplayHour);

    expect(visible).toHaveLength(17);
    expect(visible[0].localTime).toBe("06:00");
    expect(visible[visible.length - 1]?.localTime).toBe("22:00");
    expect(isSpotForecastDisplayHour(hour("05:59"))).toBe(false);
    expect(isSpotForecastDisplayHour(hour("22:01"))).toBe(false);
  });
});
