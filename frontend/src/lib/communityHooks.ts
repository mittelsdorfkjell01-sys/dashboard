import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import * as api from "./api/community";
import { mergeFeed, type FeedPost } from "./communityFeed";
import { mutate, useSwr } from "./swr";

export interface CommunityFeedState {
  posts: FeedPost[];
  photos: api.CommunityImage[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  /** Put a new comment into the list before the server confirms it. */
  addTip: (tip: api.TipItem) => void;
  /** Drop a comment (and anything replying to it) from the list at once. */
  removeTip: (id: string) => void;
  /** Swap an edited comment in place, keeping its position in the thread. */
  replaceTip: (tip: api.TipItem) => void;
}

export function useCommunityFeed(spotId?: string): CommunityFeedState {
  const ratings = useSwr(spotId ? `ratings:${spotId}` : null, () => api.getRatings(spotId!));
  // Comments are the one part of this page other people change while you are
  // looking at it. A half-minute poll (and a refresh when the tab comes back)
  // is enough to keep a thread current without a socket; the interval is long
  // enough that a reader scrolling the list never sees it jump under them.
  const tips = useSwr(spotId ? `tips:${spotId}` : null, () => api.getTips(spotId!), {
    refreshIntervalMs: 30_000,
    refreshOnFocus: true,
  });
  const images = useSwr(spotId ? `images:${spotId}` : null, () => api.getSpotImages(spotId!));

  const communityImages = useMemo(
    () => (images.data?.items ?? []).filter((image) => image.source !== "wikimedia_commons"),
    [images.data],
  );
  const posts = useMemo(
    () => mergeFeed({
      ratings: ratings.data?.items ?? [],
      tips: tips.data?.items ?? [],
      images: communityImages,
    }),
    [ratings.data, tips.data, communityImages],
  );

  return {
    posts,
    photos: images.data?.items ?? [],
    // Gallery cold starts must not keep comments in a loading state.
    loading: ratings.loading || tips.loading,
    error: ratings.error ?? tips.error,
    reload: () => {
      ratings.reload();
      tips.reload();
      images.reload();
    },
    // The three local edits below land before the request does, so the list
    // answers the tap instead of the network. Each caller still reloads
    // afterwards, so a failed request is corrected by the next read.
    addTip: (tip) => {
      if (!spotId) return;
      mutate<{ items: api.TipItem[] }>(`tips:${spotId}`, (current) => ({
        items: [tip, ...(current?.items ?? [])],
      }));
    },
    removeTip: (id) => {
      if (!spotId) return;
      mutate<{ items: api.TipItem[] }>(`tips:${spotId}`, (current) => ({
        // Replies go with the parent: the server refuses to delete a comment
        // that has any, but a reply whose parent is gone would otherwise hang
        // in the list until the next read.
        items: (current?.items ?? []).filter((t) => t.id !== id && t.parent_id !== id),
      }));
    },
    replaceTip: (tip) => {
      if (!spotId) return;
      mutate<{ items: api.TipItem[] }>(`tips:${spotId}`, (current) => ({
        items: (current?.items ?? []).map((t) => (t.id === tip.id ? tip : t)),
      }));
    },
  };
}

export function useRatingScore(spotId?: string): number | null {
  const ratings = useSwr(spotId ? `ratings:${spotId}` : null, () => api.getRatings(spotId!));
  return ratings.data?.aggregate.score ?? null;
}

export function usePersistedState<T>(
  key: string,
  initial: T,
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
      // Private browsing or quota: state still works for this session.
    }
  }, [key, value]);

  return [value, setValue];
}
