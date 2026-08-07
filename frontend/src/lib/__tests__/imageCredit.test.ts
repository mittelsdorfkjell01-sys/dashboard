import { describe, expect, it } from "vitest";
import {
  UNSPLASH_UTM,
  creditParts,
  fromGalleryPhoto,
  fromImageRecord,
  hasCredit,
  withUnsplashUtm,
} from "../imageCredit";
import { CDN_WIDTHS, hotlinkSrcSet, objectPosition, unsplashSized } from "../heroSource";
import type { ImageRecord } from "../api";

function image(overrides: Partial<ImageRecord> = {}): ImageRecord {
  return {
    url: "https://images.unsplash.com/photo-1",
    source: "Unsplash",
    license: "Unsplash License",
    license_url: "https://unsplash.com/license",
    credit: "Sam Rivera",
    credit_url: "https://unsplash.com/@sam",
    provider: "unsplash",
    source_page: "https://unsplash.com/photos/abc",
    delivery: "hotlinked",
    ...overrides,
  };
}

describe("credit parts", () => {
  it("reads photographer, provider and licence in that order", () => {
    const parts = creditParts(fromImageRecord(image()));
    expect(parts.map((p) => p.key)).toEqual(["photographer", "provider", "license"]);
    expect(parts[0].label).toBe("Sam Rivera");
    expect(parts[1].label).toBe("Unsplash");
    expect(parts[2].label).toBe("Unsplash License");
  });

  it("links each part to where it belongs", () => {
    const parts = creditParts(fromImageRecord(image()));
    expect(parts[0].href).toContain("unsplash.com/@sam");
    expect(parts[1].href).toContain("unsplash.com/photos/abc");
    expect(parts[2].href).toBe("https://unsplash.com/license");
  });

  it("omits parts that have nothing to say rather than rendering them empty", () => {
    const parts = creditParts(
      fromImageRecord(image({ credit_url: null, source_page: null, license_url: null }))
    );
    expect(parts).toHaveLength(3);
    expect(parts.every((p) => p.href === undefined)).toBe(true);
  });

  it("hides our internal upload markers, which are not public licences", () => {
    // A community hero stores the consent version ("v1"); an admin upload
    // stores "own". Printing those next to a name would be noise.
    const consent = creditParts(
      fromImageRecord(image({ provider: "community", license: "v1", credit: "@kitekai" }))
    );
    expect(consent.map((p) => p.key)).toEqual(["photographer", "provider"]);
    expect(consent[0].label).toBe("@kitekai");

    const own = creditParts(fromImageRecord(image({ provider: "upload", license: "own" })));
    expect(own.map((p) => p.key)).not.toContain("license");
  });

  it("still credits a public-domain photo, though nothing requires it", () => {
    const parts = creditParts(
      fromImageRecord(
        image({ provider: "wikimedia", license: "CC0", credit: "Hist. Archive" })
      )
    );
    expect(parts.map((p) => p.label)).toEqual([
      "Hist. Archive",
      "Wikimedia Commons",
      "CC0",
    ]);
  });

  it("returns nothing for a missing image", () => {
    expect(fromImageRecord(null)).toBeNull();
    expect(creditParts(null)).toEqual([]);
    expect(hasCredit(null)).toBe(false);
  });

  it("renders a gallery row through the same path as a hero", () => {
    const parts = creditParts(
      fromGalleryPhoto({
        credit: "Ana Ruiz",
        source: "wikimedia_commons",
        license_name: "CC BY-SA 4.0",
        license_url: "https://creativecommons.org/licenses/by-sa/4.0",
        source_url: "https://commons.wikimedia.org/wiki/File:X.jpg",
      })
    );
    expect(parts.map((p) => p.label)).toEqual([
      "Ana Ruiz",
      "Wikimedia Commons",
      "CC BY-SA 4.0",
    ]);
  });

  it("labels a community upload as Community, not as its internal slug", () => {
    const parts = creditParts(
      fromGalleryPhoto({ credit: "@surferin", source: "user_upload" })
    );
    expect(parts.map((p) => p.label)).toEqual(["@surferin", "Community"]);
  });
});

describe("unsplash referral parameters", () => {
  it("adds them to Unsplash links", () => {
    expect(withUnsplashUtm("https://unsplash.com/@sam", "unsplash")).toBe(
      `https://unsplash.com/@sam?${UNSPLASH_UTM}`
    );
  });

  it("appends to an existing query string", () => {
    expect(withUnsplashUtm("https://unsplash.com/x?a=1", "unsplash")).toBe(
      `https://unsplash.com/x?a=1&${UNSPLASH_UTM}`
    );
  });

  it("does not double up when the server already added them", () => {
    const already = `https://unsplash.com/@sam?${UNSPLASH_UTM}`;
    expect(withUnsplashUtm(already, "unsplash")).toBe(already);
  });

  it("leaves other providers alone", () => {
    expect(withUnsplashUtm("https://www.pexels.com/@marta", "pexels")).toBe(
      "https://www.pexels.com/@marta"
    );
  });
});

describe("hotlinked delivery", () => {
  it("resizes through the Unsplash CDN instead of shipping the original", () => {
    const srcset = hotlinkSrcSet("https://images.unsplash.com/photo-1", "unsplash");
    expect(srcset).toBeDefined();
    for (const width of CDN_WIDTHS) {
      expect(srcset).toContain(`w=${width}`);
      expect(srcset).toContain(`${width}w`);
    }
  });

  it("never upscales", () => {
    expect(unsplashSized("https://images.unsplash.com/p", 1600)).toContain("fit=max");
  });

  it("keeps an existing query string intact", () => {
    const sized = unsplashSized("https://images.unsplash.com/p?ixid=abc", 800);
    expect(sized).toContain("ixid=abc");
    expect(sized).toContain("&w=800");
  });

  it("gives up rather than guessing another CDN's parameter names", () => {
    expect(hotlinkSrcSet("https://images.pexels.com/p.jpg", "pexels")).toBeUndefined();
    expect(hotlinkSrcSet("https://example.com/p.jpg", null)).toBeUndefined();
  });
});

describe("focal point", () => {
  it("becomes an object-position the browser understands", () => {
    expect(objectPosition({ x: 30, y: 70 })).toBe("30% 70%");
  });

  it("is absent when no focal point was chosen", () => {
    expect(objectPosition(null)).toBeUndefined();
    expect(objectPosition(undefined)).toBeUndefined();
  });
});
