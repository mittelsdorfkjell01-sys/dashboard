import { describe, expect, it } from "vitest";
import { ApiError } from "../api";
import { parseDuplicateConflict } from "../duplicateConflicts";

describe("duplicate API conflicts", () => {
  it("parses structured duplicate candidates", () => {
    const conflict = parseDuplicateConflict(new ApiError("conflict", 409, {
      detail: {
        code: "likely_duplicate",
        entity: "spot",
        message: "Mögliche Dublette",
        candidates: [{ id: "1", name: "Laboe", distance_m: 120 }],
        override_allowed: true,
      },
    }));
    expect(conflict?.candidates[0]).toMatchObject({ name: "Laboe", distance_m: 120 });
    expect(conflict?.override_allowed).toBe(true);
  });

  it("does not confuse optimistic-lock conflicts with duplicates", () => {
    expect(parseDuplicateConflict(new ApiError("stale", 409, {
      detail: { code: "stale_write" },
    }))).toBeNull();
  });
});
