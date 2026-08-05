import { describe, expect, it } from "vitest";
import {
  adminSectionLabel,
  createAdminReturnState,
  readAdminReturnTarget,
} from "../adminNavigation";

describe("admin navigation context", () => {
  it("preserves path, filters and hash", () => {
    expect(
      createAdminReturnState(
        {
          pathname: "/admin/spots",
          search: "?status=draft&offset=25",
          hash: "#list",
        },
        "Spots"
      )
    ).toEqual({
      adminReturn: {
        to: "/admin/spots?status=draft&offset=25#list",
        label: "Spots",
      },
    });
  });

  it("accepts only internal admin return targets", () => {
    expect(
      readAdminReturnTarget({
        adminReturn: { to: "/admin/review?tab=hero", label: "Review" },
      })
    ).toEqual({ to: "/admin/review?tab=hero", label: "Review" });
    expect(
      readAdminReturnTarget({
        adminReturn: { to: "/admin?focus=board", label: "Übersicht" },
      })
    ).toEqual({ to: "/admin?focus=board", label: "Übersicht" });

    expect(
      readAdminReturnTarget({
        adminReturn: { to: "https://example.com", label: "Extern" },
      })
    ).toBeNull();
    expect(
      readAdminReturnTarget({ adminReturn: { to: "/spot/123", label: "Spot" } })
    ).toBeNull();
  });

  it("derives concise labels for notification entry points", () => {
    expect(adminSectionLabel("/admin/map")).toBe("Karte");
    expect(adminSectionLabel("/admin/activity")).toBe("Aktivität");
    expect(adminSectionLabel("/admin/spot/123/edit")).toBe("Spot");
  });
});
