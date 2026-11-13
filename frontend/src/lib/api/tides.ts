import { request } from "./client";
import type { GeoPoint } from "./shared";

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

export interface PublicTideSeriesPoint {
  time: string;
  level_normalized: number;
  level_m: number | null;
  phase: "rising" | "high" | "falling" | "low";
}

export interface PublicTides {
  available: boolean;
  product_type: "astronomical_tide" | "modelled_sea_level";
  message: string | null;
  timezone: string | null;
  phase: "rising" | "high" | "falling" | "low" | "unavailable";
  cycle_position: number | null;
  quality: TideQuality;
  approximate: boolean;
  last_calculated_at: string | null;
  valid_until: string | null;
  forecast_start: string | null;
  forecast_end: string | null;
  horizon_days: number;
  partial: boolean;
  datum: "relative_low_high" | "mean_sea_level";
  current_level_m: number | null;
  navigational: boolean;
  model_name: string | null;
  model_version: string | null;
  source_name: string | null;
  source_url: string | null;
  attribution: string | null;
  events: PublicTideEvent[];
  series: PublicTideSeriesPoint[];
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

export type TideRolloutStatus =
  | "missing_profile"
  | "disabled"
  | "processing"
  | "failed"
  | "invalid"
  | "anchor_review"
  | "reviewed_private"
  | "public"
  | "needs_anchor";

export interface TideRolloutItem {
  spot_id: string;
  spot_name: string;
  region_name: string | null;
  country: string | null;
  status: TideRolloutStatus;
  enabled: boolean;
  public_enabled: boolean;
  anchor_status: TideProfile["anchor_status"] | null;
  anchor_distance_m: number | null;
  anchor_warnings: string[];
  calculation_status: TideProfile["calculation_status"];
  calculation_error: string | null;
  last_calculated_at: string | null;
  latest_run_status: string | null;
}

export interface TideRolloutQueue {
  items: TideRolloutItem[];
  summary: Partial<Record<TideRolloutStatus, number>>;
  total: number;
}

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

export interface TideProfileRevision {
  version: number;
  reason: string;
  actor: string | null;
  created_at: string;
  snapshot: Record<string, unknown>;
}

export const getSpotTides = (id: string, days = 10) =>
  request<PublicTides>(`/spots/${id}/tides?days=${Math.max(1, Math.min(10, days))}`);

export const getTideProfile = (id: string) =>
  request<TideProfile>(`/admin/spots/${id}/tide`);

export const getTideRolloutQueue = () =>
  request<TideRolloutQueue>("/admin/spots/tide/queue");

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

export const getTideSuggestion = (id: string) =>
  request<TideSuggestion>(`/admin/spots/${id}/tide/suggestion`);

export const applyTideSuggestion = (id: string, body: { apply_high: boolean; apply_low: boolean; reason: string }) =>
  request<TideProfile>(`/admin/spots/${id}/tide/suggestion/apply`, { method: "POST", body: JSON.stringify(body) });

export const getTideHistory = (id: string) =>
  request<TideProfileRevision[]>(`/admin/spots/${id}/tide/history`);

export const rollbackTideProfile = (id: string, version: number, reason: string) =>
  request<TideProfile>(`/admin/spots/${id}/tide/rollback`, { method: "POST", body: JSON.stringify({ version, reason }) });
