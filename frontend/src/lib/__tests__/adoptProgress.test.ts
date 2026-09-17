import { afterEach, describe, expect, it, vi } from "vitest";
import { adoptMediaWithProgress, ApiError } from "../api";

const body = {
  entity_type: "spot" as const,
  entity_id: "11111111-1111-1111-1111-111111111111",
  role: "hero" as const,
  provider: "pexels",
  external_id: "photo-1",
};

function streamedResponse(events: object[]): Response {
  const text = events.map((event) => JSON.stringify(event)).join("\n") + "\n";
  const split = Math.floor(text.length / 2);
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text.slice(0, split)));
      controller.enqueue(encoder.encode(text.slice(split)));
      controller.close();
    },
  }), { headers: { "Content-Type": "application/x-ndjson" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("adoptMediaWithProgress", () => {
  it("reads split progress events and waits for the committed result", async () => {
    vi.stubGlobal("document", { cookie: "swd_csrf=token123" });
    const result = {
      entity_type: "spot", entity_id: body.entity_id, role: "hero",
      image: { url: "https://example.com/hero.webp" }, gallery_image_id: null,
      demoted_hero: false, warnings: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(streamedResponse([
      { type: "progress", percent: 0, message: "Start" },
      { type: "progress", percent: 45, message: "Heruntergeladen" },
      { type: "result", result },
    ]));
    vi.stubGlobal("fetch", fetchMock);
    const received: number[] = [];

    const adopted = await adoptMediaWithProgress(body, ({ percent }) => received.push(percent));

    expect(received).toEqual([0, 45]);
    expect(adopted).toEqual(result);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      credentials: "include",
      headers: { "X-CSRF-Token": "token123" },
    });
  });

  it("preserves a duplicate error sent inside the stream", async () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamedResponse([
      { type: "progress", percent: 25, message: "Geprüft" },
      { type: "error", status: 409, message: "Schon verwendet", detail: { code: "duplicate_hero", message: "Schon verwendet" } },
    ])));

    await expect(adoptMediaWithProgress(body, () => {})).rejects.toMatchObject({
      name: "ApiError", status: 409, detail: { detail: { code: "duplicate_hero" } },
    } satisfies Partial<ApiError>);
  });

  it("explains a gateway timeout before the stream starts", async () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway Timeout", { status: 504 }),
    ));

    await expect(adoptMediaWithProgress(body, () => {})).rejects.toMatchObject({
      status: 504,
      message: expect.stringContaining("prüfen, ob das Hero-Bild bereits übernommen wurde"),
    });
  });
});
