import { API_BASE, request } from "./api";

export type EventType =
  | "impression"
  | "click"
  | "favorite_add"
  | "favorite_remove"
  | "dismiss"
  | "search"
  | "session_checkin";

interface BufferedEvent {
  type: EventType;
  anonId: string;
  spotId?: string;
  surface?: string;
  context: Record<string, unknown>;
}

const STORAGE_KEY = "swd.anonymous-event-id.v1";
const FLUSH_DELAY_MS = 5_000;
const MAX_BATCH = 50;
const buffer: BufferedEvent[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;
let flushing = false;

function createAnonymousId(): string {
  if (typeof globalThis.crypto !== "undefined" && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function anonymousEventId(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    const created = createAnonymousId();
    localStorage.setItem(STORAGE_KEY, created);
    return created;
  } catch {
    return createAnonymousId();
  }
}

function scheduleFlush(): void {
  if (timer !== null) return;
  timer = setTimeout(() => {
    timer = null;
    void flushEvents();
  }, FLUSH_DELAY_MS);
}

export function trackEvent(
  type: EventType,
  input: { spotId?: string; surface?: string; context?: Record<string, unknown> } = {},
): void {
  buffer.push({
    type,
    anonId: anonymousEventId(),
    spotId: input.spotId,
    surface: input.surface,
    context: input.context ?? {},
  });
  if (buffer.length >= MAX_BATCH) void flushEvents();
  else scheduleFlush();
}

export async function flushEvents(): Promise<void> {
  if (flushing || buffer.length === 0) return;
  flushing = true;
  const batch = buffer.slice(0, MAX_BATCH);
  try {
    await request<{ accepted: number }>("/events", {
      method: "POST",
      body: JSON.stringify({ events: batch }),
      timeoutMs: 5_000,
    });
    buffer.splice(0, batch.length);
  } catch {
    // Telemetry never interrupts the user's task. The next event or page exit
    // gets one more chance to send this in-memory batch.
  } finally {
    flushing = false;
    if (buffer.length > 0) scheduleFlush();
  }
}

function flushWithBeacon(): void {
  if (buffer.length === 0 || typeof navigator === "undefined" || !navigator.sendBeacon) return;
  const batch = buffer.slice(0, MAX_BATCH);
  const payload = new Blob([JSON.stringify({ events: batch })], { type: "application/json" });
  if (navigator.sendBeacon(`${API_BASE}/events`, payload)) buffer.splice(0, batch.length);
}

if (typeof window !== "undefined") {
  window.addEventListener("pagehide", flushWithBeacon);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushWithBeacon();
  });
}
