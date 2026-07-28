import type { ReviewTip } from "./api";

export interface TipThread {
  root: ReviewTip;
  replies: ReviewTip[];
}

/**
 * Group a flat, chronological list of admin tips into threads: each top-level
 * comment (`parent_id === null`) with its replies in order. A reply whose
 * parent isn't in the list is treated as its own root, so nothing is dropped.
 * Used by the per-spot moderation panel to show a reply under its parent.
 */
export function groupTipThreads(tips: ReviewTip[]): TipThread[] {
  const byId = new Map(tips.map((t) => [t.id, t]));
  const roots: ReviewTip[] = [];
  const repliesByParent = new Map<string, ReviewTip[]>();

  for (const t of tips) {
    if (t.parent_id && byId.has(t.parent_id)) {
      const arr = repliesByParent.get(t.parent_id) ?? [];
      arr.push(t);
      repliesByParent.set(t.parent_id, arr);
    } else {
      roots.push(t);
    }
  }

  return roots.map((root) => ({
    root,
    replies: repliesByParent.get(root.id) ?? [],
  }));
}
