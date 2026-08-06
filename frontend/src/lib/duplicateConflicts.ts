import { ApiError } from "./api";

export interface DuplicateCandidate {
  id: string;
  name: string;
  region_id?: string | null;
  region_name?: string | null;
  country?: string | null;
  distance_m?: number | null;
  similarity?: number | null;
  bounds_overlap?: boolean;
}

export interface DuplicateConflict {
  code: "exact_duplicate" | "likely_duplicate";
  entity: "spot" | "region";
  message: string;
  candidates: DuplicateCandidate[];
  override_allowed: boolean;
}

export function parseDuplicateConflict(error: unknown): DuplicateConflict | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const outer = error.detail;
  if (!outer || typeof outer !== "object" || !("detail" in outer)) return null;
  const detail = (outer as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const value = detail as Partial<DuplicateConflict>;
  if (value.code !== "exact_duplicate" && value.code !== "likely_duplicate") {
    return null;
  }
  if (value.entity !== "spot" && value.entity !== "region") return null;
  return {
    code: value.code,
    entity: value.entity,
    message: typeof value.message === "string" ? value.message : "Mögliche Dublette gefunden.",
    candidates: Array.isArray(value.candidates) ? value.candidates : [],
    override_allowed: value.override_allowed === true,
  };
}
