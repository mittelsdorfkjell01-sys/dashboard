import { describe, expect, it } from "vitest";
import { normalizeBottomTypes } from "../labels";

describe("normalizeBottomTypes", () => {
  it("turns a legacy label and a duplicate key into one API value", () => {
    expect(normalizeBottomTypes(["Sand", "sand"])).toEqual(["sand"]);
    expect(normalizeBottomTypes(["Fels", "Riff", "Gemischt (nicht näher bestimmt)"]))
      .toEqual(["rock", "reef", "mixed"]);
  });

  it("keeps unknown stored values visible to future migration work", () => {
    expect(normalizeBottomTypes(["n/a", "sand"])).toEqual(["n/a", "sand"]);
  });
});
