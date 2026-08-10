import { describe, expect, it } from "vitest";
import { weatherSectorsOverlap } from "../../pages/AdminWeatherProfile";
import type { WeatherSector } from "../api";

const sector = (start_deg: number, end_deg: number): WeatherSector => ({ start_deg, end_deg, speed_factor: 1, direction_offset_deg: 0, version: 1, enabled: true });

describe("weather profile sectors", () => {
  it("detects overlap across north", () => expect(weatherSectorsOverlap(sector(330, 20), sector(10, 40))).toBe(true));
  it("allows intentional gaps", () => expect(weatherSectorsOverlap(sector(330, 20), sector(80, 120))).toBe(false));
});
