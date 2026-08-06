import { describe, expect, it } from "vitest";
import { areFormValuesEqual, stableFormValue } from "../useUnsavedChangesGuard";

describe("unsaved form value comparison", () => {
  it("treats unchanged values and object key order as clean", () => {
    expect(areFormValuesEqual({ name: "Laboe", sports: ["surf"] }, {
      sports: ["surf"], name: "Laboe",
    })).toBe(true);
  });

  it("detects edits and becomes clean again when values are reverted", () => {
    const initial = { name: "Laboe", region: "Ostsee" };
    expect(areFormValuesEqual({ ...initial, name: "Laboe Hafen" }, initial)).toBe(false);
    expect(areFormValuesEqual({ ...initial, name: "Laboe" }, initial)).toBe(true);
  });

  it("creates a deterministic fingerprint for nested form data", () => {
    expect(stableFormValue({ b: { y: 2, x: 1 }, a: [3, 4] })).toBe(
      stableFormValue({ a: [3, 4], b: { x: 1, y: 2 } })
    );
  });
});
