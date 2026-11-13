import { request } from "./client";

export interface RatingItem {
  id: string;
  stars: number;
  skill_level: string;
  sport: string;
  conditions: string;
  author_name: string;
  created_at: string;
  upvotes?: number;
  viewer_upvoted?: boolean;
}

export interface RatingAggregate {
  count: number;
  avg: number | null;
  score: number;
}

export interface TipItem {
  id: string;
  body: string;
  title: string | null;
  author_name: string;
  created_at: string;
  parent_id: string | null;
  upvotes?: number;
  viewer_upvoted?: boolean;
  /** The signed-in viewer wrote this comment, so it may offer deletion. */
  viewer_is_author?: boolean;
}

export interface CommunityImage {
  id: string;
  url: string;
  kind: string;
  width: number | null;
  height: number | null;
  credit: string | null;
  created_at: string;
  source: string;
  license_name: string | null;
  license_url: string | null;
  source_url: string | null;
}

export const getRatings = (spotId: string) =>
  request<{ items: RatingItem[]; aggregate: RatingAggregate }>(`/spots/${spotId}/ratings`);

export const postRating = (
  spotId: string,
  body: {
    stars: number;
    skill_level: string;
    sport: string;
    conditions: string;
    author_name?: string;
    author_email?: string;
    website?: string;
  },
) => request<RatingItem>(`/spots/${spotId}/ratings`, {
  method: "POST",
  body: JSON.stringify(body),
});

export const getTips = (spotId: string) =>
  request<{ items: TipItem[] }>(`/spots/${spotId}/tips`);

export const postTip = (
  spotId: string,
  body: {
    body: string;
    title?: string;
    author_name?: string;
    author_email?: string;
    parent_id?: string;
    website?: string;
  },
) => request<TipItem>(`/spots/${spotId}/tips`, {
  method: "POST",
  body: JSON.stringify(body),
});

/** Delete one of the viewer's own comments. Returns 409 when the comment has
 *  replies — deleting it would take other people's text with it, so those go
 *  through the operator instead. */
export const deleteOwnTip = (id: string) =>
  request<void>(`/community/comments/tip/${id}`, { method: "DELETE" });

export const setCommentUpvote = (kind: "rating" | "tip", id: string, active: boolean) =>
  request<{ count: number; viewer_upvoted: boolean }>(`/community/comments/${kind}/${id}/upvote`, {
    method: active ? "PUT" : "DELETE",
  });

export const getSpotImages = (spotId: string) =>
  request<{ items: CommunityImage[] }>(`/spots/${spotId}/images`);

export const fetchCommonsImages = (spotId: string) =>
  request<{ items: CommunityImage[] }>(`/admin/spots/${spotId}/commons-images/fetch`, {
    method: "POST",
  });

export function uploadSpotImage(
  spotId: string,
  file: File,
  kind: "gallery" | "hero_candidate",
  options: { credit?: string; licenseAccept: boolean; review?: boolean } = { licenseAccept: false },
): Promise<CommunityImage> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  form.append("license_accept", String(options.licenseAccept));
  if (options.credit) form.append("credit", options.credit);
  if (options.review) form.append("review", "true");
  return request<CommunityImage>(`/spots/${spotId}/images`, {
    method: "POST",
    body: form,
    timeoutMs: 120_000,
  });
}

export const reportImage = (
  imageId: string,
  body: { reason: string; note?: string; reporter_email?: string; website?: string },
) => request<{ image_id: string; report_count: number; takedown_contact: string | null }>(
  `/images/${imageId}/report`,
  { method: "POST", body: JSON.stringify(body) },
);

export const getImageLicense = () =>
  request<{ version: string; terms: string }>(`/community/license`);

export const postSubmission = (body: {
  payload: Record<string, unknown>;
  submitter_name?: string;
  submitter_email?: string;
  website?: string;
}) => request<{ id: string; status: string }>(`/submissions`, {
  method: "POST",
  body: JSON.stringify(body),
});
