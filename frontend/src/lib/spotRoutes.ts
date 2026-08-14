import type { Spot } from "./types";

/** A readable URL component derived only from the public spot name. */
export function spotNameSegment(name: string): string {
  return name
    .normalize("NFKC")
    .trim()
    .replace(/[’']/g, "-")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
}

export function spotPath(
  spot: Pick<Spot, "name">,
  tab: "info" | "daten" = "info",
): string {
  return `/spot/${encodeURIComponent(spotNameSegment(spot.name))}/${tab}`;
}
