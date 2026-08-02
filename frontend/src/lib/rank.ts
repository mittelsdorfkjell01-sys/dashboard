// The "Fertigstellen" traffic-light rank, mirrored from app/admin/rank.py.
//   green  — nothing open
//   yellow — one or two points open (hero image present)
//   red    — hero image missing OR more than two points open
// Climatology is a soft gap (auto-started on go-live): it only ever keeps a spot
// yellow, never forces red. An operator override wins over the automatic value.

import type { Rank } from "./api";

// Gaps that count as "important" — their absence forces red on their own.
const IMPORTANT_GAPS = new Set(["image"]);
// Gaps that must never push a spot to red (kept yellow at worst).
const SOFT_GAPS = new Set(["climatology"]);

export const RANKS: Rank[] = ["green", "yellow", "red"];

export function autoRank(gaps: string[]): Rank {
  if (gaps.length === 0) return "green";
  const hard = gaps.filter((g) => !SOFT_GAPS.has(g));
  if (gaps.some((g) => IMPORTANT_GAPS.has(g)) || hard.length > 2) return "red";
  return "yellow";
}

export function effectiveRank(gaps: string[], override: Rank | null): Rank {
  return override ?? autoRank(gaps);
}

export const RANK_LABEL: Record<Rank, string> = {
  red: "Rot",
  yellow: "Gelb",
  green: "Grün",
};

// Solid dot colour for a rank. Uses the admin semantic tokens (theme-aware:
// legible in both light and dark) — rank.ts is an admin-only helper.
export const RANK_DOT: Record<Rank, string> = {
  red: "bg-admin-danger",
  yellow: "bg-admin-warning",
  green: "bg-admin-success",
};

// Tinted card styling (border + background) for a ranked row. Admin semantic
// token surfaces so the traffic-light tint adapts to light/dark.
export const RANK_CARD: Record<Rank, string> = {
  red: "border-admin-danger-border bg-admin-danger-bg",
  yellow: "border-admin-warning-bg bg-admin-warning-bg",
  green: "border-admin-success-border bg-admin-success-bg",
};
