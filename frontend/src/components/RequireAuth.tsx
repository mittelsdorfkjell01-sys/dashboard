// Route guard: redirects to /admin/login when signed out, and shows a calm
// "no permission" note when a role is required the user doesn't have.

import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../lib/auth";
import type { AdminRole } from "../lib/api";

export default function RequireAuth({
  role,
  children,
}: {
  role?: AdminRole;
  children: ReactNode;
}) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="grid min-h-[50vh] place-items-center text-[14px] text-muted">
        Lädt…
      </div>
    );
  }

  if (!user) {
    return (
      <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
    );
  }

  if (role && user.role !== role) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <p className="text-[15px] font-medium text-ink">Keine Berechtigung</p>
        <p className="mt-2 text-[13px] text-muted">
          Dieser Bereich ist Administrator:innen vorbehalten.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
