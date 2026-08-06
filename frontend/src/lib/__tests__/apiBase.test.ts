import { describe, expect, it } from "vitest";
import { alignLoopbackApiHost } from "../api";

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
