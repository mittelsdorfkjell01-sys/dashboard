// Public account API. Talks to the FastAPI /account endpoints (see
// app/api/account.py). Auth is an httpOnly session cookie set by the server —
// this module never sees a token; `request` sends credentials on every call.
//
// Favourites and submissions expose a SYNCHRONOUS read surface (isFavorite,
// listFavorites, listMySubmissions) because the UI reads them during render. We
// back that with a small in-memory cache that `hydrate()` fills from the server
// once a session is established, then broadcast FAVORITES_EVENT / SUBMISSIONS_EVENT
// so mounted components re-read. Mutations update the cache only after the
// server confirms them.

import { ApiError, request } from "./api";
import { trackEvent } from "./events";

export interface Account {
  id: string;
  email: string;
  displayName: string;
  createdAt: string; // ISO
  emailVerified: boolean;
  pendingEmail: string | null;
  mailAvailable: boolean;
  preferences: {
    units?: { wind: "kn" | "bft" | "ms"; wave: "m" | "ft"; temp: "c" | "f"; distance: "km" | "mi" };
    sports?: string[];
    conditions?: Partial<Record<SportKey, SportConditions>>;
    submissionEmails?: boolean;
  };
}

export type SportKey = "surf" | "windsurf" | "kitesurf" | "wing";

/** Canonical account thresholds: knots, metres and degrees Celsius. */
export interface SportConditions {
  windMinKn?: number | null;
  windMaxKn?: number | null;
  waveMinM?: number | null;
  waveMaxM?: number | null;
  waterTempMinC?: number | null;
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
export type SubmissionStatus = "pending" | "merged" | "rejected" | "withdrawn";
export interface MySubmission {
  id: string;
  name: string;
  status: SubmissionStatus;
  createdAt: string;
  updatedAt?: string | null;
  reviewedAt?: string | null;
  reviewNote?: string | null;
  resultingSpotId?: string | null;
  publishedSpotId?: string | null;
  regionId?: string | null;
  lat?: number | null;
  lon?: number | null;
  sports?: string[];
}

export type CollectionStatus = "idle" | "loading" | "ready" | "error";
export interface CollectionState<T> { items: T[]; status: CollectionStatus; error: string | null; hasMore?: boolean }
export interface AccountActivity {
  id: string;
  kind: "rating" | "tip" | "image" | "correction";
  spotId: string | null;
  createdAt: string;
  status: string;
  reviewNote?: string | null;
}

export type RiderLevel = "beginner" | "advanced" | "expert" | "competition";
export type TravelMode = "day_trip" | "weekend" | "trip" | "camper";
export type BoardType = "twintip" | "surfboard" | "foil" | "bigair_twintip";
export type GearKind = "kite" | "board" | "foil";

export interface RiderProfile {
  weightKg: number | null;
  homeLocation: { lat: number; lon: number } | null;
  maxTravelKm: number | null;
  travelMode: TravelMode;
  availability: number[];
  minWaterTempC: number | null;
  excludedBottoms: string[];
  profileVersion: number;
}

export interface RiderSportProfile {
  sport: SportKey;
  level: RiderLevel | null;
  styleWeights: Record<string, number>;
  preferredWaterCharacter: string[];
  profileVersion: number;
}

export interface GearItem {
  id: string;
  sport: SportKey;
  kind: GearKind;
  size: number | null;
  boardType: BoardType | null;
  active: boolean;
  sortOrder: number;
  profileVersion: number;
}

export type GearItemInput = Omit<GearItem, "id" | "profileVersion">;

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
let favoritesStatus: CollectionStatus = "idle";
let submissionsStatus: CollectionStatus = "idle";
let favoritesError: string | null = null;
let submissionsError: string | null = null;
let submissionsHasMore = false;

function emit(name: string): void {
  window.dispatchEvent(new CustomEvent(name));
}

function clearCaches(): void {
  favCache = [];
  subsCache = [];
  favoritesStatus = submissionsStatus = "idle";
  favoritesError = submissionsError = null;
  submissionsHasMore = false;
  emit(FAVORITES_EVENT);
  emit(SUBMISSIONS_EVENT);
}

/** Load the signed-in user's favourites + submissions into the cache. Called
 *  after a session is confirmed; failures remain visible for explicit retry. */
export async function refreshFavorites(): Promise<void> {
  favoritesStatus = "loading";
  favoritesError = null;
  emit(FAVORITES_EVENT);
  try {
    favCache = (await call<{ items: FavoriteSpot[] }>("/account/favorites")).items;
    favoritesStatus = "ready";
  } catch (error) {
    favoritesStatus = "error";
    favoritesError = error instanceof Error ? error.message : "Favoriten konnten nicht geladen werden.";
  }
  emit(FAVORITES_EVENT);
}

export async function refreshSubmissions(): Promise<void> {
  submissionsStatus = "loading";
  submissionsError = null;
  emit(SUBMISSIONS_EVENT);
  try {
    const page = await call<{ items: MySubmission[]; hasMore: boolean }>("/account/submissions?limit=50&offset=0");
    subsCache = page.items;
    submissionsHasMore = page.hasMore;
    submissionsStatus = "ready";
  } catch (error) {
    submissionsStatus = "error";
    submissionsError = error instanceof Error ? error.message : "Vorschläge konnten nicht geladen werden.";
  }
  emit(SUBMISSIONS_EVENT);
}

async function hydrate(): Promise<void> {
  await Promise.all([refreshFavorites(), refreshSubmissions()]);
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
  displayName: string;
}): Promise<void> {
  await call<{ accepted: boolean; message: string }>("/account/register", {
    method: "POST",
    body: JSON.stringify({
      email: input.email,
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
}): Promise<Account> {
  return call<Account>("/account/profile", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export const requestEmailChange = (email: string, password: string) =>
  call<Account>("/account/email/change", { method: "POST", body: JSON.stringify({ email, password }) });

export const confirmEmail = (token: string, password?: string) =>
  call<Account>("/account/email/confirm", { method: "POST", body: JSON.stringify({ token, password }) });

export const requestPasswordReset = (email: string) =>
  call<{ accepted: boolean }>("/account/password-reset/request", { method: "POST", body: JSON.stringify({ email }) });

export const confirmPasswordReset = (token: string, password: string) =>
  call<void>("/account/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, password }) });

let preferencesQueue: Promise<void> = Promise.resolve();

/** Serialize independent settings panels so the last server snapshot wins. */
export function updatePreferences(patch: Account["preferences"]): Promise<Account> {
  const operation = preferencesQueue.then(() => call<Account>("/account/preferences", {
    method: "PATCH", body: JSON.stringify(patch),
  }));
  preferencesQueue = operation.then(() => undefined, () => undefined);
  return operation;
}

export const fetchAccountActivity = () =>
  call<{ items: AccountActivity[] }>("/account/activity");

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

// --- private rider setup --------------------------------------------------

export const getRiderProfile = () => call<RiderProfile>("/account/rider-profile");

export const putRiderProfile = (profile: Omit<RiderProfile, "profileVersion">) =>
  call<RiderProfile>("/account/rider-profile", {
    method: "PUT", body: JSON.stringify(profile),
  });

export const getRiderSportProfile = (sport: SportKey) =>
  call<RiderSportProfile>(`/account/rider-profile/${sport}`);

export const putRiderSportProfile = (
  sport: SportKey,
  profile: Pick<RiderSportProfile, "level" | "styleWeights" | "preferredWaterCharacter">,
) => call<RiderSportProfile>(`/account/rider-profile/${sport}`, {
  method: "PUT", body: JSON.stringify(profile),
});

export const getGear = async (sport?: SportKey) =>
  (await call<{ items: GearItem[] }>(`/account/gear${sport ? `?sport=${sport}` : ""}`)).items;

export const createGearItem = (item: GearItemInput) =>
  call<GearItem>("/account/gear", { method: "POST", body: JSON.stringify(item) });

export const updateGearItem = (id: string, item: GearItemInput) =>
  call<GearItem>(`/account/gear/${id}`, { method: "PUT", body: JSON.stringify(item) });

export const deleteGearItem = (id: string) =>
  call<void>(`/account/gear/${id}`, { method: "DELETE" });

export function getFavoritesState(): CollectionState<FavoriteSpot> {
  return { items: favCache, status: favoritesStatus, error: favoritesError };
}

export function isFavorite(spotId: string): boolean {
  return favCache.some((f) => f.id === spotId);
}

/** Toggle a spot's favourite state after the server confirms the mutation. */
export async function toggleFavorite(spot: {
  id: string;
  name: string;
  region?: string | null;
  sports?: string[];
}): Promise<boolean> {
  const exists = favCache.some((f) => f.id === spot.id);
  if (exists) {
    await removeFavorite(spot.id);
    return false;
  }
  await call<void>(`/account/favorites/${spot.id}`, { method: "PUT" });
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
  trackEvent("favorite_add", { spotId: spot.id, surface: "spot" });
  return true;
}

export async function removeFavorite(spotId: string): Promise<void> {
  await call<void>(`/account/favorites/${spotId}`, { method: "DELETE" });
  favCache = favCache.filter((f) => f.id !== spotId);
  emit(FAVORITES_EVENT);
  trackEvent("favorite_remove", { spotId, surface: "spot" });
}

// --- my submissions --------------------------------------------------------

export function listMySubmissions(): MySubmission[] {
  return subsCache;
}

export function getSubmissionsState(): CollectionState<MySubmission> {
  return { items: subsCache, status: submissionsStatus, error: submissionsError, hasMore: submissionsHasMore };
}

export async function loadMoreSubmissions(): Promise<void> {
  if (!submissionsHasMore || submissionsStatus === "loading") return;
  submissionsStatus = "loading";
  emit(SUBMISSIONS_EVENT);
  try {
    const page = await call<{ items: MySubmission[]; hasMore: boolean }>(
      `/account/submissions?limit=50&offset=${subsCache.length}`
    );
    subsCache = [...subsCache, ...page.items];
    submissionsHasMore = page.hasMore;
    submissionsError = null;
    submissionsStatus = "ready";
  } catch (error) {
    submissionsError = error instanceof Error ? error.message : "Weitere Vorschläge konnten nicht geladen werden.";
    submissionsStatus = "error";
  }
  emit(SUBMISSIONS_EVENT);
}

/** Propose a spot by name. POSTs to the server, then prepends the stored row to
 *  the cache and notifies the list. */
export async function addSubmission(input: {
  name: string; regionId?: string; lat?: number; lon?: number; sports?: string[];
}): Promise<MySubmission> {
  const sub = await call<MySubmission>("/account/submissions", {
    method: "POST",
    body: JSON.stringify(input),
  });
  subsCache = [sub, ...subsCache];
  emit(SUBMISSIONS_EVENT);
  return sub;
}

export async function withdrawSubmission(id: string): Promise<void> {
  await call<void>(`/account/submissions/${id}`, { method: "DELETE" });
  subsCache = subsCache.map((sub) => sub.id === id ? { ...sub, status: "withdrawn" } : sub);
  emit(SUBMISSIONS_EVENT);
}

export async function findSimilarSpots(q: string): Promise<{ id: string; name: string }[]> {
  return (await call<{ items: { id: string; name: string }[] }>(
    `/account/submissions/similar?q=${encodeURIComponent(q)}`
  )).items;
}
