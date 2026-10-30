import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import { isVisited, markVisited, unmarkVisited, VISITS_EVENT } from "../lib/account";
import { AccountVisitedIcon } from "../lib/icons";

/**
 * "Spots besucht" — a compact round check-in that records a `session_checkin`
 * event for this spot (replaces the old inline "War heute hier" panel). Same
 * round icon chassis as the save/share buttons in the same row; the pin icon
 * matches the account menu's "Spots besucht" entry. Once tapped it settles into
 * an active (filled) state to confirm the visit.
 */
export default function VisitedButton({ spotId }: { spotId: string }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [visited, setVisited] = useState(() => isVisited(spotId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setVisited(isVisited(spotId));
    window.addEventListener(VISITS_EVENT, sync);
    return () => window.removeEventListener(VISITS_EVENT, sync);
  }, [spotId]);

  const onClick = async () => {
    if (!user) {
      const here = location.pathname + location.search + location.hash;
      navigate(`/anmelden?redirect=${encodeURIComponent(here)}`);
      return;
    }
    if (busy) return;
    setBusy(true); setError(null);
    try {
      if (visited) await unmarkVisited(spotId);
      else await markVisited(spotId);
    } catch { setError(t("visits.actionFailed")); }
    finally { setBusy(false); }
  };

  return (
    <span className="relative inline-flex">
    <button
      type="button"
      onClick={() => void onClick()}
      disabled={busy}
      aria-pressed={visited}
      aria-label={visited ? t("visits.remove") : t("visits.add")}
      title={visited ? t("visits.added") : t("visits.add")}
      className={`grid h-10 w-10 place-items-center rounded-full border transition-colors active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
        visited ? "border-ink bg-ink text-white" : "border-line text-ink hover:bg-band"
      }`}
    >
      <AccountVisitedIcon className="text-lead" />
    </button>
    {error && <span role="alert" className="absolute left-0 top-full z-10 mt-1 w-44 rounded-card bg-danger-bg p-2 text-caption text-danger">{error}</span>}
    </span>
  );
}
