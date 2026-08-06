// Filter + sort state for the spot lists (Landing / Region), (de)serialised to
// the URL query string so a view is shareable and survives a reload.

import type { Spot } from "./types";
import type { SpotQuery } from "./api";
import { LEVELS } from "./labels";

export type SortKey = "name-asc" | "name-desc" | "level-asc" | "level-desc";

export const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "name-asc", label: "Name A–Z" },
  { key: "name-desc", label: "Name Z–A" },
  { key: "level-asc", label: "Level: Anfänger → Experte" },
  { key: "level-desc", label: "Level: Experte → Anfänger" },
];

export const DEFAULT_SORT: SortKey = "name-asc";

export interface FilterState {
  level?: string;
  waterCharacter?: string;
  styles: string[];
  bottomTypes?: string[];
  sort: SortKey;
}

export function emptyFilters(): FilterState {
  return { styles: [], bottomTypes: [], sort: DEFAULT_SORT };
}

export function parseFilters(sp: URLSearchParams): FilterState {
  const sort = (sp.get("sort") as SortKey) || DEFAULT_SORT;
  return {
    level: sp.get("level") || undefined,
    waterCharacter: sp.get("water") || undefined,
    styles: sp.getAll("style"),
    bottomTypes: sp.getAll("bottom"),
    sort: SORT_OPTIONS.some((o) => o.key === sort) ? sort : DEFAULT_SORT,
  };
}

/** Serialise into URLSearchParams (mutates a fresh copy). */
export function filtersToSearchParams(f: FilterState): URLSearchParams {
  const sp = new URLSearchParams();
  if (f.level) sp.set("level", f.level);
  if (f.waterCharacter) sp.set("water", f.waterCharacter);
  f.styles.forEach((s) => sp.append("style", s));
  (f.bottomTypes ?? []).forEach((s) => sp.append("bottom", s));
  if (f.sort !== DEFAULT_SORT) sp.set("sort", f.sort);
  return sp;
}

/** The server-side query part (filtering is done by the API). */
export function filtersToQuery(f: FilterState): SpotQuery {
  return {
    level: f.level,
    water_character: f.waterCharacter,
    style: f.styles.length ? f.styles : undefined,
    bottom_type: f.bottomTypes?.length ? f.bottomTypes : undefined,
  };
}

export function activeFilterCount(f: FilterState): number {
  return (
    (f.level ? 1 : 0) +
    (f.waterCharacter ? 1 : 0) +
    f.styles.length +
    (f.bottomTypes?.length ?? 0) +
    (f.sort !== DEFAULT_SORT ? 1 : 0)
  );
}

/** Client-side filter — used on the region page so the hero/map/season keep the
 *  full spot set while only the grid narrows. */
export function filterSpots(spots: Spot[], f: FilterState): Spot[] {
  return spots.filter((s) => {
    // level / waterCharacter are multi-select arrays; a single-select filter
    // matches when the spot carries that value among its own.
    if (f.level && !(s.level ?? []).includes(f.level)) return false;
    if (f.waterCharacter && !(s.waterCharacter ?? []).includes(f.waterCharacter))
      return false;
    if (f.styles.length && !f.styles.some((x) => (s.style ?? []).includes(x)))
      return false;
    if (
      (f.bottomTypes?.length ?? 0) > 0 &&
      !f.bottomTypes?.some((x) => (s.bottomType ?? []).includes(x))
    ) return false;
    return true;
  });
}

/** Client-side sort (the API already applied the filters). */
export function sortSpots(spots: Spot[], sort: SortKey): Spot[] {
  const out = [...spots];
  // A spot can hold several levels; rank it by its *lowest* (most accessible)
  // known level so beginner-to-expert sorting keeps mixed spots near beginners.
  const levelRank = (s: Spot) => {
    const idxs = (s.level ?? [])
      .map((l) => LEVELS.indexOf(l as (typeof LEVELS)[number]))
      .filter((i) => i >= 0);
    return idxs.length ? Math.min(...idxs) : 999;
  };
  switch (sort) {
    case "name-desc":
      return out.sort((a, b) => b.name.localeCompare(a.name, "de"));
    case "level-asc":
      return out.sort(
        (a, b) => levelRank(a) - levelRank(b) || a.name.localeCompare(b.name, "de")
      );
    case "level-desc":
      return out.sort(
        (a, b) => levelRank(b) - levelRank(a) || a.name.localeCompare(b.name, "de")
      );
    case "name-asc":
    default:
      return out.sort((a, b) => a.name.localeCompare(b.name, "de"));
  }
}
