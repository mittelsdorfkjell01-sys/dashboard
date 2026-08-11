// Public account API. Talks to the FastAPI /account endpoints (see
// app/api/account.py). Auth is an httpOnly session cookie set by the server —
// this module never sees a token; `request` sends credentials on every call.
//
// Favourites and submissions expose a SYNCHRONOUS read surface (isFavorite,
// listFavorites, listMySubmissions) because the UI reads them during render. We
// back that with a small in-memory cache that `hydrate()` fills from the server
// once a session is established, then broadcast FAVORITES_EVENT / SUBMISSIONS_EVENT
// so mounted components re-read. Mutations update the cache optimistically and
// reconcile with the server in the background.

import { ApiError, request } from "./api";

export interface Account {
  id: string;
  email: string;
  displayName: string;
  createdAt: string; // ISO
}

export interface FavoriteSpot {
  id: string;
  name: string;
  region?: string | null;
  sports?: string[];
  addedAt: string;
}

// Mirrors the backend submission lifecycle (app/admin/moderation.py): a proposal
// is "pending", becomes "merged" once an admin turns it into a (draft) spot, or
// "rejected". The UI maps these to badges with a safe fallback for any value it
// does not recognise.
export type SubmissionStatus = "pending" | "merged" | "rejected";
export interface MySubmission {
  id: string;
  name: string;
  status: SubmissionStatus;
  createdAt: string;
}

/** Thrown for expected, user-facing failures (duplicate email, bad password …). */
export class AccountError extends Error {}

export const FAVORITES_EVENT = "swd:favorites";
export const SUBMISSIONS_EVENT = "swd:submissions";

/** Run an account request, surfacing the server's German detail as an
 *  AccountError the pages already know how to display. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    return await request<T>(path, init);
  } catch (e) {
    if (e instanceof ApiError) throw new AccountError(e.message);
    throw e;
  }
}

// --- in-memory caches ------------------------------------------------------

let favCache: FavoriteSpot[] = [];
let subsCache: MySubmission[] = [];

function emit(name: string): void {
  window.dispatchEvent(new CustomEvent(name));
}

function clearCaches(): void {
  favCache = [];
  subsCache = [];
  emit(FAVORITES_EVENT);
  emit(SUBMISSIONS_EVENT);
}

/** Load the signed-in user's favourites + submissions into the cache. Called
 *  after a session is confirmed; failures leave the caches empty (best-effort). */
async function hydrate(): Promise<void> {
  try {
    const [favs, subs] = await Promise.all([
      request<{ items: FavoriteSpot[] }>("/account/favorites"),
      request<{ items: MySubmission[] }>("/account/submissions"),
    ]);
    favCache = favs.items;
    subsCache = subs.items;
    emit(FAVORITES_EVENT);
    emit(SUBMISSIONS_EVENT);
  } catch {
    /* not logged in / offline → caches stay empty */
  }
}

// --- auth / session --------------------------------------------------------

/** Resolve the current session (or null). Hydrates the caches on success. Used
 *  by AuthContext on mount and after auth changes. */
export async function fetchSession(): Promise<Account | null> {
  try {
    const me = await request<Account>("/account/me");
    await hydrate();
    return me;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      clearCaches();
      return null;
    }
    throw e;
  }
}

export async function register(input: {
  email: string;
  password: string;
  displayName: string;
}): Promise<void> {
  await call<{ accepted: boolean; message: string }>("/account/register", {
    method: "POST",
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      displayName: input.displayName,
    }),
  });
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<Account> {
  const acc = await call<Account>("/account/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
  await hydrate();
  return acc;
}

export async function logout(): Promise<void> {
  try {
    await request("/account/logout", { method: "POST" });
  } finally {
    clearCaches();
  }
}

export async function updateProfile(patch: {
  displayName?: string;
  email?: string;
}): Promise<Account> {
  return call<Account>("/account/profile", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function changePassword(oldPw: string, newPw: string): Promise<void> {
  await call<void>("/account/password", {
    method: "POST",
    body: JSON.stringify({ oldPassword: oldPw, newPassword: newPw }),
  });
}

export async function downloadAccountExport(): Promise<void> {
  const data = await call<Record<string, unknown>>("/account/export");
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "surfwinddata-export.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function deleteAccount(password: string): Promise<void> {
  await call<void>("/account", {
    method: "DELETE",
    body: JSON.stringify({ password }),
  });
  clearCaches();
}

// --- favourites ------------------------------------------------------------

export function listFavorites(): FavoriteSpot[] {
  return favCache;
}

export function isFavorite(spotId: string): boolean {
  return favCache.some((f) => f.id === spotId);
}

/** Toggle a spot's favourite state. Returns the new state synchronously
 *  (optimistic); the server call runs in the background and rolls back on
 *  failure. Callers guard on auth before invoking (see FavoriteButton). */
export function toggleFavorite(spot: {
  id: string;
  name: string;
  region?: string | null;
  sports?: string[];
}): boolean {
  const exists = favCache.some((f) => f.id === spot.id);
  if (exists) {
    removeFavorite(spot.id);
    return false;
  }
  const prev = favCache;
  favCache = [
    {
      id: spot.id,
      name: spot.name,
      region: spot.region ?? null,
      sports: spot.sports ?? [],
      addedAt: new Date().toISOString(),
    },
    ...favCache,
  ];
  emit(FAVORITES_EVENT);
  request(`/account/favorites/${spot.id}`, { method: "PUT" }).catch(() => {
    favCache = prev; // rollback
    emit(FAVORITES_EVENT);
  });
  return true;
}

export function removeFavorite(spotId: string): void {
  const prev = favCache;
  favCache = favCache.filter((f) => f.id !== spotId);
  emit(FAVORITES_EVENT);
  request(`/account/favorites/${spotId}`, { method: "DELETE" }).catch(() => {
    favCache = prev; // rollback
    emit(FAVORITES_EVENT);
  });
}

// --- my submissions --------------------------------------------------------

export function listMySubmissions(): MySubmission[] {
  return subsCache;
}

/** Propose a spot by name. POSTs to the server, then prepends the stored row to
 *  the cache and notifies the list. */
export async function addSubmission(name: string): Promise<MySubmission> {
  const sub = await call<MySubmission>("/account/submissions", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  subsCache = [sub, ...subsCache];
  emit(SUBMISSIONS_EVENT);
  return sub;
}
