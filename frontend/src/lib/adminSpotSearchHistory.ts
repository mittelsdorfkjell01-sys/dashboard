const STORAGE_KEY = "swd:admin-spot-searches";
const MAX_SEARCHES = 8;

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getAdminSpotSearches(): string[] {
  try {
    const value = storage()?.getItem(STORAGE_KEY);
    const parsed = value ? JSON.parse(value) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0)
      .slice(0, MAX_SEARCHES);
  } catch {
    return [];
  }
}

export function rememberAdminSpotSearch(query: string): string[] {
  const cleaned = query.trim();
  if (!cleaned) return getAdminSpotSearches();
  const next = [
    cleaned,
    ...getAdminSpotSearches().filter(
      (entry) => entry.localeCompare(cleaned, "de", { sensitivity: "base" }) !== 0
    ),
  ].slice(0, MAX_SEARCHES);
  try {
    storage()?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Browsers may deny storage in private or restricted contexts.
  }
  return next;
}
