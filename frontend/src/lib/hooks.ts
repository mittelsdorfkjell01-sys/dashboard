// Data-loading hooks: fetch from the API, adapt to frontend shapes, and expose
// { data, loading, error, reload } so every page can render a skeleton / error
// state instead of a blank screen. Backed by a shared stale-while-revalidate
// cache (see ./swr): navigating between pages renders cached data instantly and
// refreshes in the background instead of re-showing a skeleton and re-fetching.

import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import type { Spot } from "./types";
import * as api from "./api";
import { adaptSpot, adaptSpots } from "./adapt";
import { usePersistentSwr, useSwr, type SwrState } from "./swr";
import { mutate } from "./swr";
import { mergeFeed, type FeedPost } from "./communityFeed";
import type { NormalizedForecastSeries } from "./forecastNormalization";

// Kept as names for backward-compatible imports; identical shape to SwrState.
export type AsyncState<T> = SwrState<T>;
export type AsyncStateReloadable<T> = SwrState<T>;

export interface LandingSpotsData {
  spots: Spot[];
  total: number;
  version: string;
}

/** Bounded first-paint catalogue plus every curated landing hero. */
export function useLandingSpots(): AsyncStateReloadable<LandingSpotsData> {
  const state = usePersistentSwr("spots:landing", api.getLandingSpots, {
    storageKey: "swd.landing-spots.v1",
    maxAgeMs: 24 * 60 * 60 * 1000,
  });
  const data = useMemo(
    () => state.data
      ? { ...state.data, spots: adaptSpots(state.data.spots, new Map()) }
      : null,
    [state.data],
  );
  return { ...state, data };
}

/** Spots (+ their regions), adapted. Regions come from the shared cache, so a
 *  spot list never re-fetches the region catalogue from scratch. */
export function useSpots(
  query: api.SpotQuery = {},
  enabled = true,
): AsyncStateReloadable<Spot[]> {
  const key = `spots:${JSON.stringify(query)}`;
  const persist = query.limit === 100 && Object.keys(query).length === 1;
  const spots = usePersistentSwr(
    enabled ? key : null,
    () => api.getSpots(query),
    persist ? {
        storageKey: "swd.public-spots.v1",
        maxAgeMs: 7 * 24 * 60 * 60 * 1000,
      } : null,
  );
  const data = useMemo(
    () => (spots.data ? adaptSpots(spots.data, new Map()) : null),
    [spots.data],
  );
  return {
    data,
    loading: spots.loading,
    refreshing: spots.refreshing,
    stale: spots.stale,
    error: spots.error,
    errorStatus: spots.errorStatus,
    reload: spots.reload,
  };
}

/** "aktuelle Top Spots" — published spots ranked by this week's wind forecast,
 *  today's conditions and popularity (backend `/spots/top`), adapted with their
 *  regions. Rotates daily; same shape as {@link useSpots} so tiles are unchanged. */
export function useTopSpots(limit = 5): AsyncStateReloadable<Spot[]> {
  const spots = useSwr(
    `top-spots:kitesurf:${limit}`,
    () => api.getTopSpots(limit, "kitesurf"),
  );
  const data = useMemo(
    () => (spots.data ? adaptSpots(spots.data, new Map()) : null),
    [spots.data],
  );
  return {
    data,
    loading: spots.loading,
    refreshing: spots.refreshing,
    stale: spots.stale,
    error: spots.error,
    errorStatus: spots.errorStatus,
    reload: spots.reload,
  };
}

/** Personalized ordering with the same public SpotSummary card contract. */
export function useRecommendations(
  query: api.RecommendationQuery,
  enabled = true,
): AsyncStateReloadable<Spot[]> {
  const key = `recommendations:${JSON.stringify(query)}`;
  // Only the explicitly non-personalized variant is public. Keeping these
  // three small landing lists across reloads makes returning visits render
  // immediately, while account-specific rankings never reach localStorage.
  const persistent = query.personalized === false
    ? {
        storageKey: `swd.public-recommendations.v1:${key}`,
        maxAgeMs: 6 * 60 * 60 * 1000,
      }
    : null;
  const state = usePersistentSwr(
    enabled ? key : null,
    () => api.getRecommendations(query),
    persistent,
  );
  const data = useMemo(
    () => (state.data ? adaptSpots(state.data, new Map()) : null),
    [state.data],
  );
  return { ...state, data };
}

export function useRiderSetupComplete(enabled: boolean): AsyncStateReloadable<boolean> {
  const state = useSwr(enabled ? "rider-setup-complete:kitesurf" : null, async () => {
    const account = await import("./account");
    const [profile, sport, gear] = await Promise.all([
      account.getRiderProfile(),
      account.getRiderSportProfile("kitesurf"),
      account.getGear("kitesurf"),
    ]);
    return Boolean(
      profile.weightKg != null &&
      sport.level &&
      gear.some((item) => item.active && item.kind === "kite" && item.size != null),
    );
  });
  return state;
}

/** A single spot (full record) + its region, adapted. */
export function useSpot(id?: string): AsyncStateReloadable<Spot> {
  const spot = useSwr(id ? `spot:${id}` : null, () => api.getSpot(id!));
  const data = useMemo(
    () => (spot.data ? adaptSpot(spot.data) : null),
    [spot.data],
  );
  return {
    data,
    loading: spot.loading,
    refreshing: spot.refreshing,
    stale: spot.stale,
    error: spot.error,
    errorStatus: spot.errorStatus,
    reload: spot.reload,
  };
}

export function useWindClimatology(
  id?: string,
  window?: { fromYear: number; toYear: number } | null,
): AsyncStateReloadable<api.WindClimatologyRead> {
  // Debounce the two bounds as primitives (an inline object would reset the
  // timer every render); a window re-aggregates server-side from stored data.
  const fromYear = useDebouncedValue(window?.fromYear, 300);
  const toYear = useDebouncedValue(window?.toYear, 300);
  const windowed = fromYear != null && toYear != null;
  return useSwr(
    id ? `wind-climatology-v2:${id}:${windowed ? `${fromYear}-${toYear}` : "full"}` : null,
    () => api.getWindClimatology(id!, windowed ? { fromYear, toYear } : {}),
  );
}

/** Debounces a fast-changing value (e.g. a slider being dragged). The
 *  returned value only catches up `delayMs` after the input stops changing. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export interface WindClimatologyV3Selection {
  minWindKn: number;
  maxWindKn: number | null; // null = open upper bound ("40+")
  directionMode: api.WindDirectionMode;
}

export interface WindClimatologyV3State {
  /** Payload for the most recently *resolved* selection — kept on screen
   *  while a newer selection is still loading, so the chart never blanks
   *  out mid-interaction. */
  data: api.WindClimatologyV3Read | null;
  /** True once the very first variant for this spot has ever loaded. */
  ready: boolean;
  /** A newer selection is in flight; `data` still reflects the previous one. */
  switching: boolean;
  error: string | null;
  notFound: boolean;
}

const V3_DEBOUNCE_MS = 300;

/** Phase 5 public V3 weekly-reliability data. Debounces the selection (slider
 *  drags don't fire a request per pixel), caches per spot+variant via the
 *  shared SWR store, and keeps the previous variant's data visible while a
 *  new one loads instead of blanking the chart. `enabled=false` short-circuits
 *  to an idle state without ever calling the API (feature-flag/V2-fallback gate). */
export function useWindClimatologyV3(
  spotId: string | undefined,
  selection: WindClimatologyV3Selection,
  enabled: boolean,
  window?: { fromYear: number; toYear: number } | null,
): WindClimatologyV3State {
  const committed = useDebouncedValue(selection, V3_DEBOUNCE_MS);
  const fromYear = useDebouncedValue(window?.fromYear, V3_DEBOUNCE_MS);
  const toYear = useDebouncedValue(window?.toYear, V3_DEBOUNCE_MS);
  const windowed = fromYear != null && toYear != null;
  const key =
    enabled && spotId
      ? `wind-climatology-v3:${spotId}:${committed.minWindKn}:${committed.maxWindKn ?? "plus"}:${committed.directionMode}:${windowed ? `${fromYear}-${toYear}` : "full"}`
      : null;
  const swr = useSwr(key, () =>
    api.getWindClimatologyV3(spotId!, {
      minWindKn: committed.minWindKn,
      maxWindKn: committed.maxWindKn,
      directionMode: committed.directionMode,
      ...(windowed ? { fromYear, toYear } : {}),
    }),
  );

  const [display, setDisplay] = useState<api.WindClimatologyV3Read | null>(null);
  const [everLoaded, setEverLoaded] = useState(false);
  useEffect(() => {
    if (swr.data) {
      setDisplay(swr.data);
      setEverLoaded(true);
    }
  }, [swr.data]);
  useEffect(() => {
    if (!enabled) {
      setDisplay(null);
      setEverLoaded(false);
    }
  }, [enabled, spotId]);

  return {
    data: display,
    ready: everLoaded,
    switching: !!key && swr.loading && display !== null,
    error: everLoaded ? null : swr.error,
    notFound: !everLoaded && !!swr.error && /404|not available|not found/i.test(swr.error),
  };
}

/** The spot's natural "best travel season" window (V3 `best_season`), fetched
 *  with the default wind window and auto-upgraded to the spot's reviewed usable
 *  directions when available — the same default the detailed Windmonate module
 *  shows. Deliberately independent of the module's URL/slider selection so the
 *  summary lines (Daten header, Info tab) stay a stable at-a-glance answer.
 *  Best-effort: returns null while loading, on error, or when no clear season
 *  exists, so callers simply render nothing. Shares the V3 SWR cache key, so on
 *  the Daten tab it usually costs no extra request. */
export function useSpotBestSeason(spotId?: string): { start_date: string; end_date: string } | null {
  const [directionMode, setDirectionMode] = useState<api.WindDirectionMode>("all");
  const v3 = useWindClimatologyV3(spotId, { minWindKn: 15, maxWindKn: 20, directionMode }, Boolean(spotId));
  useEffect(() => {
    if (v3.data?.direction.usable_available && directionMode === "all") setDirectionMode("usable");
  }, [v3.data, directionMode]);
  const season = v3.data?.best_season;
  return season ? { start_date: season.start_date, end_date: season.end_date } : null;
}

/** Live conditions for a spot (best-effort; failure is non-fatal). */
export function useSpotLive(id?: string): AsyncStateReloadable<api.LiveConditionsRead> {
  const enabled = import.meta.env.VITE_WEATHER_POLLING_ENABLED === "true";
  return useSwr(id ? `live:${id}` : null, () => api.getSpotLive(id!), enabled ? {
      refreshIntervalMs: 5 * 60_000, jitterRatio: 0.15,
      refreshOnFocus: true, refreshOnReconnect: true, maxAgeMs: 10 * 60_000,
    } : {});
}

/** Batch live conditions for several spots → Map by spot_id. One request per
 *  ≤20 ids (the endpoint's cap) instead of one per tile — chunked and merged
 *  here so callers never have to think about the limit. Best-effort. */
export function useSpotsLive(
  ids: string[],
  enabled = true,
): AsyncStateReloadable<Map<string, api.LiveConditionsRead>> {
  // Sort for a stable cache key regardless of input order.
  const key = enabled && ids.length ? `live-batch:${[...ids].sort().join(",")}` : null;
  const state = useSwr(key, async () => {
    const chunks: string[][] = [];
    for (let i = 0; i < ids.length; i += 20) chunks.push(ids.slice(i, i + 20));
    const results = await Promise.all(chunks.map((chunk) => api.getSpotsLive(chunk)));
    return results.flat();
  });
  const data = useMemo(
    () => (state.data ? new Map(state.data.map((d) => [d.spot_id, d])) : null),
    [state.data]
  );
  return { data, loading: state.loading, refreshing: state.refreshing, stale: state.stale, error: state.error, errorStatus: state.errorStatus, reload: state.reload };
}

/** Normalized 10-day forecast with hourly detail across the full horizon. */
export function useSpotForecast(id?: string): AsyncStateReloadable<NormalizedForecastSeries> {
  const enabled = import.meta.env.VITE_WEATHER_POLLING_ENABLED === "true";
  return useSwr(id ? `forecast:${id}` : null, () => api.getSpotForecast(id!, 10), enabled ? {
    refreshIntervalMs: 45 * 60_000, jitterRatio: 0.15,
    refreshOnFocus: true, refreshOnReconnect: true, maxAgeMs: 60 * 60_000,
  } : {});
}

/** Forecast hour nearest to now for lightweight hints on the Info tab. */
export function useSpotForecastSummary(id?: string): AsyncStateReloadable<api.ForecastSummaryRead> {
  const enabled = import.meta.env.VITE_WEATHER_POLLING_ENABLED === "true";
  return useSwr(id ? `forecast-summary:${id}` : null, () => api.getSpotForecastSummary(id!), {
    revalidateOnMount: "stale",
    maxAgeMs: 60 * 60_000,
    ...(enabled ? {
      refreshIntervalMs: 45 * 60_000, jitterRatio: 0.15,
      refreshOnFocus: true, refreshOnReconnect: true,
    } : {}),
  });
}

/** Region season aggregate (52 weeks). Best-effort. */
export function useRegionSeason(id?: string): AsyncStateReloadable<api.RegionSeasonResponse> {
  return useSwr(id ? `region-season:${id}` : null, () => api.getRegionSeason(id!));
}

/** Open time: the best weeks for a region. Best-effort. */
export function useBestWeeks(regionId?: string): AsyncStateReloadable<api.BestWeeksResponse> {
  return useSwr(
    regionId ? `best-weeks:${regionId}` : null,
    () => api.getBestWeeks({ region_id: regionId! })
  );
}

/** All regions (raw backend records), cached once and shared app-wide. */
export function useRegions(enabled = true): AsyncStateReloadable<api.Region[]> {
  return useSwr(enabled ? "regions" : null, () => api.getRegions());
}

/** Admin region list — includes drafts. */
export function useAdminRegions(): AsyncStateReloadable<api.Region[]> {
  return useSwr("admin-regions", () => api.getAdminRegionsFlat());
}

/** Resolve one region by slug regardless of status (so draft preview works). */
export function useRegionBySlug(slug: string | undefined) {
  return useSwr(slug ? `region-slug:${slug}` : null, () =>
    api.getRegionBySlug(slug!)
  );
}

export interface CommunityFeedState {
  posts: FeedPost[];
  photos: api.CommunityImage[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  addTip: (tip: api.TipItem) => void;
}

/** Ratings + tips + images for a spot, merged into one chronological feed
 *  (see lib/communityFeed). The Info tab's mosaic gallery tile and the
 *  community feed section call this independently from two different places
 *  in the page — the underlying useSwr cache (keyed by spotId) means that
 *  only fires one set of requests, not two. */
export function useCommunityFeed(spotId?: string): CommunityFeedState {
  const ratings = useSwr(spotId ? `ratings:${spotId}` : null, () => api.getRatings(spotId!));
  const tips = useSwr(spotId ? `tips:${spotId}` : null, () => api.getTips(spotId!));
  const images = useSwr(spotId ? `images:${spotId}` : null, () => api.getSpotImages(spotId!));

  // Commons photos were fetched automatically, not posted by a community
  // member — they feed the gallery (below) but never masquerade as a feed
  // post ("someone shared a photo").
  const communityImages = useMemo(
    () => (images.data?.items ?? []).filter((i) => i.source !== "wikimedia_commons"),
    [images.data]
  );
  const posts = useMemo(
    () =>
      mergeFeed({
        ratings: ratings.data?.items ?? [],
        tips: tips.data?.items ?? [],
        images: communityImages,
      }),
    [ratings.data, tips.data, communityImages]
  );
  const photos = images.data?.items ?? [];

  return {
    posts,
    photos,
    // Text comments do not depend on the gallery response. In particular,
    // gallery cold starts or a slow media query must not keep the comments
    // skeleton visible after ratings and tips are already available. Images
    // still join the existing posts as soon as their request completes.
    loading: ratings.loading || tips.loading,
    error: ratings.error ?? tips.error,
    reload: () => {
      ratings.reload();
      tips.reload();
      images.reload();
    },
    addTip: (tip) => {
      if (!spotId) return;
      mutate<{ items: api.TipItem[] }>(`tips:${spotId}`, (current) => ({
        items: [tip, ...(current?.items ?? [])],
      }));
    },
  };
}

/** The namebox score — real `RatingAggregate.score` (0–5, Bayesian) from the
 *  spot's published ratings. Shares the `ratings:${spotId}` cache key with
 *  `useCommunityFeed`, so mounting both on the same page (namebox + feed)
 *  never fires the request twice. */
export function useRatingScore(spotId?: string): number | null {
  const ratings = useSwr(spotId ? `ratings:${spotId}` : null, () => api.getRatings(spotId!));
  return ratings.data?.aggregate.score ?? null;
}

/** A piece of UI state persisted to localStorage under `key` (spot-agnostic —
 *  e.g. a chart's unit/metric toggle that should stay put across spots and
 *  reloads). Falls back to `initial` when nothing's stored yet, or storage
 *  isn't available (private browsing, quota). */
export function usePersistedState<T>(
  key: string,
  initial: T
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw !== null ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* private browsing / quota — the toggle still works for this session */
    }
  }, [key, value]);

  return [value, setValue];
}
