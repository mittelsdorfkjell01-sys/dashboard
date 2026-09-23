import { afterEach, describe, expect, it, vi } from "vitest";
import { getRecommendations } from "../api";

afterEach(() => vi.unstubAllGlobals());

describe("recommendation cache authentication", () => {
  it("bypasses the edge cache for an account session", async () => {
    vi.stubGlobal("document", { cookie: "swd_csrf=token123" });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getRecommendations({ surface: "now" });

    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      credentials: "include",
      headers: { Authorization: "Session" },
    });
  });

  it("keeps anonymous recommendations eligible for edge caching", async () => {
    vi.stubGlobal("document", { cookie: "" });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getRecommendations({ surface: "now" });

    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty("Authorization");
  });
});
