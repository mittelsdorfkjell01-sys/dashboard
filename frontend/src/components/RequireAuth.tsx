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
  const { user, loading, error, refresh } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="grid min-h-[50vh] place-items-center text-ui text-muted">
        Lädt…
      </div>
    );
  }

  if (error && !user) {
    return (
      <div role="alert" className="mx-auto grid min-h-[50vh] max-w-md place-items-center p-6 text-center">
        <div>
          <p className="text-body font-medium text-ink">Dashboard nicht erreichbar</p>
          <p className="mt-2 text-label text-muted">{error}</p>
          <button
            type="button"
            onClick={() => void refresh()}
            className="mt-4 min-h-11 px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            Erneut versuchen
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <Navigate
        to="/admin/login"
        replace
        state={{ from: `${location.pathname}${location.search}${location.hash}` }}
      />
    );
  }

  if (role && user.role !== role) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <p className="text-body font-medium text-ink">Keine Berechtigung</p>
        <p className="mt-2 text-label text-muted">
          Dieser Bereich ist Administrator:innen vorbehalten.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
