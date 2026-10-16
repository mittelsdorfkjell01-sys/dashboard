import { describe, expect, it } from "vitest";
import { alignLoopbackApiHost, publicApiErrorMessage } from "../api";

describe("alignLoopbackApiHost", () => {
  it("uses the page loopback host so session and CSRF cookies share an origin", () => {
    expect(alignLoopbackApiHost("http://localhost:8000", "127.0.0.1")).toBe(
      "http://127.0.0.1:8000",
    );
    expect(alignLoopbackApiHost("http://127.0.0.1:8000", "localhost")).toBe(
      "http://localhost:8000",
    );
  });

  it("does not rewrite production or root-relative API bases", () => {
    expect(alignLoopbackApiHost("/api", "127.0.0.1")).toBe("/api");
    expect(alignLoopbackApiHost("https://api.example.com", "localhost")).toBe(
      "https://api.example.com",
    );
  });
});

describe("publicApiErrorMessage", () => {
  it("hides internal server details behind a recoverable public message", () => {
    expect(publicApiErrorMessage(500, "database host secret")).toBe(
      "Unser Datendienst ist gerade nicht erreichbar. Bitte versuche es in Kürze erneut.",
    );
    expect(publicApiErrorMessage(503, "Internal Server Error")).not.toContain("Internal");
  });

  it("translates generic not-found responses but preserves useful validation copy", () => {
    expect(publicApiErrorMessage(404, "Spot not found")).toBe(
      "Der angeforderte Inhalt wurde nicht gefunden.",
    );
    expect(publicApiErrorMessage(422, "Bitte wähle eine Sportart.")).toBe(
      "Bitte wähle eine Sportart.",
    );
  });
});
