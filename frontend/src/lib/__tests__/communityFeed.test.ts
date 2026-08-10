import { describe, expect, it } from "vitest";
import type { CommunityImage, RatingItem, TipItem } from "../api";
import {
  avatarColor,
  commentThreads,
  encodeVisitDate,
  initials,
  mergeFeed,
  parsePostText,
  relativeTime,
  sortFeed,
} from "../communityFeed";

const rating = (over: Partial<RatingItem>): RatingItem => ({
  id: "r1",
  stars: 4,
  skill_level: "advanced",
  sport: "kitesurf",
  conditions: "Solide Bedingungen.",
  author_name: "Anna Muster",
  created_at: "2026-07-20T12:00:00Z",
  ...over,
});

const tip = (over: Partial<TipItem>): TipItem => ({
  id: "t1",
  body: "Parkt lieber am Nordende.",
  title: null,
  author_name: "Ben",
  created_at: "2026-07-18T09:00:00Z",
  parent_id: null,
  ...over,
});

const image = (over: Partial<CommunityImage>): CommunityImage => ({
  id: "i1",
  url: "/media/i1.jpg",
  kind: "gallery",
  width: 800,
  height: 600,
  credit: null,
  created_at: "2026-07-20T12:00:30Z",
  source: "user_upload",
  license_name: null,
  license_url: null,
  source_url: null,
  ...over,
});

describe("parsePostText / encodeVisitDate", () => {
  it("round-trips a visit date through the encoded marker", () => {
    const encoded = encodeVisitDate("2026-07-14", "War super windig.");
    expect(encoded).toBe("[besucht:2026-07-14] War super windig.");
    expect(parsePostText(encoded)).toEqual({ visitedAt: "2026-07-14", text: "War super windig." });
  });

  it("returns the text unchanged with no visit date when none was given", () => {
    expect(encodeVisitDate("", "Nur Text")).toBe("Nur Text");
  });

  it("treats plain text (no marker) as having no visit date", () => {
    expect(parsePostText("Ganz normaler Text.")).toEqual({ visitedAt: null, text: "Ganz normaler Text." });
  });
});

describe("commentThreads", () => {
  it("nests replies under their parent comment, oldest first, ignoring photos", () => {
    const posts = mergeFeed({
      ratings: [],
      tips: [
        tip({ id: "c1", body: "Top Spot", created_at: "2026-07-18T09:00:00Z" }),
        tip({ id: "r2", body: "zweite Antwort", parent_id: "c1", created_at: "2026-07-18T11:00:00Z" }),
        tip({ id: "r1", body: "erste Antwort", parent_id: "c1", created_at: "2026-07-18T10:00:00Z" }),
      ],
      images: [],
    });
    const threads = commentThreads(posts);
    expect(threads).toHaveLength(1);
    expect(threads[0].comment.id).toBe("tip:c1");
    expect(threads[0].replies.map((r) => r.text)).toEqual(["erste Antwort", "zweite Antwort"]);
  });

  it("drops orphan replies whose parent is absent", () => {
    const posts = mergeFeed({
      ratings: [],
      tips: [tip({ id: "r", body: "verwaist", parent_id: "missing" })],
      images: [],
    });
    expect(commentThreads(posts)).toHaveLength(0);
  });
});

describe("mergeFeed", () => {
  it("attaches an image to the rating with the same author, posted moments later", () => {
    const img = image({ credit: "Anna Muster", created_at: "2026-07-20T12:00:20Z" });
    const posts = mergeFeed({ ratings: [rating({})], tips: [], images: [img] });
    expect(posts).toHaveLength(1); // the image is consumed, not a separate post
    expect(posts[0].photo?.id).toBe("i1");
    expect(posts[0].reportImageId).toBe("i1");
  });

  it("leaves an unmatched image (different author) as its own photo-only post", () => {
    const img = image({ credit: "Someone Else", created_at: "2026-07-20T12:00:20Z" });
    const posts = mergeFeed({ ratings: [rating({})], tips: [], images: [img] });
    expect(posts).toHaveLength(2);
    const photoPost = posts.find((p) => p.kind === "photo")!;
    expect(photoPost.photo?.id).toBe("i1");
    expect(photoPost.authorName).toBe("Someone Else");
  });

  it("does not attach an image outside the match window even with the same author", () => {
    const img = image({ credit: "Anna Muster", created_at: "2026-07-20T13:00:00Z" }); // +1h
    const posts = mergeFeed({ ratings: [rating({})], tips: [], images: [img] });
    expect(posts).toHaveLength(2);
    expect(posts.some((p) => p.kind === "rating" && p.photo != null)).toBe(false);
  });

  it("picks the closest of several same-author images within the window", () => {
    const near = image({ id: "near", credit: "Anna Muster", created_at: "2026-07-20T12:00:10Z" });
    const far = image({ id: "far", credit: "Anna Muster", created_at: "2026-07-20T12:04:00Z" });
    const posts = mergeFeed({ ratings: [rating({})], tips: [], images: [far, near] });
    const ratingPost = posts.find((p) => p.kind === "rating")!;
    expect(ratingPost.photo?.id).toBe("near");
    expect(posts.find((p) => p.kind === "photo")?.photo?.id).toBe("far");
  });

  it("includes tips as text-only posts with no stars", () => {
    const posts = mergeFeed({ ratings: [], tips: [tip({})], images: [] });
    expect(posts).toHaveLength(1);
    expect(posts[0].kind).toBe("tip");
    expect(posts[0].stars).toBeNull();
    expect(posts[0].text).toBe("Parkt lieber am Nordende.");
  });

  it("handles 0, 1 and many mixed items without dropping or duplicating anything", () => {
    expect(mergeFeed({ ratings: [], tips: [], images: [] })).toHaveLength(0);

    const many = mergeFeed({
      ratings: Array.from({ length: 10 }, (_, i) => rating({ id: `r${i}`, author_name: `Rater ${i}` })),
      tips: Array.from({ length: 10 }, (_, i) => tip({ id: `t${i}`, author_name: `Tipper ${i}` })),
      images: Array.from({ length: 10 }, (_, i) => image({ id: `i${i}`, credit: `Unmatched ${i}` })),
    });
    expect(many).toHaveLength(30);
  });
});

describe("sortFeed", () => {
  const older = rating({ id: "old", created_at: "2026-07-01T00:00:00Z" });
  const newer = rating({ id: "new", created_at: "2026-07-20T00:00:00Z" });
  const posts = mergeFeed({ ratings: [older, newer], tips: [], images: [] });

  it("sorts newest first by default", () => {
    const sorted = sortFeed(posts, "newest", {});
    expect(sorted.map((p) => p.id)).toEqual(["rating:new", "rating:old"]);
  });

  it("sorts by helpful count, falling back to newest on ties", () => {
    const sorted = sortFeed(posts, "helpful", { "rating:old": 5, "rating:new": 1 });
    expect(sorted.map((p) => p.id)).toEqual(["rating:old", "rating:new"]);
  });
});

describe("relativeTime", () => {
  const now = new Date("2026-07-20T12:00:00Z");

  it("reads naturally across the near/medium/far ranges", () => {
    expect(relativeTime("2026-07-20T11:59:30Z", now)).toBe("gerade eben");
    expect(relativeTime("2026-07-20T11:30:00Z", now)).toBe("vor 30 Min.");
    expect(relativeTime("2026-07-20T09:00:00Z", now)).toBe("vor 3 Std.");
    expect(relativeTime("2026-07-17T12:00:00Z", now)).toBe("vor 3 Tagen");
    expect(relativeTime("2026-06-20T12:00:00Z", now)).toBe("vor 1 Monat");
  });
});

describe("avatar helpers", () => {
  it("is deterministic for the same name", () => {
    expect(avatarColor("Anna Muster")).toBe(avatarColor("Anna Muster"));
  });

  it("builds two-letter initials from first + last name, one word from a single name", () => {
    expect(initials("Anna Muster")).toBe("AM");
    expect(initials("Ben")).toBe("BE");
  });
});
