import { describe, expect, it } from "vitest";
import { hasResponsiveHeroDelivery, selectLandingHeroSlides } from "../LandingHero";
import type { Spot } from "../../lib/types";

function spot(id: string, overrides: Partial<Spot> = {}): Spot {
  return {
    id,
    name: `Spot ${id}`,
    region: "Testregion",
    wind: 0,
    tags: [],
    image: `/hero-${id}.jpg`,
    hero: `/hero-${id}.jpg`,
    ...overrides,
  };
}

describe("selectLandingHeroSlides", () => {
  it("includes only hero images explicitly selected in the admin reel", () => {
    const slides = selectLandingHeroSlides([
      spot("selected", { heroReel: true }),
      spot("not-selected", { heroReel: false }),
      spot("legacy-without-flag"),
    ]);

    expect(slides.map((slide) => slide.id)).toEqual(["selected"]);
  });

  it("returns an empty reel when no image is selected", () => {
    expect(selectLandingHeroSlides([spot("a"), spot("b", { heroReel: false })])).toEqual([]);
  });

  it("ignores selected spots without a usable hero and caps the reel", () => {
    const selected = Array.from({ length: 14 }, (_, index) =>
      spot(String(index), { heroReel: true }),
    );
    selected.unshift(spot("missing-image", { hero: undefined, heroReel: true }));

    const slides = selectLandingHeroSlides(selected);

    expect(slides).toHaveLength(12);
    expect(slides.some((slide) => slide.id === "missing-image")).toBe(false);
  });
});

describe("hasResponsiveHeroDelivery", () => {
  it("accepts hosted responsive sets and resizable provider URLs", () => {
    expect(hasResponsiveHeroDelivery(spot("hosted", {
      hero: "/media/images/hash-responsive-480_1280.avif",
      heroWidth: 1920,
      heroDelivery: "hosted",
    }))).toBe(true);
    expect(hasResponsiveHeroDelivery(spot("unsplash", {
      hero: "https://images.unsplash.com/photo-123",
      heroDelivery: "hotlinked",
      heroCredit: { provider: "unsplash" },
    }))).toBe(true);
  });

  it("rejects legacy full-size hosted heroes from the landing LCP", () => {
    expect(hasResponsiveHeroDelivery(spot("legacy", {
      hero: "/media/spots/legacy/hero-old.avif",
      heroWidth: 3840,
      heroDelivery: "hosted",
    }))).toBe(false);
  });
});
