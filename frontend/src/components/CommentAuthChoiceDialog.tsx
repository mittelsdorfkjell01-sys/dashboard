import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CloseIcon, UserIcon } from "../lib/icons";

/**
 * Auth choice shown when someone submits a comment while signed out
 * (Figma Frame_12). Centered card over a lightly *blurred* (not darkened)
 * page; two options — post anonymously (published as "Anonym") or sign in to
 * comment under their name — plus a cancel link. Esc / click-out / abbrechen
 * all cancel.
 */
export default function CommentAuthChoiceDialog({
  open,
  onAnonymous,
  onSignIn,
  onCancel,
  title = "Wie möchtest du kommentieren?",
  anonymousText = "dein Kommentar wird ohne Namen veröffentlicht",
  signInText = "melde dich an, um mit deinem Namen zu kommentieren",
}: {
  open: boolean;
  onAnonymous: () => void;
  onSignIn: () => void;
  onCancel: () => void;
  /** Overridable copy so the same dialog serves comments and photo uploads. */
  title?: string;
  anonymousText?: string;
  signInText?: string;
}) {
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[1200] grid place-items-center bg-ink/25 p-4 backdrop-blur-[3px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.2 }}
          onClick={onCancel}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="w-full max-w-[520px] rounded-3xl border border-line bg-surface p-6 shadow-float sm:p-7"
            onClick={(e) => e.stopPropagation()}
            initial={reduce ? false : { opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: reduce ? 0 : 0.22, ease: "easeOut" }}
          >
            <h2 className="text-title font-semibold text-ink">{title}</h2>
            <p className="mt-1 text-body text-muted">Dein Entwurf bleibt bei beiden Optionen erhalten.</p>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <ChoiceCard onClick={onSignIn} icon={<UserIcon width={26} height={26} className="text-teal" />} title="Anmelden" primary>
                {signInText}
              </ChoiceCard>
              <ChoiceCard onClick={onAnonymous} icon={<ThinProfileIcon />} title="Anonym weitermachen">
                {anonymousText}
              </ChoiceCard>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-2xl px-3 text-label font-medium text-muted transition-colors hover:bg-band hover:text-ink"
              >
                <CloseIcon width={15} height={15} />
                Schließen
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

function ChoiceCard({
  onClick,
  icon,
  title,
  children,
  primary = false,
}: {
  onClick: () => void;
  icon: ReactNode;
  title: string;
  children: ReactNode;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex h-full min-h-[150px] flex-col items-start rounded-2xl border p-4 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ${primary ? "border-teal/40 bg-teal/5 hover:bg-teal/10" : "border-line bg-page hover:border-teal/40 hover:bg-band"}`}
    >
      <span className="grid h-10 w-10 place-items-center rounded-full bg-surface text-teal">{icon}</span>
      <span className="mt-3 min-w-0">
        <span className="block text-body font-semibold text-ink">{title}</span>
        <span className="mt-0.5 block text-caption leading-relaxed text-muted">{children}</span>
      </span>
    </button>
  );
}

function ThinProfileIcon() {
  return (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" className="text-ink">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4.2 3.6-6.5 8-6.5s8 2.3 8 6.5" />
    </svg>
  );
}
