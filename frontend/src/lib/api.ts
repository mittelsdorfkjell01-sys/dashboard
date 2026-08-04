// Thin, typed fetch wrapper around the Surfwinddate FastAPI backend.
// Base URL comes from VITE_API_URL (default http://localhost:8000). Every call
// returns typed data or throws an ApiError the UI can surface.

import { getAdminKey } from "./adminKey";

export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

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

export interface ImageRecord {
  url: string;
  source?: string;
  license?: string;
  credit?: string;
  /** Focal point as object-position percentages (0..100). */
  focal?: { x: number; y: number };
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
  bottom_type: string | null;
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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.body && !(init.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...((init?.headers as Record<string, string>) || {}),
  };
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
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...init,
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
  status?: string;
  sport?: string;
  level?: string;
  water_character?: string;
  style?: string[];
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

export const getSpotLive = (id: string) =>
  request<LiveConditionsRead>(`/spots/${id}/live`);

/** Batch live conditions for several spots in one round-trip (landing/map). */
export const getSpotsLive = (ids: string[]) =>
  request<LiveConditionsRead[]>(
    `/spots/live?ids=${encodeURIComponent(ids.join(","))}`
  );

/** Public region listing — published only. */
export const getRegions = () => request<Region[]>(`/regions`);

/** Flat admin region list (Region[], includes drafts) — for dropdowns/pickers. */
export const getAdminRegionsFlat = () => request<Region[]>(`/regions?status=all`);

export const getRegion = (id: string) => request<Region>(`/regions/${id}`);

/** Resolve a region by slug regardless of status (so draft preview works). */
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
export const getAdminMapSpots = () =>
  request<AdminMapSpot[]>(`/admin/map-spots`);

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
}

export interface AdminSpotsResponse {
  items: SpotSummary[];
  total: number;
  limit: number;
  offset: number;
}

export const getAdminSpots = (params: AdminSpotsQuery = {}) =>
  request<AdminSpotsResponse>(
    `/admin/spots${qs(params as Record<string, unknown>)}`
  );

export interface AdminRegionEntry {
  region: Region;
  spot_counts: StatusCounts;
}

export const getAdminRegions = () =>
  request<AdminRegionEntry[]>(`/admin/regions`);

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

export const setRegionStockImage = (id: string) =>
  request<Region>(`/admin/regions/${id}/stock-image`, { method: "POST" });

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
  });
}

/** Move a spot into a region (reassign). */
export const assignSpotRegion = (spotId: string, regionId: string) =>
  request<SpotRead>(`/admin/spots/${spotId}/assign-region`, {
    method: "POST",
    body: JSON.stringify({ region_id: regionId }),
  });

/** Move several spots into a region at once (both directions). */
export const bulkAssignSpotRegion = (spotIds: string[], regionId: string) =>
  request<{ moved: number }>(`/admin/spots/bulk-assign-region`, {
    method: "POST",
    body: JSON.stringify({ spot_ids: spotIds, region_id: regionId }),
  });

/** Make spots region-less (drag out of a region without a target). */
export const bulkUnassignSpotRegion = (spotIds: string[]) =>
  request<{ changed: number }>(`/admin/spots/bulk-unassign-region`, {
    method: "POST",
    body: JSON.stringify({ spot_ids: spotIds }),
  });

// --- admin spot actions (go-live / ERA5) -----------------------------------

export interface Era5Status {
  spot_id?: string;
  status?: string;
  [k: string]: unknown;
}

export const goLiveSpot = (id: string) =>
  request<Record<string, unknown>>(`/admin/spots/${id}/live`, { method: "POST" });

export const unpublishSpot = (id: string) =>
  request<{ spot_id: string; status: string }>(`/admin/spots/${id}/unpublish`, {
    method: "POST",
  });

export const archiveSpot = (id: string) =>
  request<{ spot_id: string; status: string }>(`/admin/spots/${id}/archive`, {
    method: "POST",
  });

export const triggerEra5 = (id: string) =>
  request<Era5Status>(`/admin/spots/${id}/era5`, { method: "POST" });

export const getEra5Status = (id: string) =>
  request<Era5Status>(`/admin/spots/${id}/era5`);

/** Kick off background processing of all queued ERA5 jobs. */
export const processEra5Queue = () =>
  request<{ queued: number; scheduled: boolean }>(`/admin/era5/process-queue`, {
    method: "POST",
  });

// --- admin endpoints -------------------------------------------------------

export interface SpotCreateBody {
  name: string;
  region_id: string;
  lat: number;
  lon: number;
  sports?: string[];
  slug?: string;
  water_type?: string[];
  bottom_type?: string | null;
  level?: string[];
  water_character?: string[];
  style?: string[];
  facilities?: FacilityMap | null;
  facing?: number | null;
  editorial?: Record<string, any> | null;
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
  });
}
