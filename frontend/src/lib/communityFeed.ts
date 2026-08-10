// Merges the three separate community endpoints (ratings, tips, images) into
// one chronological feed, client-side — there is no unified "post" endpoint
// on the backend (and this sprint adds none), so a "post" is a view built by
// joining what's already there:
//
//  - A rating (stars + free-text "conditions") or a tip (free-text "body")
//    is the post's text half.
//  - An uploaded image is attached to whichever rating/tip has the same
//    `credit`/author name and was created within a few minutes of it (the
//    composer submits both in one action) — a best-effort join, since images
//    have no real foreign key back to a rating or tip. An image that matches
//    nothing becomes its own photo-only post (older, gallery-only uploads
//    still show up in the feed instead of disappearing).
//  - A visit date has no backend column either, so the composer encodes it as
//    a leading `[besucht:YYYY-MM-DD]` marker in the same free-text field;
//    `parsePostText` strips it back out for display.

import type { CommunityImage, RatingItem, TipItem } from "./api";

export type FeedPostKind = "rating" | "tip" | "photo";

export interface FeedPost {
  id: string; // unique across kinds: "rating:<id>" | "tip:<id>" | "photo:<id>"
  kind: FeedPostKind;
  authorName: string;
  createdAt: string;
  visitedAt: string | null; // "YYYY-MM-DD", from the encoded marker
  stars: number | null;
  skillLevel: string | null;
  sport: string | null;
  text: string | null;
  title: string | null;
  photo: CommunityImage | null;
  /** For a reply, the `id` of the FeedPost it answers (`tip:<parent>`); null
   *  for top-level posts. Only tips can be replies. */
  parentId: string | null;
  /** Image id to route "melden" to — only photo-bearing posts have anything
   *  reportable (there's no report endpoint for ratings/tips). */
  reportImageId: string | null;
}

/** A top-level comment together with its replies (oldest first). */
export interface CommentThread {
  comment: FeedPost;
  replies: FeedPost[];
}

/**
 * Groups the feed's text posts into single-level threads: each top-level
 * comment (a post with text and no `parentId`) with its replies attached,
 * oldest reply first. Photo-only posts and orphan replies are ignored.
 */
export function commentThreads(posts: FeedPost[]): CommentThread[] {
  const tops = posts.filter((p) => p.text && !p.parentId);
  const byParent = new Map<string, FeedPost[]>();
  for (const p of posts) {
    if (p.text && p.parentId) {
      const list = byParent.get(p.parentId) ?? [];
      list.push(p);
      byParent.set(p.parentId, list);
    }
  }
  return tops.map((comment) => ({
    comment,
    replies: (byParent.get(comment.id) ?? []).sort((a, b) =>
      a.createdAt.localeCompare(b.createdAt)
    ),
  }));
}

const VISIT_MARKER_RE = /^\[besucht:(\d{4}-\d{2}-\d{2})\]\s*/;

export function encodeVisitDate(visitedAt: string, text: string): string {
  return visitedAt ? `[besucht:${visitedAt}] ${text}` : text;
}

export function parsePostText(raw: string): { visitedAt: string | null; text: string } {
  const m = raw.match(VISIT_MARKER_RE);
  if (!m) return { visitedAt: null, text: raw };
  return { visitedAt: m[1], text: raw.slice(m[0].length) };
}

// A photo uploaded as part of the same composer submission as a rating/tip
// lands within seconds of it — 5 minutes gives slow uploads room without
// risking a match against an unrelated, later post by the same name.
const MATCH_WINDOW_MS = 5 * 60 * 1000;

function closestMatch(images: CommunityImage[], authorName: string, createdAt: string): number {
  const t = new Date(createdAt).getTime();
  if (Number.isNaN(t)) return -1;
  let bestIndex = -1;
  let bestDelta = Infinity;
  images.forEach((img, i) => {
    if (img.credit !== authorName) return;
    const it = new Date(img.created_at).getTime();
    if (Number.isNaN(it)) return;
    const delta = Math.abs(it - t);
    if (delta <= MATCH_WINDOW_MS && delta < bestDelta) {
      bestDelta = delta;
      bestIndex = i;
    }
  });
  return bestIndex;
}

export function mergeFeed({
  ratings,
  tips,
  images,
}: {
  ratings: RatingItem[];
  tips: TipItem[];
  images: CommunityImage[];
}): FeedPost[] {
  const remaining = [...images];
  const take = (authorName: string, createdAt: string): CommunityImage | null => {
    const i = closestMatch(remaining, authorName, createdAt);
    return i === -1 ? null : remaining.splice(i, 1)[0];
  };

  const fromRatings: FeedPost[] = ratings.map((r) => {
    const { visitedAt, text } = parsePostText(r.conditions);
    const photo = take(r.author_name, r.created_at);
    return {
      id: `rating:${r.id}`,
      kind: "rating",
      authorName: r.author_name,
      createdAt: r.created_at,
      visitedAt,
      stars: r.stars,
      skillLevel: r.skill_level,
      sport: r.sport,
      text: text || null,
      title: null,
      photo,
      parentId: null,
      reportImageId: photo?.id ?? null,
    };
  });

  const fromTips: FeedPost[] = tips.map((t) => {
    const { visitedAt, text } = parsePostText(t.body);
    const photo = take(t.author_name, t.created_at);
    return {
      id: `tip:${t.id}`,
      kind: "tip",
      authorName: t.author_name,
      createdAt: t.created_at,
      visitedAt,
      stars: null,
      skillLevel: null,
      sport: null,
      text: text || null,
      title: t.title ?? null,
      photo,
      parentId: t.parent_id ? `tip:${t.parent_id}` : null,
      reportImageId: photo?.id ?? null,
    };
  });

  const fromPhotos: FeedPost[] = remaining.map((img) => ({
    id: `photo:${img.id}`,
    kind: "photo",
    authorName: img.credit ?? "Anonym",
    createdAt: img.created_at,
    visitedAt: null,
    stars: null,
    skillLevel: null,
    sport: null,
    text: null,
    title: null,
    photo: img,
    parentId: null,
    reportImageId: img.id,
  }));

  return [...fromRatings, ...fromTips, ...fromPhotos];
}

export type FeedSort = "newest" | "helpful";

/** Sorts a merged feed by post date (default) or by a client-side "helpful"
 *  vote count (see the `usePersistedState`-backed counts in SpotCommunity —
 *  there's no backend counter for this, so it's per-browser, not global). */
export function sortFeed(posts: FeedPost[], sort: FeedSort, helpfulCounts: Record<string, number>): FeedPost[] {
  return [...posts].sort((a, b) => {
    if (sort === "helpful") {
      const diff = (helpfulCounts[b.id] ?? 0) - (helpfulCounts[a.id] ?? 0);
      if (diff !== 0) return diff;
    }
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });
}

// --- presentation helpers ----------------------------------------------------

const AVATAR_PALETTE = ["#241C17", "#1E6E7E", "#4A8159", "#E0823C", "#3D332C", "#7A6F66"];

export function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/** Deterministic background color for the initials avatar, from a fixed
 *  palette keyed by a hash of the name — never an uploaded profile photo. */
export function avatarColor(name: string): string {
  return AVATAR_PALETTE[hashString(name) % AVATAR_PALETTE.length];
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const MONTHS_FULL_DE = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

/** "War am 14. Juli hier" — the visit date is more relevant than the post
 *  date for a spot report, so it gets the prominent phrasing. */
export function formatVisitDate(dateStr: string): string {
  const dt = new Date(dateStr);
  if (Number.isNaN(dt.getTime())) return "";
  return `War am ${dt.getDate()}. ${MONTHS_FULL_DE[dt.getMonth()]} hier`;
}

/** "vor 3 Tagen" — the post date, shown small/secondary next to the visit date. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.floor((now.getTime() - then) / 60000);
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `vor ${days} ${days === 1 ? "Tag" : "Tagen"}`;
  if (days < 30) {
    const weeks = Math.floor(days / 7);
    return `vor ${weeks} ${weeks === 1 ? "Woche" : "Wochen"}`;
  }
  if (days < 365) {
    const months = Math.floor(days / 30);
    return `vor ${months} ${months === 1 ? "Monat" : "Monaten"}`;
  }
  const years = Math.floor(days / 365);
  return `vor ${years} ${years === 1 ? "Jahr" : "Jahren"}`;
}
