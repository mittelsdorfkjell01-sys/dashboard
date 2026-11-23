import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDownIcon } from "../lib/icons";
import { requestAccountMenu } from "../lib/accountMenuReturn";

/**
 * The back control at the top of every page the site menu leads to — help,
 * contact, terms, imprint, privacy.
 *
 * These five are destinations a visitor steps *into* from the menu and then
 * wants to step out of again. Without a control of their own the only way back
 * is the browser gesture, which the sheet's own close button had just taught
 * them not to need.
 *
 * Where it goes depends on how the visitor arrived: from the account menu (its
 * site links mark the navigation) it returns into that open menu, so the step
 * back undoes the step in. From anywhere else — a footer link, a shared URL —
 * it is a plain step back in history, and a deep link with nothing behind it
 * falls back to the landing page rather than doing nothing.
 */
export function usePageBack(): () => void {
  const location = useLocation();
  const navigate = useNavigate();

  const fromMenu = Boolean((location.state as { fromMenu?: boolean } | null)?.fromMenu);
  return () => {
    if (fromMenu) requestAccountMenu();
    if (window.history.length > 1) navigate(-1);
    else navigate("/");
  };
}

/** The in-flow control; `ScrollBackButton` pins a copy once it scrolls away. */
export default function PageBackLink({ className = "" }: { className?: string }) {
  const { t } = useTranslation();
  const goBack = usePageBack();

  return (
    // The bare glyph, no label (2026-11-21): the same back control as the
    // maps and the floating one; the name is kept for screen readers.
    <button
      type="button"
      data-page-back
      onClick={goBack}
      aria-label={t("help.back")}
      className={`back-glyph -ml-3 ${className}`}
    >
      <ChevronDownIcon width={24} height={24} className="rotate-90" />
    </button>
  );
}
