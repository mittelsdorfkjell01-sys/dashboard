import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CloseIcon } from "../lib/icons";

/**
 * Shared bottom-sheet chassis for the Fotogalerie/Kommentare overlays (Figma
 * Frame_10/11). Slides up from the bottom (~320ms, ease-out) — always a
 * `y: 100% → 0` transform, so the same animation works for both layouts
 * below without any JS breakpoint branching:
 *
 *  - `sm:` and up: a content-sized panel (never stretched to fill the
 *    screen) floating over the page, which is only blurred behind it, never
 *    darkened — no scrim.
 *  - below `sm:`: a full-screen sheet (`inset-0`) — the blur layer is
 *    dropped here (`hidden sm:block`) since the sheet already covers
 *    everything there is to blur.
 *
 * Closes via the pill, a click on the blurred area (desktop only — there's
 * nothing to click through to on the mobile sheet), or Esc; traps Tab focus
 * inside the panel and returns focus to the trigger on close.
 */
export default function OverlayPanel({
  open,
  onClose,
  triggerRef,
  children,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
  children: ReactNode;
}) {
  const reduce = useReducedMotion();
  const panelRef = useRef<HTMLDivElement>(null);

  // Lock the page while an overlay is open so the background can't be scrolled
  // or interacted with. Compensate the scrollbar width to avoid a layout jump.
  useEffect(() => {
    if (!open) return;
    const { body } = document;
    const prevOverflow = body.style.overflow;
    const prevPaddingRight = body.style.paddingRight;
    const scrollbar = window.innerWidth - document.documentElement.clientWidth;
    body.style.overflow = "hidden";
    if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
    return () => {
      body.style.overflow = prevOverflow;
      body.style.paddingRight = prevPaddingRight;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    return () => {
      triggerRef.current?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab") {
        const root = panelRef.current;
        if (!root) return;
        const focusables = root.querySelectorAll<HTMLElement>(
          'button, [href], [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="blur"
            aria-hidden="true"
            className="fixed inset-0 z-[1100] hidden bg-black/10 backdrop-blur-[2px] sm:block"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.2 }}
            onClick={onClose}
          />
          <motion.div
            key="panel"
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            tabIndex={-1}
            data-lenis-prevent
            className="fixed inset-0 z-[1101] overflow-y-auto bg-page outline-none sm:inset-x-0 sm:top-auto sm:bottom-0 sm:min-h-[50vh] sm:max-h-[90vh] sm:rounded-t-3xl"
            initial={{ y: reduce ? 0 : "100%" }}
            animate={{ y: 0 }}
            exit={{ y: reduce ? 0 : "100%" }}
            transition={{ duration: reduce ? 0 : 0.32, ease: "easeOut" }}
          >
            <div className="sticky top-0 z-10 flex justify-center bg-page pb-2 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center gap-1.5 text-label font-medium text-muted transition-colors hover:text-ink"
              >
                <CloseIcon width={15} height={15} />
                abbrechen
              </button>
            </div>
            <div className="px-6 pb-10 sm:px-10">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}
