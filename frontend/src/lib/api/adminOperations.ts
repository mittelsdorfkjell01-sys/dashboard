import { request } from "./client";

export interface AdminEnvironment {
  app_env: "development" | "test" | "production";
  database_target: "local" | "remote" | "unknown";
  admin_writes_blocked: boolean;
  allow_remote_writes: boolean;
}

export const getEnvironment = () =>
  request<AdminEnvironment>("/admin/environment");

export interface OpsJob {
  job_id: string;
  spot_id: string | null;
  spot_name: string | null;
  status: string;
  error: string | null;
  error_category: "quota" | "coordinates" | "validation" | "provider" | "unknown" | null;
  reason: string | null;
  attempt_count: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_s: number | null;
}

export interface CacheNamespaceMetrics {
  requests: number;
  hits: number;
  misses: number;
  hit_rate: number | null;
  errors: number;
  writes: number;
  average_entry_bytes: number | null;
  lock_acquired: number;
  lock_contended: number;
  average_latency_ms: number | null;
  provider_fetches: number;
  provider_fetch_errors: number;
  provider_fetch_average_ms: number | null;
}

export interface AdminOperations {
  freshness: { missing: number; stale: number; current: number; failed: number };
  queue_depth: number;
  job_status: Record<string, number>;
  recent_jobs: OpsJob[];
  public_update: { climatology_cron: string; edge_cache: string };
  cache: {
    scope: "current_process_since_start";
    captured_at: string;
    namespaces: Record<string, CacheNamespaceMetrics>;
  };
}

export const getOperations = () =>
  request<AdminOperations>("/admin/operations");
