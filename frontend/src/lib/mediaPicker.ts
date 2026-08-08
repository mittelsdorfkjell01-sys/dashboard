// Pure logic behind the admin media picker: tab order, eligibility, tile
// badges and focal-point maths.
//
// Kept out of the component on purpose. The repo's vitest setup has no DOM
// (no jsdom, no testing-library), so anything worth asserting lives here as a
// plain function and the component keeps only rendering and wiring.

export type MediaRole = "hero" | "gallery";
export type MediaEntityType = "spot" | "region";

export type ProviderKey =
  | "nearby"
  | "unsplash"
  | "pexels"
  | "wikimedia"
  | "openverse";

export interface MediaLicense {
  name: string;
  url: string | null;
  commercial: boolean;
  modification: boolean;
}

export interface MediaCredit {
  name: string;
  url: string | null;
}

export interface MediaUsageRef {
  entity_type: MediaEntityType;
  entity_id: string;
  name: string;
  role: MediaRole;
}

export interface MediaItem {
  provider: string;
  external_id: string;
  thumb_url: string;
  preview_url: string;
  full_url: string;
  width: number | null;
  height: number | null;
  license: MediaLicense;
  credit: MediaCredit;
  source_page: string | null;
  delivery: "hotlinked" | "hosted";
  geo_verified: boolean;
  hero_eligible: boolean;
  gallery_eligible: boolean;
  used_by: MediaUsageRef[];
  unsplash_download_location: string | null;
}

export type TabStatus = "ok" | "disabled" | "budget_exhausted" | "error";

export interface TabState {
  status: TabStatus;
  items: MediaItem[];
  total: number;
  loading: boolean;
  message?: string | null;
  budget?: { used: number; limit: number; exhausted: boolean; warning: boolean } | null;
}

export const PROVIDER_LABEL: Record<ProviderKey, string> = {
  nearby: "Vor Ort",
  unsplash: "Unsplash",
  pexels: "Pexels",
  wikimedia: "Wikimedia",
  openverse: "Openverse",
};

/**
 * Tab order per entity type — the only structural difference between the spot
 * and the region picker.
 *
 * Spots lead with Unsplash because a spot hero wants an action photo, and
 * that is what the stock libraries are full of. Regions lead with Wikimedia
 * because a region hero wants the actual place, and Commons is where
 * geotagged landscape photography of real coastlines lives.
 */
export function tabOrder(entityType: MediaEntityType): ProviderKey[] {
  return entityType === "region"
    ? ["nearby", "wikimedia", "unsplash", "pexels", "openverse"]
    : ["nearby", "unsplash", "pexels", "wikimedia", "openverse"];
}

/** Whether this result can be adopted in the currently active mode.
 *
 * Historically enforced the size gate here too, but the admin sees the
 * dimensions on the tile and takes responsibility for choosing an image
 * that is smaller than the hero recommendation. Now returns true for any
 * result the server has already licence-cleared; size becomes an
 * advisory badge on the tile and a warning on the adopt response. */
export function isUsable(_item: MediaItem, _role: MediaRole): boolean {
  return true;
}

export type TileBadgeTone = "neutral" | "warning" | "info";

export interface TileBadge {
  label: string;
  tone: TileBadgeTone;
  title?: string;
}

/**
 * The badge strip on a tile.
 *
 * Everything here answers a question the operator would otherwise have to
 * open the image to answer: is it big enough, may I use it, is it already
 * somewhere else, does it actually show this place.
 */
export function tileBadges(item: MediaItem, role: MediaRole): TileBadge[] {
  const badges: TileBadge[] = [];

  if (item.width && item.height) {
    badges.push({ label: `${item.width}×${item.height}`, tone: "neutral" });
  }
  badges.push({
    label: item.license.name,
    tone: "neutral",
    title: item.license.url ?? undefined,
  });

  // Why a tile is dimmed, stated on the tile rather than left to be guessed.
  if (role === "hero" && !item.hero_eligible && item.gallery_eligible) {
    badges.push({ label: "nur Galerie", tone: "warning" });
  }

  if (item.used_by.length > 0) {
    const names = item.used_by.map((usage) => usage.name).join(", ");
    badges.push({
      label:
        item.used_by.length === 1
          ? `bereits genutzt bei ${item.used_by[0].name}`
          : `bereits genutzt (${item.used_by.length}×)`,
      tone: "warning",
      title: names,
    });
  }

  if (!item.geo_verified) {
    badges.push({ label: "Ortsbezug ungeprüft", tone: "info" });
  }

  return badges;
}

/**
 * Click position inside the preview → focal point in object-position percent.
 *
 * Percent, not a 0..1 pair, because that is what the stored image object, the
 * focal editor and `HeroImage`'s `objectPosition` all speak.
 */
export function focalFromPoint(
  rect: { left: number; top: number; width: number; height: number },
  clientX: number,
  clientY: number
): { x: number; y: number } {
  if (rect.width <= 0 || rect.height <= 0) return { x: 50, y: 50 };
  const x = ((clientX - rect.left) / rect.width) * 100;
  const y = ((clientY - rect.top) / rect.height) * 100;
  return {
    x: Math.round(Math.min(100, Math.max(0, x)) * 10) / 10,
    y: Math.round(Math.min(100, Math.max(0, y)) * 10) / 10,
  };
}

/**
 * Distribute items into masonry columns.
 *
 * Shortest-column-first rather than round-robin: with mixed aspect ratios,
 * round-robin leaves one column visibly longer than the rest.
 */
export function masonryColumns(items: MediaItem[], columnCount: number): MediaItem[][] {
  const count = Math.max(1, columnCount);
  const columns: MediaItem[][] = Array.from({ length: count }, () => []);
  const heights = new Array<number>(count).fill(0);

  for (const item of items) {
    const ratio =
      item.width && item.height ? item.height / item.width : 0.66;
    let shortest = 0;
    for (let i = 1; i < count; i += 1) {
      if (heights[i] < heights[shortest]) shortest = i;
    }
    columns[shortest].push(item);
    heights[shortest] += ratio;
  }
  return columns;
}

/** Aspect-ratio box for a tile, so lazy-loaded images cause no layout shift. */
export function aspectRatio(item: MediaItem): string {
  if (!item.width || !item.height) return "3 / 2";
  return `${item.width} / ${item.height}`;
}

/** Tab label with its post-filter hit count, so it is visible without
 *  clicking through where searching is worthwhile. */
export function tabLabel(provider: ProviderKey, state: TabState | undefined): string {
  const label = PROVIDER_LABEL[provider];
  if (!state || state.loading) return label;
  if (state.status === "disabled") return `${label} (—)`;
  if (state.status === "budget_exhausted") return `${label} (⏸)`;
  if (state.status === "error") return `${label} (!)`;
  return `${label} (${state.total})`;
}

/**
 * Keyboard navigation across the masonry grid.
 *
 * Arrow keys move within the flat result order rather than by column, because
 * the visual columns are a layout artefact — an operator scanning with the
 * keyboard expects the next photo, not the one below in the same column.
 */
export function nextIndex(
  current: number,
  key: string,
  total: number,
  columnCount: number
): number {
  if (total === 0) return -1;
  const step = Math.max(1, columnCount);
  switch (key) {
    case "ArrowRight":
      return Math.min(total - 1, current + 1);
    case "ArrowLeft":
      return Math.max(0, current - 1);
    case "ArrowDown":
      return Math.min(total - 1, current + step);
    case "ArrowUp":
      return Math.max(0, current - step);
    case "Home":
      return 0;
    case "End":
      return total - 1;
    default:
      return current;
  }
}

/** Button label for the active mode. */
export function adoptLabel(role: MediaRole): string {
  return role === "hero" ? "Als Hero übernehmen" : "Zur Galerie hinzufügen";
}
