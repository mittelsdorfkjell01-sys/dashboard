const FILTER_KEYS = ["q", "status", "region_id", "sport", "completeness", "media"] as const;

export function countActiveAdminSpotFilters(params: URLSearchParams): number {
  return FILTER_KEYS.reduce((count, key) => count + (params.get(key)?.trim() ? 1 : 0), 0);
}

export function resetAdminSpotFilters(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams();
  const sort = params.get("sort")?.trim();
  if (sort && sort !== "name") next.set("sort", sort);
  return next;
}
