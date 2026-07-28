import { describe, expect, it } from "vitest";
import { groupTipThreads } from "../tipThreads";
import type { ReviewTip } from "../api";

const tip = (over: Partial<ReviewTip> & { id: string }): ReviewTip => ({
  spot_id: "s1",
  body: "text",
  author_name: "A",
  status: "published",
  flagged: false,
  parent_id: null,
  created_at: "2024-01-01T00:00:00Z",
  ...over,
});

describe("groupTipThreads", () => {
  it("nests replies under their parent, preserving order", () => {
    const threads = groupTipThreads([
      tip({ id: "p1", body: "root one" }),
      tip({ id: "r1", parent_id: "p1", body: "reply a" }),
      tip({ id: "p2", body: "root two" }),
      tip({ id: "r2", parent_id: "p1", body: "reply b" }),
    ]);

    expect(threads.map((t) => t.root.id)).toEqual(["p1", "p2"]);
    expect(threads[0].replies.map((r) => r.id)).toEqual(["r1", "r2"]);
    expect(threads[1].replies).toEqual([]);
  });

  it("keeps hidden comments in the thread so they can be restored", () => {
    const threads = groupTipThreads([
      tip({ id: "p1" }),
      tip({ id: "r1", parent_id: "p1", status: "hidden" }),
    ]);
    expect(threads[0].replies[0].status).toBe("hidden");
  });

  it("treats an orphan reply (parent absent) as its own root", () => {
    const threads = groupTipThreads([tip({ id: "r1", parent_id: "gone" })]);
    expect(threads).toHaveLength(1);
    expect(threads[0].root.id).toBe("r1");
  });
});
