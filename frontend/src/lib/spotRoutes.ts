import type { Spot } from "./types";

/** A readable URL component used as a legacy fallback for records without a slug. */
export function spotNameSegment(name: string): string {
  return name
    .normalize("NFKC")
    .trim()
    .replace(/[’']/g, "-")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
}

export function spotPath(
  spot: Pick<Spot, "name"> & Partial<Pick<Spot, "id" | "slug">>,
  tab: "info" | "daten" = "info",
): string {
  // Catalogue slugs are stable and unique. Display-name routes lose meaningful
  // punctuation (for example "Agios Georgios / Laguna") and can become
  // impossible for the API to resolve after a reload. Account favourites do
  // not currently carry the slug, so their UUID is the equally stable fallback.
  const reference = spot.slug?.trim() || spot.id?.trim() || spotNameSegment(spot.name);
  return `/spot/${encodeURIComponent(reference)}/${tab}`;
}
