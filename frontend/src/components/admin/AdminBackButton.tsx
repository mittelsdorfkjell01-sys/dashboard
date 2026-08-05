import { useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { readAdminReturnTarget } from "../../lib/adminNavigation";

const DESTINATION_LABELS: Record<string, string> = {
  Übersicht: "zur Übersicht",
  Review: "zum Review",
  Karte: "zur Karte",
  Aktivität: "zur Aktivität",
  Regionen: "zu den Regionen",
  Region: "zur Region",
  Spots: "zu den Spots",
  Spot: "zum Spot",
  Benutzer: "zu den Benutzern",
  Dashboard: "zum Dashboard",
};

export function useAdminBackNavigation({
  fallbackTo,
  fallbackLabel,
}: {
  fallbackTo: string;
  fallbackLabel: string;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const target = readAdminReturnTarget(location.state);

  const goBack = useCallback(() => {
    if (target) navigate(-1);
    else navigate(fallbackTo, { replace: true });
  }, [fallbackTo, navigate, target]);

  return {
    goBack,
    label: target?.label ?? fallbackLabel,
    target: target?.to ?? fallbackTo,
  };
}

export default function AdminBackButton({
  onClick,
  label,
  text,
  showIcon = true,
  className = "",
}: {
  onClick: () => void;
  label: string;
  text?: string;
  showIcon?: boolean;
  className?: string;
}) {
  const destination = DESTINATION_LABELS[label] ?? `zu ${label}`;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 text-label text-admin-muted transition-colors hover:text-admin-fg ${className}`}
    >
      {showIcon && (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
          <path
            d="m15 18-6-6 6-6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {text ?? `Zurück ${destination}`}
    </button>
  );
}
