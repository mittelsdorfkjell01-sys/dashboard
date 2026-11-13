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
  addTip: (tip: api.TipItem) => void;
}

export function useCommunityFeed(spotId?: string): CommunityFeedState {
  const ratings = useSwr(spotId ? `ratings:${spotId}` : null, () => api.getRatings(spotId!));
  const tips = useSwr(spotId ? `tips:${spotId}` : null, () => api.getTips(spotId!));
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
    addTip: (tip) => {
      if (!spotId) return;
      mutate<{ items: api.TipItem[] }>(`tips:${spotId}`, (current) => ({
        items: [tip, ...(current?.items ?? [])],
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
