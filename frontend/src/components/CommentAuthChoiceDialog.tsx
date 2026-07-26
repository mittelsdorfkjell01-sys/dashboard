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
}: {
  open: boolean;
  onAnonymous: () => void;
  onSignIn: () => void;
  onCancel: () => void;
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
          className="fixed inset-0 z-[1200] grid place-items-center p-4 backdrop-blur-[3px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.2 }}
          onClick={onCancel}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Kommentar verfassen"
            className="w-full max-w-[560px] rounded-[28px] bg-white/95 p-7 shadow-card backdrop-blur-md sm:p-9"
            onClick={(e) => e.stopPropagation()}
            initial={reduce ? false : { opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: reduce ? 0 : 0.22, ease: "easeOut" }}
          >
            <h2 className="text-center text-title font-semibold text-teal">Kommentar verfassen</h2>
            <p className="mt-1.5 text-center text-body text-muted">wie möchtest du fortfahren?</p>

            <div className="mt-7 grid gap-4 sm:grid-cols-2">
              <ChoiceCard onClick={onAnonymous} icon={<IncognitoIcon />} title="Anonym">
                dein Kommentar wird ohne Namen veröffentlicht
              </ChoiceCard>
              <ChoiceCard onClick={onSignIn} icon={<UserIcon width={26} height={26} />} title="Anmelden">
                melde dich an, um mit deinem Namen zu kommentieren
              </ChoiceCard>
            </div>

            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex items-center gap-1.5 text-label font-medium text-muted transition-colors hover:text-ink"
              >
                <CloseIcon width={15} height={15} />
                abbrechen
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
}: {
  onClick: () => void;
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col items-center rounded-3xl border border-line px-6 py-8 text-center transition-colors hover:border-teal/50 hover:bg-teal/[0.03]"
    >
      <span className="text-teal">{icon}</span>
      <span className="mt-4 text-body font-semibold text-ink">{title}</span>
      <span className="mt-2 max-w-[24ch] text-caption leading-relaxed text-muted">{children}</span>
      <span aria-hidden="true" className="mt-6 text-teal transition-transform group-hover:translate-x-1">
        <ArrowIcon />
      </span>
    </button>
  );
}

function IncognitoIcon() {
  return (
    <svg width="34" height="30" viewBox="0 0 34 30" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 15 9.6 6.4A3 3 0 0 1 12.5 4.3h9A3 3 0 0 1 24.4 6.4L27 15" />
      <line x1="3" y1="15.5" x2="31" y2="15.5" />
      <circle cx="10.5" cy="21.5" r="4.5" />
      <circle cx="23.5" cy="21.5" r="4.5" />
      <path d="M15 20.5c1.3-1 2.7-1 4 0" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="42" height="12" viewBox="0 0 42 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="6" x2="39" y2="6" />
      <path d="M33 1 39 6l-6 5" />
    </svg>
  );
}
