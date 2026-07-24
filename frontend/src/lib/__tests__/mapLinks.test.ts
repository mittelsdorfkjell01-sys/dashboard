import { describe, it, expect, vi, afterEach } from "vitest";
import { geoUri, googleMapsUrl, formatCoords, mapLinkProps, haversineKm, satelliteTileUrl } from "../mapLinks";

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

describe("satelliteTileUrl", () => {
  it("is the single world tile at zoom 0, for any coordinate", () => {
    expect(satelliteTileUrl(41.18, 9.32, 0)).toBe(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/0/0/0"
    );
    expect(satelliteTileUrl(-33.9, 151.2, 0)).toBe(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/0/0/0"
    );
  });

  it("uses Esri's z/y/x path order", () => {
    const url = satelliteTileUrl(54.4, 11.2, 5);
    expect(url).toMatch(/\/tile\/5\/\d+\/\d+$/);
  });
});
