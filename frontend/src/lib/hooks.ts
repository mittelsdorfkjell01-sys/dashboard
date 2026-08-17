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

// Kept as names for backward-compatible imports; identical shape to SwrState.
export type AsyncState<T> = SwrState<T>;
export type AsyncStateReloadable<T> = SwrState<T>;

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
    error: spots.error,
    reload: spots.reload,
  };
}

/** "aktuelle Top Spots" — published spots ranked by this week's wind forecast,
 *  today's conditions and popularity (backend `/spots/top`), adapted with their
 *  regions. Rotates daily; same shape as {@link useSpots} so tiles are unchanged. */
export function useTopSpots(limit = 5): AsyncStateReloadable<Spot[]> {
  const spots = usePersistentSwr(`top-spots:${limit}`, () => api.getTopSpots(limit), {
    storageKey: `swd.top-spots.v1.${limit}`,
    maxAgeMs: 7 * 24 * 60 * 60 * 1000,
  });
  const data = useMemo(
    () => (spots.data ? adaptSpots(spots.data, new Map()) : null),
    [spots.data],
  );
  return {
    data,
    loading: spots.loading,
    error: spots.error,
    reload: spots.reload,
  };
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
    error: spot.error,
    reload: spot.reload,
  };
}

export function useWindClimatology(id?: string): AsyncStateReloadable<api.WindClimatologyRead> {
  return useSwr(id ? `wind-climatology-v2:${id}` : null, () => api.getWindClimatology(id!));
}

/** Live conditions for a spot (best-effort; failure is non-fatal). */
export function useSpotLive(id?: string): AsyncStateReloadable<api.LiveConditionsRead> {
  return useSwr(id ? `live:${id}` : null, () => api.getSpotLive(id!));
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
  return { data, loading: state.loading, error: state.error, reload: state.reload };
}

/** 10-day forecast for a spot (days 1–5 hourly, days 6–10 trend). */
export function useSpotForecast(id?: string): AsyncStateReloadable<api.ForecastSeries> {
  return useSwr(id ? `forecast:${id}` : null, () => api.getSpotForecast(id!));
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
