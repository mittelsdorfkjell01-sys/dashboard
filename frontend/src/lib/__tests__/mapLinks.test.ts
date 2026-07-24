import { describe, it, expect, vi, afterEach } from "vitest";
import { geoUri, googleMapsUrl, formatCoords, mapLinkProps, haversineKm, coloredTileUrl } from "../mapLinks";

describe("geoUri / googleMapsUrl", () => {
  it("builds a geo: URI with a redundant q= (for handlers that ignore the bare coords)", () => {
    expect(geoUri(41.18, 9.32)).toBe("geo:41.18,9.32?q=41.18,9.32");
  });

  it("builds a Google Maps search URL", () => {
    expect(googleMapsUrl(41.18, 9.32)).toBe(
      "https://www.google.com/maps/search/?api=1&query=41.18,9.32"
    );
  });
});

describe("formatCoords", () => {
  it("formats to 4 decimal places", () => {
    expect(formatCoords(41.18, 9.32)).toBe("41.1800, 9.3200");
  });
});

describe("mapLinkProps", () => {
  const setUserAgent = (ua: string) =>
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(ua);

  afterEach(() => vi.restoreAllMocks());

  it("uses geo: in place on iOS", () => {
    setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)");
    const props = mapLinkProps(41.18, 9.32);
    expect(props.href).toBe("geo:41.18,9.32?q=41.18,9.32");
    expect(props.target).toBeUndefined();
  });

  it("uses geo: in place on Android", () => {
    setUserAgent("Mozilla/5.0 (Linux; Android 14)");
    expect(mapLinkProps(41.18, 9.32).href).toBe("geo:41.18,9.32?q=41.18,9.32");
  });

  it("falls back to Google Maps in a new tab on desktop", () => {
    setUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)");
    const props = mapLinkProps(41.18, 9.32);
    expect(props.href).toBe("https://www.google.com/maps/search/?api=1&query=41.18,9.32");
    expect(props.target).toBe("_blank");
    expect(props.rel).toBe("noopener noreferrer");
  });
});

describe("haversineKm", () => {
  it("is zero for the same point", () => {
    expect(haversineKm([54.4, 11.2], [54.4, 11.2])).toBeCloseTo(0, 5);
  });

  it("matches the ~111 km/degree-of-latitude rule of thumb", () => {
    expect(haversineKm([0, 0], [1, 0])).toBeCloseTo(111.2, 0);
  });
});

describe("coloredTileUrl", () => {
  // Tarifa, Spain — daytime and nighttime UTC instants, same as sunTimes.test.ts.
  const TARIFA: [number, number] = [36.0, -5.6];
  const NOON_SUMMER = new Date(Date.UTC(2026, 6, 15, 12, 0, 0));
  const MIDNIGHT_SUMMER = new Date(Date.UTC(2026, 6, 15, 0, 0, 0));

  it("is the single world tile at zoom 0, for any coordinate", () => {
    expect(coloredTileUrl(TARIFA[0], TARIFA[1], 0, NOON_SUMMER)).toMatch(/\/0\/0\/0\.png$/);
    expect(coloredTileUrl(-33.9, 151.2, 0, NOON_SUMMER)).toMatch(/\/0\/0\/0\.png$/);
  });

  it("uses standard z/x/y path order", () => {
    const url = coloredTileUrl(TARIFA[0], TARIFA[1], 5, NOON_SUMMER);
    expect(url).toMatch(/\/(voyager|dark_all)\/5\/\d+\/\d+\.png$/);
  });

  it("picks the day tile by day and the night tile by night, at the same coordinate", () => {
    expect(coloredTileUrl(TARIFA[0], TARIFA[1], 8, NOON_SUMMER)).toContain("/voyager/");
    expect(coloredTileUrl(TARIFA[0], TARIFA[1], 8, MIDNIGHT_SUMMER)).toContain("/dark_all/");
  });
});
