import type { Location } from "react-router-dom";

export interface AdminReturnTarget {
  to: string;
  label: string;
}

export interface AdminNavigationState {
  adminReturn?: AdminReturnTarget;
  adminJustCreated?: {
    id: string;
  };
}

type LocationParts = Pick<Location, "pathname" | "search" | "hash">;

export function createAdminReturnState(
  location: LocationParts,
  label: string
): AdminNavigationState {
  return {
    adminReturn: {
      to: `${location.pathname}${location.search}${location.hash}`,
      label,
    },
  };
}

export function readAdminReturnTarget(state: unknown): AdminReturnTarget | null {
  if (!state || typeof state !== "object") return null;
  const candidate = (state as AdminNavigationState).adminReturn;
  if (!candidate || typeof candidate.to !== "string" || typeof candidate.label !== "string") {
    return null;
  }
  if (!/^\/admin(?:[/?#]|$)/.test(candidate.to)) return null;
  const label = candidate.label.trim();
  return label ? { to: candidate.to, label } : null;
}

export function adminSectionLabel(pathname: string): string {
  if (pathname === "/admin") return "Übersicht";
  if (pathname.startsWith("/admin/review")) return "Review";
  if (pathname.startsWith("/admin/map")) return "Karte";
  if (pathname.startsWith("/admin/activity")) return "Aktivität";
  if (pathname.startsWith("/admin/regions")) return "Regionen";
  if (pathname.startsWith("/admin/users")) return "Benutzer";
  if (pathname.startsWith("/admin/spots")) return "Spots";
  if (pathname.includes("/region/")) return "Region";
  if (pathname.includes("/spot/")) return "Spot";
  return "Dashboard";
}
