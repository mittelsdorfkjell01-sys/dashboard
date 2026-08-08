// Thin, typed fetch wrapper around the Surfwinddate FastAPI backend.
// Base URL comes from VITE_API_URL (default http://localhost:8000). Every call
// returns typed data or throws an ApiError the UI can surface.

import { getAdminKey } from "./adminKey";
import type {
  MediaEntityType,
  MediaItem,
  MediaRole,
  ProviderKey,
  TabStatus,
} from "./mediaPicker";

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

/** Resolve a possibly root-relative URL (e.g. "/media/…") against the API host. */
export function resolveMediaUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/")) return `${API_BASE}${url}`;
  return url;
}

/** Seed rows carry an unreachable `*.local` sentinel host. */
const SENTINEL_HOST = /^https?:\/\/[^/]+\.local\b/i;

/**
 * Resolve a media URL, but report unreachable seed sentinels as absent so
 * callers render their designed no-image state instead of a broken <img>.
 */
export function usableMediaUrl(url?: string | null): string | undefined {
  const resolved = resolveMediaUrl(url);
  return resolved && !SENTINEL_HOST.test(resolved) ? resolved : undefined;
}

// --- backend shapes --------------------------------------------------------

export interface GeoPoint {
  lat: number;
  lon: number;
}

/**
 * The `image` object stored on spots and regions. Written server-side by
 * `app/media/image_object.py` — a license *snapshot* (the terms as they read
 * when the photo was fetched), not a reference, because photos get deleted and
 * provider terms change.
 */
export interface ImageRecord {
  url: string;
  /** Display name of the origin ("Unsplash", "upload", "wikimedia_commons"). */
  source?: string;
  license?: string;
  license_url?: string | null;
  credit?: string;
  /** Photographer profile link — attribution is mandatory for every provider. */
  credit_url?: string | null;
  /** Machine slug: unsplash | pexels | wikimedia | openverse | upload |
   *  community | manual | seed | unknown. */
  provider?: string;
  external_id?: string | null;
  /** The photo's detail page at the provider. */
  source_page?: string | null;
  retrieved_at?: string | null;
  /** hotlinked = provider CDN (Unsplash requires it); hosted = our storage. */
  delivery?: "hotlinked" | "hosted";
  /** Focal point as object-position percentages (0..100). */
  focal?: { x: number; y: number };
  /** Mobile-specific focal point (used under ≈640px). Optional — when absent,
   *  the mobile crop falls back to `focal`. */
  focal_mobile?: { x: number; y: number } | null;
  width?: number | null;
  height?: number | null;
  /** True only where coordinate proximity was actually established. */
  geo_verified?: boolean;
  role?: "hero" | "gallery";
  /** Source health from the maintenance check: "ok" | "dead" | null (never
   *  checked). Photos get deleted and accounts vanish. */
  source_status?: "ok" | "dead" | null;
  source_checked_at?: string | null;
}

export type FacilityKind = "parking" | "shower" | "food" | "camping" | "school";
export type FacilityMap = Partial<
  Record<FacilityKind, { available: boolean; note?: string }>
>;

export interface SpotSummary {
  id: string;
  slug: string;
  name: string;
  region_id: string | null;
  location: GeoPoint | null;
  sports: string[];
  water_type: string[];
  bottom_type: string[];
  level: string[];
  water_character: string[];
  style: string[];
  facilities: FacilityMap | null;
  status: string;
  confidence: number | null;
  facing: number | null;
  image: ImageRecord | null;
}

export interface SpotRead extends SpotSummary {
  era5_cell: Record<string, unknown> | null;
  model_pref: string | null;
  editorial: Record<string, any> | null;
  climatology: Record<string, any> | null;
  overrides: Record<string, any> | null;
  finish_rank: Rank | null;
  created_at: string;
  updated_at: string;
}

export type TideQuality =
  | "unavailable"
  | "model_only"
  | "reviewed_anchor"
  | "manual_calibrated"
  | "gauge_calibrated";

export interface TideEvent {
  id: string;
  event_type: "high" | "low";
  raw_time: string | null;
  time: string;
  uncertainty_minutes: number;
  profile_version: number;
  overridden: boolean;
}

export interface PublicTideEvent {
  id: string;
  event_type: "high" | "low";
  time: string;
  uncertainty_minutes: number;
}

export interface PublicTides {
  available: boolean;
  message: string | null;
  timezone: string | null;
  phase: "rising" | "high" | "falling" | "low" | "unavailable";
  cycle_position: number | null;
  quality: TideQuality;
  approximate: boolean;
  last_calculated_at: string | null;
  valid_until: string | null;
  events: PublicTideEvent[];
}

export interface TideOverride {
  id: string;
  event_type: "high" | "low";
  raw_time: string;
  original_model_time: string;
  manual_time: string;
  difference_minutes: number;
  scope: "single" | "high_profile" | "low_profile" | "calibration_input";
  reason: string;
  source: string | null;
  actor: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TideProfile {
  id: string;
  spot_id: string;
  enabled: boolean;
  public_enabled: boolean;
  timezone: string | null;
  model_name: string;
  model_version: string;
  automatic_anchor: GeoPoint | null;
  manual_anchor: GeoPoint | null;
  effective_anchor: GeoPoint | null;
  anchor_distance_m: number | null;
  anchor_kind: string | null;
  anchor_status: "needs_review" | "auto_selected" | "reviewed" | "invalid";
  anchor_warnings: string[] | null;
  global_offset_minutes: number;
  high_offset_minutes: number;
  low_offset_minutes: number;
  manual_uncertainty_minutes: number | null;
  estimated_uncertainty_minutes: number | null;
  uncertainty_source: string | null;
  quality_status: TideQuality;
  note: string | null;
  correction_reason: string | null;
  correction_source: string | null;
  version: number;
  last_calculated_at: string | null;
  calculation_status: "not_configured" | "queued" | "running" | "ready" | "failed" | "stale";
  calculation_error: string | null;
  updated_at: string;
  events: TideEvent[];
  overrides: TideOverride[];
  latest_run: Record<string, unknown> | null;
  limits: {
    soft_offset_minutes: number;
    hard_offset_minutes: number;
    reason_required_minutes: number;
  };
}

export interface Region {
  id: string;
  slug: string;
  name: string;
  country: string | null;
  center: GeoPoint | null;
  description: string | null;
  image: ImageRecord | null;
  season: Record<string, any> | null;
  defaults: Record<string, any> | null;
  status: string;
  updated_at: string;
}

export interface CurrentConditions {
  wind: number | null;
  gust: number | null;
  dir: number | null;
  air: number | null;
  sst: number | null;
  swell: number | null;
  period: number | null;
  swell_dir: number | null;
}

export interface LiveConditionsRead {
  spot_id: string;
  model: string;
  time: string | null;
  current: CurrentConditions;
}

export interface ForecastDaySummary {
  wind_avg: number | null;
  wind_max: number | null;
  gust_max: number | null;
  air_min: number | null;
  air_max: number | null;
  swell_max: number | null;
}
export interface ForecastHour {
  time: string;
  wind: number | null;
  gust: number | null;
  dir: number | null;
  air: number | null;
  swell: number | null;
  period: number | null;
  swell_dir: number | null;
  precip: number | null; // mm/h
  sst: number | null; // deg C
}
export interface ForecastDay {
  date: string;
  confidence: string;
  summary: ForecastDaySummary;
  hours: ForecastHour[];
}
export interface ForecastSeries {
  spot_id: string;
  model: string;
  generated_at: string;
  days: ForecastDay[];
}

export interface SpotSeason {
  stage: number;
  spot_id: string;
  [k: string]: unknown;
}

export interface RegionSeasonResponse {
  region_id: string;
  season: {
    weeks?: Array<{
      week: number;
      spots_working?: number;
      wind_p50?: number | null;
      sst_p50?: number | null;
      air_p50?: number | null;
    }>;
    [k: string]: unknown;
  };
}

export interface ReadinessItem {
  field: string;
  severity: string;
  ok: boolean;
  na: boolean;
}

export interface Readiness {
  spot_id: string;
  status: string;
  ready: boolean;
  checklist: ReadinessItem[];
  gaps: string[];
}

// --- request core ----------------------------------------------------------

const REQUEST_TIMEOUT_MS = 15000;
type RequestOptions = RequestInit & { timeoutMs?: number };

function cookieValue(name: string): string | undefined {
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
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
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrf = cookieValue("swd_csrf");
    if (csrf) headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  }
  // LOCAL DEV break-glass: when VITE_ADMIN_KEY is set, send it on EVERY request
  // (incl. /auth/me) so the admin area works without the cookie login. Falls back
  // to a session-entered key on /admin only. Unset in prod → normal cookie auth.
  const devKey = import.meta.env.VITE_ADMIN_KEY as string | undefined;
  if (devKey) {
    headers["X-Admin-Key"] = devKey;
  } else if (path.startsWith("/admin")) {
    const key = getAdminKey();
    if (key) headers["X-Admin-Key"] = key;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...fetchInit,
      headers,
      // Send/receive the httpOnly session cookie (Sprint A auth) on every call.
      credentials: "include",
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = e instanceof DOMException && e.name === "AbortError";
    throw new ApiError(
      aborted
        ? "Zeitüberschreitung — der Server hat nicht rechtzeitig geantwortet."
        : "Verbindung zum Server fehlgeschlagen. Läuft das Backend?",
      0,
      e
    );
  } finally {
    clearTimeout(timer);
  }
  if (!resp.ok) {
    let detail: unknown = null;
    try {
      detail = await resp.json();
    } catch {
      /* non-JSON error body */
    }
    const msg =
      (detail && typeof detail === "object" && "detail" in detail
        ? typeof (detail as any).detail === "string"
          ? (detail as any).detail
          : JSON.stringify((detail as any).detail)
        : null) || `Anfrage fehlgeschlagen (${resp.status}).`;
    throw new ApiError(msg, resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// Read caching lives in the SWR layer (see ./swr): it dedupes in-flight requests
// and serves stale-while-revalidate across the app on every build, so the public
// GET helpers below are plain fetches (no second, TTL-based cache underneath).

function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)));
    else sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// --- public endpoints ------------------------------------------------------

export interface SpotQuery {
  region_id?: string;
  sport?: string;
  level?: string;
  water_character?: string;
  style?: string[];
  bottom_type?: string[];
  limit?: number;
  offset?: number;
}

export const getSpots = (params: SpotQuery = {}) =>
  request<SpotSummary[]>(`/spots${qs(params as Record<string, unknown>)}`);

/** "aktuelle Top Spots": published spots ranked by this week's wind forecast,
 *  today's conditions and popularity. Stable per day, rotates daily. */
export const getTopSpots = (limit = 5, sport?: string) =>
  request<SpotSummary[]>(`/spots/top${qs({ limit, sport })}`);

export const getSpot = (id: string) => request<SpotRead>(`/spots/${id}`);

export const getSpotTides = (id: string) =>
  request<PublicTides>(`/spots/${id}/tides`);

export const getSpotLive = (id: string) =>
  request<LiveConditionsRead>(`/spots/${id}/live`);

/** Batch live conditions for several spots in one round-trip (landing/map). */
export const getSpotsLive = (ids: string[]) =>
  request<LiveConditionsRead[]>(
    `/spots/live?ids=${encodeURIComponent(ids.join(","))}`
  );

/** Public region listing — published only. */
export const getRegions = () => request<Region[]>(`/regions`);

/** Flat protected region list (Region[], includes editorial states). */
export async function getAdminRegionsFlat(): Promise<Region[]> {
  const entries = await request<AdminRegionEntry[]>(`/admin/regions`);
  return entries.map((entry) => entry.region);
}

export const getRegion = (id: string) => request<Region>(`/regions/${id}`);

/** Resolve a published region by slug. */
export async function getRegionBySlug(slug: string): Promise<Region | undefined> {
  try {
    return await request<Region>(`/regions/by-slug/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return undefined;
    throw e;
  }
}

/** "Berechnen" mode: recompute best months from the region's spots' climatology. */
export const computeRegionMonths = (id: string) =>
  request<Region>(`/admin/regions/${id}/compute-months`, { method: "POST" });

export const publishRegion = (id: string) =>
  request<Region>(`/admin/regions/${id}/publish`, { method: "POST" });
export const unpublishRegion = (id: string) =>
  request<Region>(`/admin/regions/${id}/unpublish`, { method: "POST" });

export const getSpotForecast = (id: string, days?: number) =>
  request<ForecastSeries>(`/spots/${id}/forecast${qs({ days })}`);

/** Stage-2 season curve: pct_usable[52] + flagged good weeks. */
export const getSpotSeason = (id: string, sport?: string) =>
  request<SpotSeason>(`/spots/${id}/season${qs({ stage: 2, sport })}`);

export const getRegionSeason = (id: string, sport?: string) =>
  request<RegionSeasonResponse>(`/regions/${id}/season${qs({ sport })}`);

// --- search ----------------------------------------------------------------

export interface SearchSpot {
  id: string;
  slug: string;
  name: string;
  location: GeoPoint;
  sports: string[];
  score?: number | null;
  distance_m?: number | null;
}

export interface SearchRegionHit {
  id: string;
  slug: string;
  name: string;
  center: GeoPoint | null;
}

export interface SearchResult {
  resolved: string; // entities | point | area | none
  regionen: SearchRegionHit[];
  spots: SearchSpot[];
  treffer: number;
  geocode?: { type: string; name: string } | null;
}

export interface SearchQuery {
  q: string;
  sport?: string;
  week?: number;
  level?: string;
}

export const getSearch = (params: SearchQuery) =>
  request<SearchResult>(`/search${qs(params as unknown as Record<string, unknown>)}`);

// Open axes (Sprint 6 backend). Shapes are permissive — the UI only needs a few
// fields and tolerates the rest.
export interface BestRegionsResponse {
  regions?: Array<{ id?: string; slug?: string; name?: string; coverage?: number; intensity?: number }>;
  window?: unknown;
  [k: string]: unknown;
}
export interface BestWeeksResponse {
  weeks?: Array<{ week: number; score?: number; spots_working?: number }>;
  [k: string]: unknown;
}

export const getBestRegions = (params: { sport?: string; month?: number; weeks?: string; limit?: number } = {}) =>
  request<BestRegionsResponse>(`/search/best-regions${qs(params as Record<string, unknown>)}`);

export const getBestWeeks = (params: { region_id?: string; spot_id?: string; sport?: string; top?: number }) =>
  request<BestWeeksResponse>(`/areas/best-weeks${qs(params as Record<string, unknown>)}`);

// --- auth (Sprint A) --------------------------------------------------------

export type AdminRole = "admin" | "curator";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: AdminRole;
}

export const login = (email: string, password: string) =>
  request<AuthUser>(`/auth/login`, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const logout = () => request<void>(`/auth/logout`, { method: "POST" });

export const getMe = () => request<AuthUser>(`/auth/me`);

// --- admin user management (admin role only) -------------------------------

export interface AdminUserRecord {
  id: string;
  email: string;
  display_name: string;
  role: AdminRole;
  is_active: boolean;
  last_login_at: string | null;
  last_seen_at: string | null;
  created_at: string;
}

export const getAdminUsers = () => request<AdminUserRecord[]>(`/admin/users`);

export const createAdminUser = (body: {
  email: string;
  password: string;
  display_name?: string;
  role?: AdminRole;
}) =>
  request<AdminUserRecord>(`/admin/users`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateAdminUser = (
  id: string,
  body: { role?: AdminRole; is_active?: boolean; display_name?: string; email?: string }
) =>
  request<AdminUserRecord>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const setAdminUserPassword = (id: string, password: string) =>
  request<void>(`/admin/users/${id}/password`, {
    method: "POST",
    body: JSON.stringify({ password }),
  });

export const deleteAdminUser = (id: string) =>
  request<void>(`/admin/users/${id}`, { method: "DELETE" });

// --- community / UGC (Sprint C/D, public) ----------------------------------

export interface RatingItem {
  id: string;
  stars: number;
  skill_level: string;
  sport: string;
  conditions: string;
  author_name: string;
  created_at: string;
}
export interface RatingAggregate {
  count: number;
  avg: number | null;
  score: number;
}
export const getRatings = (spotId: string) =>
  request<{ items: RatingItem[]; aggregate: RatingAggregate }>(
    `/spots/${spotId}/ratings`
  );
export const postRating = (
  spotId: string,
  body: {
    stars: number;
    skill_level: string;
    sport: string;
    conditions: string;
    author_name?: string;
    author_email?: string;
    website?: string;
  }
) =>
  request<RatingItem>(`/spots/${spotId}/ratings`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export interface TipItem {
  id: string;
  body: string;
  author_name: string;
  created_at: string;
  /** Set when this tip is a reply to another (single-level threads). */
  parent_id: string | null;
}
export const getTips = (spotId: string) =>
  request<{ items: TipItem[] }>(`/spots/${spotId}/tips`);
export const postTip = (
  spotId: string,
  body: {
    body: string;
    author_name?: string;
    author_email?: string;
    parent_id?: string;
    website?: string;
  }
) =>
  request<TipItem>(`/spots/${spotId}/tips`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export interface CommunityImage {
  id: string;
  url: string;
  kind: string;
  width: number | null;
  height: number | null;
  credit: string | null;
  created_at: string;
  source: string;
  license_name: string | null;
  license_url: string | null;
  source_url: string | null;
}
export const getSpotImages = (spotId: string) =>
  request<{ items: CommunityImage[] }>(`/spots/${spotId}/images`);

/** Admin: geosearch Wikimedia Commons around the spot and store newly-licensed
 *  hits as gallery images. Safe to call again — already-stored photos are
 *  skipped, so it only ever adds what's new since the last fetch. */
export const fetchCommonsImages = (spotId: string) =>
  request<{ items: CommunityImage[] }>(`/admin/spots/${spotId}/commons-images/fetch`, {
    method: "POST",
  });

export function uploadSpotImage(
  spotId: string,
  file: File,
  kind: "gallery" | "hero_candidate",
  opts: { credit?: string; licenseAccept: boolean; review?: boolean } = { licenseAccept: false }
): Promise<CommunityImage> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("kind", kind);
  fd.append("license_accept", String(opts.licenseAccept));
  if (opts.credit) fd.append("credit", opts.credit);
  // Standalone gallery uploads (decoupled from the composer) go to the admin
  // review queue instead of appearing immediately — hero candidates are
  // already always pending, so this only changes anything for "gallery".
  if (opts.review) fd.append("review", "true");
  return request<CommunityImage>(`/spots/${spotId}/images`, {
    method: "POST",
    body: fd,
    timeoutMs: 120_000,
  });
}

export const reportImage = (
  imageId: string,
  body: { reason: string; note?: string; reporter_email?: string; website?: string }
) =>
  request<{ image_id: string; report_count: number; takedown_contact: string | null }>(
    `/images/${imageId}/report`,
    { method: "POST", body: JSON.stringify(body) }
  );

export const getImageLicense = () =>
  request<{ version: string; terms: string }>(`/community/license`);

export const postSubmission = (body: {
  payload: Record<string, unknown>;
  submitter_name?: string;
  submitter_email?: string;
  website?: string;
}) =>
  request<{ id: string; status: string }>(`/submissions`, {
    method: "POST",
    body: JSON.stringify(body),
  });

// --- admin moderation (Sprint D) -------------------------------------------

export interface ReviewCounts {
  submissions_pending: number;
  hero_candidates_pending: number;
  gallery_images_pending: number;
  reported_images: number;
  flagged_tips: number;
  flagged_ratings: number;
}
export interface ReviewSubmission {
  id: string;
  name: string | null;
  submitter_name: string;
  status: string;
  created_at: string;
  payload: Record<string, unknown>;
}
export interface ReviewImage {
  id: string;
  spot_id: string;
  url: string;
  kind: string;
  credit: string | null;
  status: string;
  report_count: number;
  created_at: string;
}
export interface ReviewTip {
  id: string;
  spot_id: string;
  body: string;
  author_name: string;
  status: string;
  flagged: boolean;
  /** Set when this comment is a reply (points at the top-level comment). */
  parent_id: string | null;
  created_at: string;
}
export interface ReviewRating {
  id: string;
  spot_id: string;
  stars: number;
  conditions: string;
  author_name: string;
  status: string;
  flagged: boolean;
  created_at: string;
}
export interface ReviewQueue {
  counts: ReviewCounts;
  submissions: ReviewSubmission[];
  hero_candidates: ReviewImage[];
  pending_gallery_images: ReviewImage[];
  reported_images: ReviewImage[];
  tips: ReviewTip[];
  ratings: ReviewRating[];
}

export const getReviewQueue = () => request<ReviewQueue>(`/admin/review/queue`);

/** Fields an admin supplies to complete a name-only proposal at approval time.
 *  Omit for a submission that already carries a full payload. */
export interface SubmissionCompletion {
  region_id?: string;
  lat?: number;
  lon?: number;
  sports?: string[];
  allow_duplicate?: boolean;
}
export const approveSubmission = (id: string, completion: SubmissionCompletion = {}) =>
  request<{ spot_id: string; status: string }>(
    `/admin/submissions/${id}/approve`,
    { method: "POST", body: JSON.stringify(completion) }
  );
export const rejectSubmission = (id: string, note?: string) =>
  request<{ status: string }>(`/admin/submissions/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
export const approveImage = (id: string) =>
  request<{ id: string; status: string }>(`/admin/images/${id}/approve`, {
    method: "POST",
  });
export const rejectImage = (id: string, note?: string) =>
  request<{ id: string; status: string }>(`/admin/images/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
export const removeImage = (id: string, note?: string) =>
  request<{ id: string; status: string }>(`/admin/images/${id}/remove`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
export const dismissReports = (id: string) =>
  request<{ id: string; report_count: number }>(
    `/admin/images/${id}/dismiss-reports`,
    { method: "POST" }
  );
/** All comments on a spot (published + hidden), for per-spot moderation. */
export const getSpotTips = (spotId: string) =>
  request<{ items: ReviewTip[] }>(`/admin/spots/${spotId}/tips`);
export const hideTip = (id: string) =>
  request<{ id: string; status: string }>(`/admin/tips/${id}/hide`, { method: "POST" });
export const restoreTip = (id: string) =>
  request<{ id: string; status: string }>(`/admin/tips/${id}/restore`, {
    method: "POST",
  });
export const hideRating = (id: string) =>
  request<{ id: string; status: string }>(`/admin/ratings/${id}/hide`, {
    method: "POST",
  });
export const restoreRating = (id: string) =>
  request<{ id: string; status: string }>(`/admin/ratings/${id}/restore`, {
    method: "POST",
  });

// --- admin dashboard (Sprint B) --------------------------------------------

export interface StatusCounts {
  draft: number;
  published: number;
  archived: number;
  total: number;
}

export interface NotLiveSpot {
  id: string;
  name: string;
  slug: string;
  status: string;
  region_id: string;
  gaps: string[];
}

export interface DraftSpot {
  id: string;
  name: string;
  slug: string;
  status: string;
  region_id: string;
  gaps: string[];
  ready: boolean;
  updated_at: string;
}

export type Rank = "red" | "yellow" | "green";

/** A spot in the "Fertigstellen" list with its traffic-light rank. */
export interface RankedSpot {
  id: string;
  name: string;
  slug: string;
  status: string;
  region_id: string | null;
  gaps: string[];
  ready: boolean;
  rank: Rank; // effective (override if set, else auto)
  rank_auto: Rank;
  finish_rank: Rank | null; // manual override, null = auto
}

/** Set (rank) or clear (null) a spot's manual Fertigstellen rank. */
export const setFinishRank = (id: string, rank: Rank | null) =>
  request<SpotRead>(`/admin/spots/${id}/finish-rank`, {
    method: "PATCH",
    body: JSON.stringify({ rank }),
  });

export interface LastChange {
  action: string;
  fields: string[];
  at: string | null;
}
export interface RecentSpot {
  id: string;
  name: string;
  slug: string;
  status: string;
  region_id: string;
  confidence: number | null;
  updated_at: string;
  last_change: LastChange | null;
}

export type TeamNotePriority = "normal" | "important";

export interface TeamNote {
  id: string;
  author: string | null;
  body: string;
  priority: TeamNotePriority;
  created_at: string;
}

export interface NoRegionSpot {
  id: string;
  name: string;
  slug: string;
  status: string;
}
export interface AdminOverview {
  spots: StatusCounts;
  regions: number;
  readiness_open: number;
  not_live: NotLiveSpot[];
  finish: RankedSpot[];
  finish_open: number;
  no_region: NoRegionSpot[];
  drafts: DraftSpot[];
  recent: RecentSpot[];
  review: Record<string, number>;
  team_notes: TeamNote[];
  era5_queued: number;
  climatology_missing: number;
  climatology_stale: number;
  climatology_current: number;
  climatology_failed: number;
}

export const getAdminOverview = () => request<AdminOverview>(`/admin/overview`);

/** Lightweight spot for the admin map: coordinates + status only. */
export interface AdminMapSpot {
  id: string;
  name: string;
  status: string;
  lat: number;
  lon: number;
}
export const getAdminMapSpots = (bounds?: [number, number, number, number]) => {
  const query = bounds
    ? `?west=${bounds[0]}&south=${bounds[1]}&east=${bounds[2]}&north=${bounds[3]}`
    : "";
  return request<AdminMapSpot[]>(`/admin/map-spots${query}`);
};

// --- team notes + activity (admin) -----------------------------------------

export const getTeamNotes = () => request<TeamNote[]>(`/admin/team-notes`);
export const createTeamNote = (body: string, priority: TeamNotePriority = "normal") =>
  request<TeamNote>(`/admin/team-notes`, {
    method: "POST",
    body: JSON.stringify({ body, priority }),
  });
export const updateTeamNote = (
  id: string,
  patch: { body?: string; priority?: TeamNotePriority }
) =>
  request<TeamNote>(`/admin/team-notes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
export const deleteTeamNote = (id: string) =>
  request<void>(`/admin/team-notes/${id}`, { method: "DELETE" });

export interface ActivityItem {
  actor: string | null;
  actor_email?: string | null;
  action: string;
  label: string;
  target: string | null;
  target_id: string | null;
  kind: string;
  fields: string[];
  at: string | null;
  /** How many audited actions this slot aggregates (spots are grouped). */
  actions?: number;
}
export const getActivity = (q?: string) =>
  request<ActivityItem[]>(`/admin/activity${qs({ q })}`);

// --- board tasks (kanban overview) -----------------------------------------

export interface BoardTask {
  id: string;
  title: string;
  body: string | null;
  status: "open" | "done";
  author: string | null;
  created_at: string;
}
export const getBoardTasks = () => request<BoardTask[]>(`/admin/board/tasks`);
export const createBoardTask = (title: string, body?: string) =>
  request<BoardTask>(`/admin/board/tasks`, {
    method: "POST",
    body: JSON.stringify({ title, body }),
  });
export const updateBoardTask = (
  id: string,
  patch: { status?: "open" | "done"; title?: string; body?: string }
) =>
  request<BoardTask>(`/admin/board/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
export const deleteBoardTask = (id: string) =>
  request<void>(`/admin/board/tasks/${id}`, { method: "DELETE" });

// --- operator notifications (badge) ----------------------------------------

export interface AdminNotification {
  id: string;
  type: string;
  message: string;
  spot_id: string | null;
  read: boolean;
  created_at: string;
}
export const getNotifications = () =>
  request<{ items: AdminNotification[]; unread: number }>(`/admin/notifications`);
export const getUnreadNotificationCount = () =>
  request<{ count: number }>(`/admin/notifications/unread-count`);
export const markNotificationRead = (id: string) =>
  request<AdminNotification>(`/admin/notifications/${id}/read`, { method: "POST" });
export const markAllNotificationsRead = () =>
  request<{ marked: number }>(`/admin/notifications/read-all`, { method: "POST" });

export interface AdminSpotsQuery {
  status?: string;
  region_id?: string;
  sport?: string;
  q?: string;
  sort?: string;
  limit?: number;
  offset?: number;
  /** Hide spots with this status (e.g. "archived" for the non-archived tabs). */
  exclude_status?: string;
  completeness?: "complete" | "incomplete";
  media?: MediaFilterKey;
}

export interface AdminSpotSummary extends SpotSummary {
  readiness: { ready: boolean; missing_count: number; gaps: string[] };
  media_flags: MediaFlags;
}

export interface AdminSpotsResponse {
  items: AdminSpotSummary[];
  total: number;
  limit: number;
  offset: number;
}

export const getAdminSpots = (params: AdminSpotsQuery = {}) =>
  request<AdminSpotsResponse>(
    `/admin/spots${qs(params as Record<string, unknown>)}`
  );

export const getAdminSpot = (id: string) =>
  request<SpotRead>(`/admin/spots/${id}/record`);

export const getTideProfile = (id: string) =>
  request<TideProfile>(`/admin/spots/${id}/tide`);

export const updateTideProfile = (
  id: string,
  body: Partial<Pick<TideProfile,
    | "enabled" | "public_enabled" | "timezone"
    | "global_offset_minutes" | "high_offset_minutes" | "low_offset_minutes"
    | "manual_uncertainty_minutes" | "note" | "correction_reason"
    | "correction_source"
  >> & { review_anchor?: boolean },
) => request<TideProfile>(`/admin/spots/${id}/tide`, {
  method: "PATCH", body: JSON.stringify(body),
});

export const autoSelectTideAnchor = (id: string) =>
  request<{ run_id: string; status: string }>(`/admin/spots/${id}/tide/anchor/auto`, { method: "POST" });

export const setManualTideAnchor = (id: string, body: { lat: number; lon: number; reason: string }) =>
  request<TideProfile>(`/admin/spots/${id}/tide/anchor`, { method: "PUT", body: JSON.stringify(body) });

export const previewTides = (id: string, body: { global_offset_minutes: number; high_offset_minutes: number; low_offset_minutes: number }) =>
  request<{ events: TideEvent[] }>(`/admin/spots/${id}/tide/preview`, { method: "POST", body: JSON.stringify(body) });

export const recalculateTides = (id: string) =>
  request<{ run_id: string; status: string }>(`/admin/spots/${id}/tide/recalculate`, { method: "POST" });

export const createTideOverride = (id: string, body: {
  event_id: string; manual_time: string;
  scope: TideOverride["scope"]; reason: string; source?: string;
}) => request<{ id: string; difference_minutes: number; scope: string }>(
  `/admin/spots/${id}/tide/overrides`, { method: "POST", body: JSON.stringify(body) },
);

export const revokeTideOverride = (spotId: string, overrideId: string) =>
  request<void>(`/admin/spots/${spotId}/tide/overrides/${overrideId}`, { method: "DELETE" });

export interface TideSuggestionPart {
  offset_minutes: number;
  spread_minutes: number;
  uncertainty_minutes: number;
  count: number;
}
export interface TideSuggestion {
  total: number;
  high: TideSuggestionPart | null;
  low: TideSuggestionPart | null;
  from: string | null;
  until: string | null;
}
export const getTideSuggestion = (id: string) =>
  request<TideSuggestion>(`/admin/spots/${id}/tide/suggestion`);
export const applyTideSuggestion = (id: string, body: { apply_high: boolean; apply_low: boolean; reason: string }) =>
  request<TideProfile>(`/admin/spots/${id}/tide/suggestion/apply`, { method: "POST", body: JSON.stringify(body) });

export interface TideProfileRevision {
  version: number;
  reason: string;
  actor: string | null;
  created_at: string;
  snapshot: Record<string, unknown>;
}
export const getTideHistory = (id: string) =>
  request<TideProfileRevision[]>(`/admin/spots/${id}/tide/history`);
export const rollbackTideProfile = (id: string, version: number, reason: string) =>
  request<TideProfile>(`/admin/spots/${id}/tide/rollback`, { method: "POST", body: JSON.stringify({ version, reason }) });

export interface AdminRegionEntry {
  region: Region;
  spot_counts: StatusCounts;
}

export const getAdminRegions = (q?: string) =>
  request<AdminRegionEntry[]>(`/admin/regions${qs({ q })}`);

export const getAdminRegion = (id: string) =>
  request<Region>(`/admin/regions/${id}/record`);

export interface GeocodeHit {
  name: string;
  lat: number;
  lon: number;
  country: string | null;
  feature_code: string | null;
}
export const geocodeAdmin = (q: string) =>
  request<GeocodeHit[]>(`/admin/geocode${qs({ q })}`);

export interface RegionCreateBody {
  name: string;
  slug?: string;
  country?: string | null;
  // Optional — when omitted the backend geocodes the name to a centre + bounds.
  lat?: number;
  lon?: number;
  defaults?: Record<string, unknown> | null;
  allow_duplicate?: boolean;
}

export const createRegion = (body: RegionCreateBody) =>
  request<Region>(`/admin/regions`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateRegionDefaults = (
  id: string,
  defaults: Record<string, unknown>
) =>
  request<Region>(`/admin/regions/${id}/defaults`, {
    method: "PATCH",
    body: JSON.stringify({ defaults }),
  });

export const updateRegion = (
  id: string,
  body: {
    name?: string;
    country?: string | null;
    description?: string | null;
    defaults?: Record<string, unknown>;
    season?: Record<string, unknown> | null;
    /** Optimistic-locking token; omit to force an overwrite after a 409. */
    expected_updated_at?: string;
    allow_duplicate?: boolean;
  }
) =>
  request<Region>(`/admin/regions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

/** Delete a region (only when no spots are assigned — 409 otherwise). */
export const deleteRegion = (id: string) =>
  request<void>(`/admin/regions/${id}`, { method: "DELETE" });

export const setRegionImageManual = (
  id: string,
  body: { url: string; credit: string; source?: string; license?: string }
) =>
  request<Region>(`/admin/regions/${id}/image`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export function uploadRegionImage(id: string, file: File, credit: string): Promise<Region> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("credit", credit);
  return request<Region>(`/admin/regions/${id}/image/upload`, {
    method: "POST",
    body: fd,
    timeoutMs: 120_000,
  });
}

/** Move a spot into a region (reassign). */
export const assignSpotRegion = (
  spotId: string,
  regionId: string,
  allowDuplicate = false
) =>
  request<SpotRead>(`/admin/spots/${spotId}/assign-region`, {
    method: "POST",
    body: JSON.stringify({ region_id: regionId, allow_duplicate: allowDuplicate }),
  });

/** Move several spots into a region at once (both directions). */
export const bulkAssignSpotRegion = (
  spotIds: string[],
  regionId: string,
  allowDuplicate = false
) =>
  request<{ moved: number }>(`/admin/spots/bulk-assign-region`, {
    method: "POST",
    body: JSON.stringify({
      spot_ids: spotIds,
      region_id: regionId,
      allow_duplicate: allowDuplicate,
    }),
  });

/** Make spots region-less (drag out of a region without a target). */
export const bulkUnassignSpotRegion = (spotIds: string[], allowDuplicate = false) =>
  request<{ changed: number }>(`/admin/spots/bulk-unassign-region`, {
    method: "POST",
    body: JSON.stringify({ spot_ids: spotIds, allow_duplicate: allowDuplicate }),
  });

// --- admin spot actions (go-live / ERA5) -----------------------------------

export interface Era5Status {
  spot_id?: string;
  status?: string;
  freshness_status?: string;
  stale_reasons?: string[];
  generated_at?: string | null;
  window?: string | null;
  attempt_count?: number;
  reason?: string | null;
  error?: string | null;
  [k: string]: unknown;
}

export const goLiveSpot = (id: string) =>
  request<Record<string, unknown>>(`/admin/spots/${id}/live`, {
    method: "POST",
    timeoutMs: 55_000,
  });

export const unpublishSpot = (id: string) =>
  request<{ spot_id: string; status: string }>(`/admin/spots/${id}/unpublish`, {
    method: "POST",
  });

export const archiveSpot = (id: string) =>
  request<{ spot_id: string; status: string }>(`/admin/spots/${id}/archive`, {
    method: "POST",
  });

export const reactivateSpot = (id: string) =>
  request<{ spot_id: string; status: string }>(`/admin/spots/${id}/reactivate`, {
    method: "POST",
  });

export const deleteSpot = (id: string) =>
  request<void>(`/admin/spots/${id}`, { method: "DELETE" });

export const triggerEra5 = (id: string) =>
  request<Era5Status>(`/admin/spots/${id}/era5`, { method: "POST", timeoutMs: 55_000 });

export const getEra5Status = (id: string) =>
  request<Era5Status>(`/admin/spots/${id}/era5`);

// --- admin endpoints -------------------------------------------------------

export interface SpotCreateBody {
  name: string;
  region_id: string;
  lat: number;
  lon: number;
  sports?: string[];
  slug?: string;
  water_type?: string[];
  bottom_type?: string[];
  level?: string[];
  water_character?: string[];
  style?: string[];
  facilities?: FacilityMap | null;
  facing?: number | null;
  editorial?: Record<string, any> | null;
  allow_duplicate?: boolean;
}

export type SpotUpdateBody = Partial<SpotCreateBody> & {
  /** Weather model preference (edit-only; inherited from the region on create). */
  model_pref?: string | null;
  /** Optimistic-locking token: the `updated_at` the form loaded. Omit to force
   *  an overwrite after a 409 conflict. */
  expected_updated_at?: string;
};

export const createSpot = (body: SpotCreateBody) =>
  request<SpotRead>(`/admin/spots`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateSpot = (id: string, body: SpotUpdateBody) =>
  request<SpotRead>(`/admin/spots/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const getReadiness = (id: string) =>
  request<Readiness>(`/admin/spots/${id}/readiness`);

export const setSpotImageFocal = (id: string, x: number, y: number) =>
  request<SpotRead>(`/admin/spots/${id}/image/focal`, {
    method: "POST",
    body: JSON.stringify({ x, y }),
  });

/** Mobile focal — pass null to clear the mobile override (falls back to focal). */
export const setSpotImageFocalMobile = (
  id: string,
  point: { x: number; y: number } | null,
) =>
  request<SpotRead>(`/admin/spots/${id}/image/focal/mobile`, {
    method: "POST",
    body: JSON.stringify(point ?? { x: null, y: null }),
  });

/** Edit the current hero's rights fields in place (url + focal preserved). */
export const setHeroAttribution = (
  id: string,
  body: { credit: string; license: string; source: string }
) =>
  request<SpotRead>(`/admin/spots/${id}/image/attribution`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const setRegionImageFocal = (id: string, x: number, y: number) =>
  request<Region>(`/admin/regions/${id}/image/focal`, {
    method: "POST",
    body: JSON.stringify({ x, y }),
  });

export const setRegionImageFocalMobile = (
  id: string,
  point: { x: number; y: number } | null,
) =>
  request<Region>(`/admin/regions/${id}/image/focal/mobile`, {
    method: "POST",
    body: JSON.stringify(point ?? { x: null, y: null }),
  });

export async function uploadHeroImage(
  id: string,
  file: File,
  credit: string
): Promise<SpotRead> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("credit", credit);
  return request<SpotRead>(`/admin/spots/${id}/image/upload`, {
    method: "POST",
    body: fd,
    timeoutMs: 120_000,
  });
}

// --- admin media picker ----------------------------------------------------
// Provider credentials live on the server; the browser only ever talks to our
// own proxy. The deployment's CSP allows connect-src 'self' plus MapTiler, so a
// direct provider call from here would be blocked regardless.


export interface MediaSearchResponse {
  provider: ProviderKey;
  status: TabStatus;
  items: MediaItem[];
  total: number;
  page: number;
  meta: {
    cached: boolean;
    budget: {
      used: number;
      limit: number;
      exhausted: boolean;
      warning: boolean;
    } | null;
    message: string | null;
  };
}

export interface MediaSearchQuery {
  provider: ProviderKey;
  q?: string;
  role?: MediaRole;
  page?: number;
  lat?: number | null;
  lon?: number | null;
  radius_km?: number;
}

export const searchMedia = (query: MediaSearchQuery, signal?: AbortSignal) =>
  request<MediaSearchResponse>(`/admin/media/search${qs({ ...query })}`, { signal });

export interface MediaContext {
  entity_type: MediaEntityType;
  entity_id: string;
  title: string;
  subtitle: string;
  lat: number | null;
  lon: number | null;
  suggestions: string[];
  has_image: boolean;
}

export const getMediaContext = (entityType: MediaEntityType, entityId: string) =>
  request<MediaContext>(`/admin/media/context/${entityType}/${entityId}`);

export interface MediaProviderStatus {
  provider: ProviderKey;
  available: boolean;
  budget: { used: number; limit: number; exhausted: boolean; warning: boolean };
}

export const getMediaProviders = () =>
  request<{ providers: MediaProviderStatus[] }>(`/admin/media/providers`);

export interface AdoptMediaBody {
  entity_type: MediaEntityType;
  entity_id: string;
  role: MediaRole;
  provider: string;
  external_id: string;
  focal?: { x: number; y: number };
}

export interface AdoptMediaResponse {
  entity_type: MediaEntityType;
  entity_id: string;
  role: MediaRole;
  image: ImageRecord | null;
  gallery_image_id: string | null;
  demoted_hero: boolean;
  warnings: string[];
}

export const adoptMedia = (body: AdoptMediaBody) =>
  request<AdoptMediaResponse>(`/admin/media/adopt`, {
    method: "POST",
    body: JSON.stringify(body),
    // Hosted providers are downloaded and re-encoded server-side on adopt.
    timeoutMs: 120_000,
  });

export const verifyMediaSources = (limit = 100) =>
  request<{
    checked: number;
    checked_at: string;
    dead: {
      entity_type: MediaEntityType;
      entity_id: string;
      name: string;
      url: string;
      status: number | null;
    }[];
  }>(`/admin/media/verify-sources${qs({ limit })}`, { method: "POST" });

export interface GalleryImage {
  id: string;
  url: string;
  kind: "gallery" | "hero_candidate";
  status: string;
  position: number | null;
  width: number | null;
  height: number | null;
  source: string | null;
  provider: string | null;
  external_id: string | null;
  delivery: "hotlinked" | "hosted" | null;
  credit: string | null;
  credit_url: string | null;
  license_name: string | null;
  license_url: string | null;
  source_url: string | null;
  geo_verified: boolean;
  created_at: string;
}

export const getGallery = (entityType: MediaEntityType, entityId: string) =>
  request<{ items: GalleryImage[] }>(`/admin/media/gallery/${entityType}/${entityId}`);

export const reorderGallery = (
  entityType: MediaEntityType,
  entityId: string,
  imageIds: string[]
) =>
  request<{ items: GalleryImage[] }>(`/admin/media/gallery/order`, {
    method: "PATCH",
    body: JSON.stringify({ entity_type: entityType, entity_id: entityId, image_ids: imageIds }),
  });

export const removeGalleryImage = (imageId: string) =>
  request<void>(`/admin/media/gallery/${imageId}`, { method: "DELETE" });

export const promoteGalleryImage = (imageId: string) =>
  request<{ entity_type: MediaEntityType; entity_id: string; image: ImageRecord }>(
    `/admin/media/gallery/${imageId}/promote`,
    { method: "POST" }
  );

export type MediaFilterKey = "no_hero" | "unverified" | "duplicate" | "dead";

export interface MediaFlags {
  no_hero: boolean;
  unverified: boolean;
  duplicate: boolean;
  dead: boolean;
}

export interface RegionWorklistEntry {
  id: string;
  name: string;
  country: string | null;
  flags: MediaFlags;
}

export const getMediaWorklist = (media?: MediaFilterKey) =>
  request<{ summary: Record<MediaFilterKey, number>; regions: RegionWorklistEntry[] }>(
    `/admin/media/worklist${qs({ media })}`
  );
