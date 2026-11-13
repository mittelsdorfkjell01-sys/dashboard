import { getAdminKey } from "../adminKey";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function alignLoopbackApiHost(base: string, pageHostname?: string): string {
  if (!pageHostname || !LOOPBACK_HOSTS.has(pageHostname) || !/^https?:\/\//i.test(base)) {
    return base;
  }
  const url = new URL(base);
  if (LOOPBACK_HOSTS.has(url.hostname)) url.hostname = pageHostname;
  return url.toString().replace(/\/$/, "");
}

const configuredApiBase =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

export const API_BASE: string = alignLoopbackApiHost(
  configuredApiBase,
  typeof window === "undefined" ? undefined : window.location.hostname,
);

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function publicApiErrorMessage(status: number, fallback?: string | null): string {
  if (status === 0) return fallback || "Verbindung zum Datendienst fehlgeschlagen.";
  if (status === 404) {
    return fallback && !/not found/i.test(fallback)
      ? fallback
      : "Der angeforderte Inhalt wurde nicht gefunden.";
  }
  if (status === 429) return "Zu viele Anfragen auf einmal. Bitte warte kurz und versuche es erneut.";
  if (status >= 500) {
    return "Unser Datendienst ist gerade nicht erreichbar. Bitte versuche es in Kürze erneut.";
  }
  return fallback || `Anfrage fehlgeschlagen (${status}).`;
}

const REQUEST_TIMEOUT_MS = 15_000;
type RequestOptions = RequestInit & { timeoutMs?: number };

function cookieValue(name: string): string | undefined {
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

export function addAuthHeaders(path: string, method: string, headers: Record<string, string>): void {
  if (["GET", "HEAD"].includes(method) && cookieValue("swd_csrf")) {
    headers.Authorization = "Session";
  }
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrf = cookieValue("swd_csrf");
    if (csrf) headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  }
  const devKey = import.meta.env.VITE_ADMIN_KEY as string | undefined;
  if (devKey) {
    headers["X-Admin-Key"] = devKey;
  } else if (path.startsWith("/admin")) {
    const key = getAdminKey();
    if (key) headers["X-Admin-Key"] = key;
  }
}

export async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const { timeoutMs = REQUEST_TIMEOUT_MS, ...fetchInit } = init ?? {};
  const headers: Record<string, string> = {
    ...(fetchInit.body && !(fetchInit.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...((fetchInit.headers as Record<string, string>) || {}),
  };
  const method = (fetchInit.method ?? "GET").toUpperCase();
  addAuthHeaders(path, method, headers);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = fetchInit.signal;
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...fetchInit,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (error) {
    const aborted = error instanceof DOMException && error.name === "AbortError";
    const offline = typeof navigator !== "undefined" && navigator.onLine === false;
    throw new ApiError(
      aborted
        ? "Zeitüberschreitung — der Server hat nicht rechtzeitig geantwortet."
        : offline
          ? "Du bist offline. Prüfe deine Verbindung und versuche es erneut."
          : "Verbindung zum Datendienst fehlgeschlagen. Bitte versuche es erneut.",
      0,
      error,
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      // Non-JSON error response.
    }
    const serverMessage =
      detail && typeof detail === "object" && "detail" in detail
        ? typeof detail.detail === "string"
          ? detail.detail
          : typeof detail.detail === "object" && detail.detail !== null &&
              "message" in detail.detail && typeof detail.detail.message === "string"
            ? detail.detail.message
            : JSON.stringify(detail.detail)
        : null;
    throw new ApiError(
      publicApiErrorMessage(response.status, serverMessage),
      response.status,
      detail,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function queryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => search.append(key, String(item)));
    else search.append(key, String(value));
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}
