import { type ReactNode } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../context/AuthContext";
import { CloseIcon } from "../../lib/icons";
import Footer from "../../components/Footer";

/**
 * Full-screen shell for the signed-in account area. Every sub-page is its own
 * full-bleed screen opened from the account menu, including Mein Setup; a single close affordance in
 * the top-right corner steps back to wherever the visitor came from (the menu,
 * a spot, the landing page). Redirects to /anmelden when signed out.
 *
 * The old brand bar + tab rail were dropped: the account areas are now reached
 * from the burger menu (see AccountMenu / Figma Frame 76/77), not a tab shell.
 */
export default function AccountLayout() {
  const { t } = useTranslation();
  const { user, ready, sessionError, refreshSession } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (!ready)
    return <main role="status" className="mx-auto max-w-lg px-4 py-20 text-center text-ui text-muted">{t("account.loading")}</main>;
  if (sessionError)
    return (
      <main className="mx-auto max-w-lg px-4 py-20 text-center">
        <h1 className="text-title font-semibold text-ink">{t("account.unavailableTitle")}</h1>
        <p role="alert" className="mt-3 text-ui text-muted">{sessionError}</p>
        <button type="button" onClick={() => void refreshSession()} className="mt-6 min-h-11 rounded-card bg-ink px-5 text-ui font-semibold text-surface">{t("common.retry")}</button>
      </main>
    );
  if (!user) {
    const redirect = encodeURIComponent(location.pathname + location.search + location.hash);
    return <Navigate to={`/anmelden?redirect=${redirect}`} replace />;
  }

  // "Zurück zum Menü": the menu is a transient overlay, so step back through
  // history; fall back to the landing page when the profile was opened directly.
  const goBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate("/");
  };

  return (
    <div className="relative min-h-screen bg-page">
      <button
        type="button"
        onClick={goBack}
        aria-label={t("common.back")}
        // The bare glyph like every back control (2026-11-21), no dark disc.
        className="back-glyph fixed right-2 top-[max(0.75rem,env(safe-area-inset-top))] z-50 sm:right-4"
      >
        <CloseIcon width={24} height={24} />
      </button>
      <Outlet />
      {/* The info and legal pages are linked from the footer only; the
          account area keeps it so the Impressum is one tap away here too. */}
      <Footer />
    </div>
  );
}

/**
 * Shared padded container + title for the plain account sub-pages (Saved,
 * Spots besucht, Spots hinzufügen, Mein Setup, Einstellungen). Profil brings its own
 * full-bleed hero instead of this header.
 */
export function AccountPage({
  title,
  intro,
  action,
  children,
}: {
  title: string;
  intro?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-content px-5 pb-[max(2.5rem,env(safe-area-inset-bottom))] pt-16">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-heading font-semibold text-ink">{title}</h1>
          {intro && <p className="mt-1 text-ui text-muted">{intro}</p>}
        </div>
        {action}
      </header>
      {children}
    </div>
  );
}
